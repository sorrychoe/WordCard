import io
import json
from threading import Event
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from PIL import Image
from wordcard import uploader as u


class UploadTests(unittest.TestCase):
    """실제 계정 요청 없이 게시 순서, 재시도 및 실패 후 중복 방지를 검증한다."""
    def run_publish(self, count=1, fail_commit=False, fail_link=False):
        """API 응답을 모의해 게시 결과와 요청·체크포인트 이력을 반환한다."""
        calls, checkpoints = [], []
        def request(url, params=None, **kwargs):
            """테스트 시나리오에 따라 공식 API 응답 또는 통신 오류를 모의한다."""
            calls.append((url, params, kwargs))
            if url.endswith('content_publishing_limit'):
                return {'data': [{'quota_usage': 0, 'config': {'quota_total': 100}}]}
            if params and params.get('fields') == 'status_code':
                return {'status_code': 'FINISHED'}
            if url.endswith('/media_publish'):
                self.assertEqual(checkpoints[-1]['status'], 'pending')
                self.assertFalse(kwargs['retry'])
                if fail_commit:
                    raise u.UploadError('인터넷 오류')
                return {'id': 'published-id'}
            if params and params.get('fields') == 'permalink':
                if fail_link:
                    raise u.UploadError('인터넷 오류')
                return {'permalink': 'https://www.instagram.com/p/example/'}
            return {'id': f'container-{len(calls)}'}
        with patch.object(u, 'request_json', side_effect=request), patch.object(u, 'host_image', return_value='https://i.ibb.co/example.jpg'):
            try:
                result = u.publish([Image.new('RGB', (8, 8))] * count, '설명 #말씀', '123', 'mock-credential', 'mock-host-key', checkpoint=checkpoints.append)
            except u.PublishUncertain:
                result = None
        return result, calls, checkpoints

    def test_single_and_carousel(self):
        """장수별 게시 종류, 자식 컨테이너 수와 단 한 번의 최종 게시를 검증한다."""
        for count in [1, 2, 10]:
            result, calls, checkpoints = self.run_publish(count)
            self.assertEqual(result['status'], 'published')
            self.assertEqual(result['id'], 'published-id')
            media = [params for url, params, _ in calls if url.endswith('/media')]
            if count == 1:
                self.assertEqual(media[0]['caption'], '설명 #말씀')
            else:
                self.assertTrue(all(params['is_carousel_item'] == 'true' for params in media[:-1]))
                self.assertEqual(media[-1]['media_type'], 'CAROUSEL')
                self.assertEqual(len(media[-1]['children'].split(',')), count)
            self.assertEqual(len([c for c in calls if c[0].endswith('media_publish')]), 1)
            self.assertEqual(checkpoints[0]['status'], 'pending')
            self.assertEqual(checkpoints[-1]['status'], 'published')

    def test_commit_timeout_not_retried_and_link_failure_success(self):
        """게시 응답 단절 시 재시도를 막고 링크 실패는 게시 성공으로 유지하는지 검증한다."""
        result, calls, checkpoints = self.run_publish(fail_commit=True)
        self.assertIsNone(result)
        self.assertEqual(checkpoints[-1]['status'], 'pending')
        self.assertEqual(len([c for c in calls if c[0].endswith('media_publish')]), 1)
        result, _, checkpoints = self.run_publish(fail_link=True)
        self.assertEqual(result['status'], 'published')
        self.assertEqual(result['permalink'], '')

    def test_validation_cancel_and_quota(self):
        """캡션·태그·할당량·취소·HTTPS 제한에서 게시가 차단되는지 검증한다."""
        u.validate_caption('가' * 2200)
        with self.assertRaises(u.UploadError):
            u.validate_caption('가' * 2201)
        with self.assertRaises(u.UploadError):
            u.validate_caption(' '.join('#태그' for _ in range(31)))
        cancel = Event()
        cancel.set()
        with self.assertRaises(u.Cancelled):
            u.check_cancel(cancel)
        with patch.object(u, 'request_json', return_value={'data': [{'quota_usage': 100}]}), patch.object(u, 'host_image') as host:
            with self.assertRaises(u.UploadError):
                u.publish([Image.new('RGB', (8, 8))], '', '123', 'mock-credential', 'mock-host-key')
            host.assert_not_called()
        with self.assertRaises(u.UploadError):
            u.request_json('http://graph.instagram.com/me')

    def test_http_retry_redaction_and_expiration(self):
        """네트워크 재시도 횟수, 자격 증명 오류 안내와 만료 계산을 검증한다."""
        with patch.object(u, 'build_opener') as opener, patch.object(u, 'wait'):
            opener.return_value.open.side_effect = URLError('sensitive URL')
            with self.assertRaises(u.UploadError) as error:
                u.request_json(u.GRAPH + '/me', token='mock-credential')
            self.assertNotIn('sensitive', str(error.exception))
            self.assertEqual(opener.return_value.open.call_count, 3)
        with patch.object(u, 'build_opener') as opener:
            opener.return_value.open.side_effect = HTTPError(u.GRAPH, 400, 'secret', {}, io.BytesIO(json.dumps({'error': {'code': 190}}).encode()))
            with self.assertRaisesRegex(u.UploadError, '다시 연결'):
                u.request_json(u.GRAPH + '/me')
            self.assertEqual(opener.return_value.open.call_count, 1)
        self.assertGreater(u.days_remaining(u.expiry_date()), 59)
        self.assertIsNone(u.days_remaining('bad'))

    def test_hosting_jpeg_and_one_hour_expiry(self):
        """호스팅에 전달한 데이터가 JPEG이며 만료 시간이 3,600초인지 검증한다."""
        with patch.object(u, 'request_json', return_value={'success': True, 'data': {'url': 'https://i.ibb.co/image.jpg'}}) as request:
            u.host_image(Image.new('RGBA', (10, 10)), 'mock-host-key')
            params = request.call_args.args[1]
            self.assertEqual(params['expiration'], 3600)
            import base64
            with Image.open(io.BytesIO(base64.b64decode(params['image']))) as image:
                self.assertEqual(image.format, 'JPEG')
                self.assertEqual(image.mode, 'RGB')

    def test_poll_failure_never_publishes(self):
        """컨테이너 준비 실패 후에는 게시 API를 절대 호출하지 않는지 검증한다."""
        def request(url, params=None, **kwargs):
            """테스트 시나리오에 따라 공식 API 응답 또는 통신 오류를 모의한다."""
            if url.endswith('content_publishing_limit'):
                return {'data': [{'quota_usage': 0}]}
            if params and params.get('fields') == 'status_code':
                return {'status_code': 'ERROR'}
            if url.endswith('/media_publish'):
                self.fail('Must not publish before images are ready')
            return {'id': 'container'}
        with patch.object(u, 'request_json', side_effect=request), patch.object(u, 'host_image', return_value='https://i.ibb.co/image.jpg'):
            with self.assertRaises(u.UploadError):
                u.publish([Image.new('RGB', (8, 8))], '', '123', 'mock-credential', 'mock-host-key')


if __name__ == '__main__':
    unittest.main()
