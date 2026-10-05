"""Official Instagram API and replaceable temporary image hosting. No secret logging."""
import base64
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import re
import socket
from threading import Event
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

GRAPH = "https://graph.instagram.com/v25.0"


class UploadError(ValueError):
    """민감한 서버 응답을 포함하지 않는 사용자 안내용 게시 오류."""
    pass


class Cancelled(UploadError):
    """최종 게시 이전 단계에서 사용자가 취소했음을 나타내는 오류."""
    pass


class PublishUncertain(UploadError):
    """최종 요청이 서버에 반영되었을 수 있어 확인 전 재시도를 막아야 하는 오류."""
    def __init__(self, container):
        """결과가 불확실한 컨테이너 번호와 중복 방지 안내를 오류에 보관한다."""
        self.container = container
        super().__init__("게시 결과를 확인하지 못했습니다. 중복 게시를 막기 위해 인스타 계정을 먼저 확인해 주세요.")


class NoRedirect(HTTPRedirectHandler):
    """다른 서버로 자격 증명이 전달되지 않도록 리디렉션을 거부한다."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """HTTP 리디렉션 요청을 생성하지 않아 인증 정보의 유출을 막는다."""
        return None  # Credentials must never travel to another origin.


def caption_counts(caption: str):
    """캡션의 문자 수와 공백으로 구분된 해시태그 수를 반환한다."""
    return len(caption), len(re.findall(r"(?<!\w)#[^\s#]+", caption))


def validate_caption(caption: str):
    """캡션 2,200자·해시태그 30개 제한을 검사하고 초과하면 안내 오류를 낸다."""
    length, tags = caption_counts(caption)
    if length > 2200 or tags > 30:
        raise UploadError("캡션은 2,200자, 해시태그는 30개까지 가능합니다. 문구를 줄여 주세요.")


def check_cancel(cancel):
    """취소 이벤트가 설정되어 있으면 다음 네트워크 단계 전에 중단한다."""
    if cancel and cancel.is_set():
        raise Cancelled("올리기를 취소했습니다. 저장한 PNG는 그대로 남아 있습니다.")


def wait(seconds, cancel):
    """취소 이벤트에 즉시 반응하며 재시도 또는 상태 조회 간격만큼 기다린다."""
    if cancel:
        if cancel.wait(seconds):
            check_cancel(cancel)
    else:
        time.sleep(seconds)


def request_json(url, params=None, *, token="", post=False, retry=True, cancel=None, deadline=None):
    """HTTPS 허용 서버에 요청하고 비밀 값을 숨긴 채 일시 오류를 최대 3회 시도한다."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ("graph.instagram.com", "api.imgbb.com"):
        raise UploadError("허용되지 않은 서버 주소입니다.")
    encoded = urlencode(params or {}).encode("utf-8")
    if not post and encoded:
        url += "?" + encoded.decode()
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if post:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    # Three attempts in total, except the non-idempotent publish commit.
    for attempt in range(3 if retry else 1):
        check_cancel(cancel)
        try:
            req = Request(url, data=encoded if post else None, headers=headers)
            timeout = min(20, deadline - time.monotonic()) if deadline is not None else 20
            if timeout <= 0:
                raise UploadError("이미지 준비가 30초를 넘었습니다. 잠시 후 다시 시도해 주세요.")
            with build_opener(NoRedirect()).open(req, timeout=timeout) as response:
                data = json.load(response)
            if not isinstance(data, dict) or "error" in data:
                raise UploadError("서버가 요청을 거절했습니다. 계정 연결과 권한을 확인해 주세요.")
            return data
        except HTTPError as error:
            try:
                code = json.loads(error.read()).get("error", {}).get("code")
            except (ValueError, AttributeError):
                code = None
            if error.code in (401, 403) or code in (10, 190, 200):
                raise UploadError("계정 연결이 만료되었거나 게시 권한이 없습니다. 설정에서 다시 연결해 주세요.") from None
            if error.code not in (429, 500, 502, 503, 504):
                raise UploadError("서버가 요청을 거절했습니다. 계정 권한과 이미지 호스팅 키를 확인해 주세요.") from None
        except (URLError, TimeoutError, socket.timeout, ConnectionError, OSError):
            pass
        except (ValueError, TypeError):
            raise UploadError("서버 응답을 읽지 못했습니다. 잠시 후 다시 시도해 주세요.") from None
        if retry and attempt < 2:
            wait(2, cancel)
    raise UploadError("인터넷 연결을 확인하고 다시 눌러 주세요.")


def connect(token: str) -> dict:
    """공식 Instagram API에서 토큰의 사용자 번호와 계정명을 조회한다."""
    if not token.strip():
        raise UploadError("액세스 토큰을 입력해 주세요.")
    data = request_json(f"{GRAPH}/me", {"fields": "user_id,username"}, token=token)
    if not data.get("user_id") or not data.get("username"):
        raise UploadError("계정을 확인하지 못했습니다. 프로페셔널 계정과 토큰을 확인해 주세요.")
    return {"id": str(data["user_id"]), "username": data["username"]}


def refresh(token: str) -> dict:
    """유효한 장기 토큰을 공식 갱신 API로 교체하고 실제 수명을 반환한다."""
    result = request_json("https://graph.instagram.com/refresh_access_token", {
        "grant_type": "ig_refresh_token", "access_token": token,
    })
    if not result.get("access_token") or not isinstance(result.get("expires_in"), (int, float)):
        raise UploadError("토큰을 갱신하지 못했습니다. 설정에서 다시 연결해 주세요.")
    return result


