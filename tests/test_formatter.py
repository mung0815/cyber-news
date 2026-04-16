"""formatter 모듈 테스트"""

from datetime import datetime
from pathlib import Path

import pytest

from cyber_news.formatter import render_html
from cyber_news.generator import GeneratorResult


@pytest.fixture
def sample_config():
    return {
        "sources": [{"name": "Test"}, {"name": "Test2"}],
        "output": {"dir": "test_output", "generate_pdf": False, "generate_index": False},
    }


class TestRenderHtml:
    def test_normal_render(self, sample_config):
        result = GeneratorResult(
            executive_summary=["요약1", "요약2"],
            articles=[
                {"title": "테스트 기사", "summary": "요약 내용", "category": "cyber_attack",
                 "impact": "high", "source": "Test", "link": "http://a.com"},
            ],
        )
        html = render_html(result, sample_config, datetime(2026, 4, 16))
        assert "사이버전 일일 브리핑" in html
        assert "2026년 4월 16일" in html
        assert "테스트 기사" in html
        assert "요약1" in html

    def test_empty_report(self, sample_config):
        result = GeneratorResult(
            executive_summary=["오늘 수집된 뉴스가 없습니다."],
            articles=[],
        )
        html = render_html(result, sample_config, datetime(2026, 4, 16))
        assert "수집된 사이버전 관련 뉴스가 없습니다" in html

    def test_fallback_banner(self, sample_config):
        result = GeneratorResult(
            executive_summary=["원문 기반"],
            articles=[{"title": "A", "summary": "", "category": "tech",
                       "impact": "low", "source": "T", "link": "http://a"}],
            is_fallback=True,
        )
        html = render_html(result, sample_config, datetime(2026, 4, 16))
        assert "AI 요약 미사용" in html

    def test_html_escaping(self, sample_config):
        result = GeneratorResult(
            executive_summary=["<script>alert('xss')</script>"],
            articles=[
                {"title": "<b>XSS</b>", "summary": "", "category": "tech",
                 "impact": "low", "source": "T", "link": "http://a"},
            ],
        )
        html = render_html(result, sample_config, datetime(2026, 4, 16))
        assert "<script>alert" not in html
        assert "&lt;b&gt;" in html

    def test_category_filtering(self, sample_config):
        result = GeneratorResult(
            executive_summary=["요약"],
            articles=[
                {"title": "Attack", "summary": "", "category": "cyber_attack",
                 "impact": "high", "source": "T", "link": "http://1"},
                {"title": "Policy", "summary": "", "category": "policy",
                 "impact": "low", "source": "T", "link": "http://2"},
            ],
        )
        html = render_html(result, sample_config, datetime(2026, 4, 16))
        assert "사이버공격/사건" in html
        assert "정책/규제" in html
        # nation_state 카테고리는 기사가 없으므로 표시 안 됨
        assert "국가 사이버전 동향" not in html
