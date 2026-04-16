"""config.yaml 로드 및 검증"""

import logging
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = {
    "sources": "RSS 소스 목록이 필요합니다",
    "keywords": "키워드 설정이 필요합니다",
}


def load_config(path: str = "config.yaml") -> dict:
    config_path = Path(path)
    if not config_path.exists():
        logger.error(f"설정 파일을 찾을 수 없습니다: {path}")
        sys.exit(1)

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not config:
        logger.error("설정 파일이 비어 있습니다")
        sys.exit(1)

    return config


def validate_config(config: dict) -> list[str]:
    errors = []

    for field, msg in REQUIRED_FIELDS.items():
        if field not in config or not config[field]:
            errors.append(f"필수 필드 누락: {field} — {msg}")

    sources = config.get("sources", [])
    if not isinstance(sources, list):
        errors.append("sources는 리스트여야 합니다")
    else:
        for i, source in enumerate(sources):
            if not isinstance(source, dict):
                errors.append(f"sources[{i}]: 딕셔너리여야 합니다")
                continue
            if "url" not in source:
                errors.append(f"sources[{i}]: url 필드 누락")
            elif source["url"]:
                parsed = urlparse(source["url"])
                if not parsed.scheme or not parsed.netloc:
                    errors.append(f"sources[{i}]: 잘못된 URL 형식 — {source['url']}")
            if "name" not in source:
                errors.append(f"sources[{i}]: name 필드 누락")

    keywords = config.get("keywords", {})
    if isinstance(keywords, dict):
        all_kw = keywords.get("ko", []) + keywords.get("en", [])
        if not all_kw:
            errors.append("키워드가 비어 있습니다. 모든 기사가 필터링됩니다")

    kakao = config.get("kakao", {})
    if kakao:
        api_key = kakao.get("rest_api_key", "")
        if not api_key or api_key == "YOUR_KAKAO_REST_API_KEY":
            logger.warning("카카오 REST API 키 미설정. 카카오톡 발송이 건너뛰어집니다.")

    return errors
