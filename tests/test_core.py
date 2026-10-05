import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from wordcard.bible_books import BOOKS
from wordcard.exporter import export_png
from wordcard.layout import fit, font, font_name, paginate, prepare_template, templates, text_spec, wrap, PUNCTUATION
from wordcard.parser import Card, parse
from wordcard.project import Project, load_project, save_project
from wordcard.renderer import render
from wordcard.settings import Settings, atomic_json

SAMPLE = "제목\n날짜 | 설교자\n\n첫 번째 본문입니다.\n두 번째 문장입니다.\n\n직접 입력한 구절입니다.\n(요한복음 3:16)\n\n마무리 문장입니다."


class CoreTests(unittest.TestCase):
    """문단 판정, 카드 배치, PNG 픽셀과 작업 파일 보존을 검증한다."""
    def test_paragraphs_and_references(self):
        """문단 우선순위와 66권 이름·약칭의 장절 인식을 검증한다."""
        cards = parse(SAMPLE)
        self.assertEqual([c.type for c in cards], ['cover', 'body', 'verse', 'ending'])
        self.assertEqual(cards[0].subtitle, '날짜 | 설교자')
        self.assertEqual(cards[2].ref, '요한복음 3:16')
        self.assertNotIn('3:16', cards[2].text)
        self.assertEqual(parse(SAMPLE, ending=False)[-1].type, 'body')
        self.assertEqual(parse('제목')[0].type, 'cover')
        self.assertEqual(parse(' \n '), [])
        self.assertEqual(len(BOOKS), 66)
        for ref in ['요 3:16', '요한복음 3:16-18', '(시편 23:1)', '시편 23편 1절']:
            self.assertEqual(parse('제목\n\n본문 ' + ref)[1].type, 'verse', ref)
        for full, short in BOOKS:
            for name in [full, short]:
                self.assertEqual(parse('제목\n\n본문 (' + name + ' 1:1)')[1].type, 'verse')
        self.assertEqual(parse('제목\n\n참고요 3:16', ending=False)[1].type, 'body')

    def test_wrap_and_pagination(self):
        """한글 보존, 줄 폭, 문장부호 위치와 문장 단위 카드 분할을 검증한다."""
        template = prepare_template(templates()['light'], '4:5')
        face = font(template['fonts']['body'], 36)
        for source in ['한글 어절 단위로 줄을 바꿉니다.', '아주긴한글단어' * 8 + '.)', '긴 문장의 뒤에 ) 닫는 괄호가 있습니다.', '첫줄\n둘째줄']:
            lines = wrap(source, face, 220)
            self.assertEqual(''.join(source.split()), ''.join(''.join(lines).split()))
            self.assertTrue(all(face.getlength(line) <= 220 for line in lines))
            self.assertTrue(all(not line or line[0] not in PUNCTUATION for line in lines))
        sentence = '하루를 돌아보며 감사하는 마음을 가집니다.'
        cards = paginate([Card('body', ' '.join([sentence] * 40))], template)
        self.assertGreater(len(cards), 1)
        self.assertEqual(' '.join(c.text.replace('\n', ' ') for c in cards), ' '.join([sentence] * 40))
        self.assertTrue(all(c.text.endswith('.') and fit(c.text, font_name(template, c.type), text_spec(template, c.type)) for c in cards))
        with self.assertRaisesRegex(ValueError, '한 문장'):
            paginate([Card('body', '가' * 3000)], template)

    def test_render_export_and_ratios(self):
        """모든 템플릿·비율의 출력 크기, 안전 여백과 저장 픽셀 일치를 검증한다."""
        for key, data in templates().items():
            for ratio, height in [('4:5', 1350), ('1:1', 1080)]:
                template = prepare_template(data, ratio)
                cards = paginate(parse(SAMPLE), template)
                images = [render(c, template, Settings(), i, len(cards)) for i, c in enumerate(cards, 1)]
                self.assertTrue(all(image.size == (1080, height) for image in images))
                with tempfile.TemporaryDirectory() as directory:
                    destination = export_png(images, Path(directory), '../제목:*')
                    paths = sorted(destination.glob('*.png'))
                    self.assertEqual(len(paths), 4)
                    with Image.open(paths[0]) as output:
                        self.assertEqual(output.tobytes(), images[0].tobytes())
                        self.assertTrue(output.info.get('icc_profile'))
                    self.assertNotEqual(destination, export_png(images[:1], Path(directory), '../제목:*'))
                for layout in [*template['cards'].values(), {'footer': template['footer']}]:
                    for spec in layout.values():
                        if isinstance(spec, dict) and 'box' in spec:
                            x, y, w, h = spec['box']
                            self.assertGreaterEqual(min(x, y), 80)
                            self.assertLessEqual(x + w, 1000)
                            self.assertLessEqual(y + h, height - 80)

    def test_project_roundtrip_and_invalid_files(self):
        """작업 저장·복원 일치와 잘못된 카드 스키마 거부를 검증한다."""
        project = Project(source=SAMPLE, cards=parse(SAMPLE), caption='직접 쓴 설명', publications=[{'id': '123', 'status': 'published'}])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '작업.wordcard'
            save_project(path, project)
            self.assertEqual(load_project(path), project)
            data = json.loads(path.read_text(encoding='utf-8'))
            self.assertNotIn('token', data)
            data['cards'][0]['type'] = 'invalid'
            atomic_json(path, data)
            with self.assertRaisesRegex(ValueError, '형식'):
                load_project(path)
            path.write_text('{bad', encoding='utf-8')
            with self.assertRaises(ValueError):
                load_project(path)


if __name__ == '__main__':
    unittest.main()