def expiry_date(seconds=60 * 86400):
    """현재 UTC 시각에서 지정 초 후의 만료일을 ISO 8601 문자열로 반환한다."""
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def days_remaining(expires_at: str):
    """시간대가 있는 만료일까지 남은 일수를 계산하고 잘못된 값이면 None을 반환한다."""
    if not expires_at:
        return None
    try:
        return (datetime.fromisoformat(expires_at) - datetime.now(timezone.utc)).total_seconds() / 86400
    except (ValueError, TypeError):
        return None


def host_image(image, key: str, cancel: Event | None = None) -> str:
    """이미지를 품질 95 JPEG로 변환해 1시간 만료 조건으로 ImgBB에 올린다."""
    buffer = BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=95)
    result = request_json("https://api.imgbb.com/1/upload", {
        "key": key, "expiration": 3600,
        "image": base64.b64encode(buffer.getvalue()).decode("ascii"),
    }, post=True, cancel=cancel)
    url = result.get("data", {}).get("url", "")
    if not result.get("success") or urlparse(url).scheme != "https":
        raise UploadError("이미지 주소를 받지 못했습니다. 이미지 호스팅 키를 확인해 주세요.")
    return url


def ready(container, token, cancel):
    """최대 30초 동안 컨테이너 준비 상태를 조회하며 오류·만료·취소를 처리한다."""
    deadline = time.monotonic() + 30
    while True:
        data = request_json(f"{GRAPH}/{container}", {"fields": "status_code"}, token=token, cancel=cancel, deadline=deadline)
        state = data.get("status_code")
        if state == "FINISHED":
            return
        if state in ("ERROR", "EXPIRED", "PUBLISHED"):
            raise UploadError("인스타그램이 이미지를 준비하지 못했습니다. 이미지와 계정 상태를 확인해 주세요.")
        if time.monotonic() >= deadline:
            raise UploadError("이미지 준비가 30초를 넘었습니다. 잠시 후 다시 시도해 주세요.")
        wait(min(2, max(0, deadline - time.monotonic())), cancel)


def publish(images, caption, user_id, token, key, progress=lambda message: None, cancel=None, checkpoint=lambda record: None):
    """1~10장을 단일 또는 캐러셀로 준비한 뒤 기록을 남기고 최종 게시를 한 번 요청한다."""
    validate_caption(caption)
    if not 1 <= len(images) <= 10:
        raise UploadError("한 번에 1~10장만 올릴 수 있습니다. 카드를 나눠 주세요.")
    if not user_id.isdigit() or not token or not key:
        raise UploadError("설정에서 인스타 계정과 이미지 호스팅 키를 연결해 주세요.")
    progress("게시 가능 횟수 확인 중")
    limit = request_json(f"{GRAPH}/{user_id}/content_publishing_limit", {"fields": "quota_usage,config"}, token=token, cancel=cancel)
    entries = limit.get("data", [])
    if not entries or not isinstance(entries[0].get("quota_usage"), int):
        raise UploadError("게시 가능 횟수를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.")
    maximum = min(100, entries[0].get("config", {}).get("quota_total", 100))
    if entries[0]["quota_usage"] >= maximum:
        raise UploadError("오늘 게시 가능 횟수를 모두 사용했습니다. 나중에 다시 올려 주세요.")
    children = []
    for i, image in enumerate(images, 1):
        check_cancel(cancel)
        progress(f"이미지 준비 중 ({i}/{len(images)})")
        url = host_image(image, key, cancel)
        params = {"image_url": url}
        params.update({"is_carousel_item": "true"} if len(images) > 1 else {"caption": caption})
        child = request_json(f"{GRAPH}/{user_id}/media", params, token=token, post=True, cancel=cancel).get("id")
        if not child:
            raise UploadError("이미지 준비 번호를 받지 못했습니다. 다시 시도해 주세요.")
        ready(child, token, cancel)
        children.append(child)
    container = children[0]
    if len(children) > 1:
        progress("여러 장 묶는 중")
        container = request_json(f"{GRAPH}/{user_id}/media", {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption}, token=token, post=True, cancel=cancel).get("id")
        if not container:
            raise UploadError("묶음 준비 번호를 받지 못했습니다. 다시 시도해 주세요.")
        ready(container, token, cancel)
    check_cancel(cancel)
    record = {"container_id": container, "timestamp": datetime.now(timezone.utc).isoformat(), "status": "pending", "id": "", "permalink": ""}
    checkpoint(record.copy())  # Persist before commit, including crash/ambiguous response cases.
    progress("최종 게시 중 — 이 단계에서는 취소할 수 없습니다")
    try:
        result = request_json(f"{GRAPH}/{user_id}/media_publish", {"creation_id": container}, token=token, post=True, retry=False)
        post_id = result.get("id")
        if not post_id:
            raise UploadError("게시물 번호를 받지 못했습니다.")
    except UploadError:
        raise PublishUncertain(container) from None
    record.update(id=post_id, status="published")
    checkpoint(record.copy())
    try:
        result = request_json(f"{GRAPH}/{post_id}", {"fields": "permalink"}, token=token)
        link = result.get("permalink", "")
        if urlparse(link).scheme == "https" and urlparse(link).hostname in ("instagram.com", "www.instagram.com"):
            record["permalink"] = link
    except UploadError:
        pass  # Publication succeeded; a link failure must never prompt reposting.
    checkpoint(record.copy())
    return record
