"""카카오톡 발송, 파일 아카이브, GitHub Pages 배포"""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

TOKENS_FILE = Path("kakao_token.json")


def load_tokens() -> dict:
    if TOKENS_FILE.exists():
        return json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
    return {}


def save_tokens(tokens: dict):
    TOKENS_FILE.write_text(json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8")


def refresh_kakao_token(config: dict) -> str | None:
    tokens = load_tokens()
    refresh_token = tokens.get("refresh_token")

    if not refresh_token:
        logger.error("카카오 refresh_token 없음. 초기 인증 필요")
        return None

    rest_api_key = str(config.get("kakao", {}).get("rest_api_key", ""))
    if not rest_api_key or rest_api_key == "YOUR_KAKAO_REST_API_KEY":
        logger.error("카카오 REST API 키 미설정")
        return None

    try:
        resp = requests.post(
            "https://kauth.kakao.com/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": rest_api_key,
                "refresh_token": refresh_token,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        tokens["access_token"] = data["access_token"]
        if "refresh_token" in data:
            tokens["refresh_token"] = data["refresh_token"]
        save_tokens(tokens)

        logger.info("카카오 토큰 갱신 완료")
        return data["access_token"]

    except Exception as e:
        logger.error(f"카카오 토큰 갱신 실패: {e}")
        return None


def get_access_token(config: dict) -> str | None:
    tokens = load_tokens()
    access_token = tokens.get("access_token")

    if access_token:
        # 토큰 유효성 검사
        try:
            resp = requests.get(
                "https://kapi.kakao.com/v1/user/access_token_info",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5,
            )
            if resp.status_code == 200:
                return access_token
        except Exception:
            pass

    return refresh_kakao_token(config)


def send_kakao_message(
    executive_summary: list[str],
    article_count: int,
    report_url: str,
    config: dict,
    date: datetime | None = None,
) -> bool:
    if date is None:
        date = datetime.now()

    access_token = get_access_token(config)
    if not access_token:
        logger.error("카카오톡 발송 실패: 액세스 토큰 없음")
        return False

    date_str = f"{date.month}/{date.day}"
    summary_text = "\n".join(f"★ {s}" for s in executive_summary[:3])

    if article_count == 0:
        description = "오늘은 수집된 뉴스가 없습니다."
    else:
        description = summary_text

    template = {
        "object_type": "feed",
        "content": {
            "title": f"사이버전 일일 브리핑 ({date_str})",
            "description": description,
            "image_url": "",
            "link": {
                "web_url": report_url,
                "mobile_web_url": report_url,
            },
        },
        "buttons": [
            {
                "title": "보고서 보기",
                "link": {
                    "web_url": report_url,
                    "mobile_web_url": report_url,
                },
            }
        ],
    }

    try:
        resp = requests.post(
            "https://kapi.kakao.com/v2/api/talk/memo/default/send",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"template_object": json.dumps(template, ensure_ascii=False)},
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("카카오톡 발송 완료")
        return True

    except Exception as e:
        logger.error(f"카카오톡 발송 실패: {e}")
        return False


def send_error_notification(error_msg: str, config: dict) -> bool:
    access_token = get_access_token(config)
    if not access_token:
        return False

    template = {
        "object_type": "text",
        "text": f"⚠ 사이버전 일일 브리핑 생성 오류\n\n{error_msg}",
        "link": {"web_url": "", "mobile_web_url": ""},
    }

    try:
        resp = requests.post(
            "https://kapi.kakao.com/v2/api/talk/memo/default/send",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"template_object": json.dumps(template, ensure_ascii=False)},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except Exception:
        return False


def deploy_to_github_pages(config: dict) -> bool:
    gh_config = config.get("github_pages", {})
    branch = gh_config.get("branch", "gh-pages")
    output_dir = config.get("output", {}).get("dir", "output")

    try:
        subprocess.run(["git", "add", output_dir], check=True, capture_output=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        subprocess.run(
            ["git", "commit", "-m", f"briefing: {date_str}"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "push", "origin", branch],
            check=True,
            capture_output=True,
        )
        logger.info("GitHub Pages 배포 완료")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"GitHub Pages 배포 실패: {e}")
        return False
    except FileNotFoundError:
        logger.error("git 명령을 찾을 수 없습니다")
        return False


def get_report_url(config: dict, date: datetime | None = None) -> str:
    if date is None:
        date = datetime.now()

    base_url = config.get("github_pages", {}).get("base_url", "")
    if base_url:
        return f"{base_url}/{date.year}/{date.month:02d}/{date.day:02d}.html"

    output_dir = Path(config.get("output", {}).get("dir", "output"))
    return str(output_dir / str(date.year) / f"{date.month:02d}" / f"{date.day:02d}.html")


def distribute(
    executive_summary: list[str],
    article_count: int,
    config: dict,
    date: datetime | None = None,
) -> dict:
    if date is None:
        date = datetime.now()

    results = {"kakao": False, "github_pages": False}

    report_url = get_report_url(config, date)

    results["kakao"] = send_kakao_message(
        executive_summary, article_count, report_url, config, date
    )

    if config.get("github_pages", {}).get("base_url"):
        results["github_pages"] = deploy_to_github_pages(config)

    return results
