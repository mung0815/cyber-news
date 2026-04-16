"""config 모듈 테스트"""

import pytest
from cyber_news.config import validate_config


class TestValidateConfig:
    def test_valid_config(self):
        config = {
            "sources": [{"name": "Test", "url": "https://example.com/feed"}],
            "keywords": {"ko": ["사이버전"], "en": ["hacking"]},
            "kakao": {"rest_api_key": "real_key_here"},
        }
        errors = validate_config(config)
        assert len(errors) == 0

    def test_missing_sources(self):
        config = {"keywords": {"ko": ["test"]}}
        errors = validate_config(config)
        assert any("sources" in e for e in errors)

    def test_missing_keywords(self):
        config = {"sources": [{"name": "T", "url": "https://a.com"}]}
        errors = validate_config(config)
        assert any("keywords" in e for e in errors)

    def test_invalid_url(self):
        config = {
            "sources": [{"name": "Test", "url": "not-a-url"}],
            "keywords": {"ko": ["test"]},
        }
        errors = validate_config(config)
        assert any("URL" in e for e in errors)

    def test_missing_source_name(self):
        config = {
            "sources": [{"url": "https://example.com/feed"}],
            "keywords": {"ko": ["test"]},
        }
        errors = validate_config(config)
        assert any("name" in e for e in errors)

    def test_empty_keywords_warning(self):
        config = {
            "sources": [{"name": "T", "url": "https://a.com"}],
            "keywords": {"ko": [], "en": []},
        }
        errors = validate_config(config)
        assert any("비어" in e for e in errors)

    def test_default_kakao_key_is_warning_not_error(self):
        config = {
            "sources": [{"name": "T", "url": "https://a.com"}],
            "keywords": {"ko": ["test"]},
            "kakao": {"rest_api_key": "YOUR_KAKAO_REST_API_KEY"},
        }
        errors = validate_config(config)
        # 카카오 키 미설정은 경고이므로 에러에 포함되지 않음
        assert not any("카카오" in e for e in errors)
