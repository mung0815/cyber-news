"""generator 모듈 테스트"""

import json
import pytest
from unittest.mock import patch, MagicMock

from cyber_news.collector import Article
from cyber_news.generator import extract_json, generate, build_fallback


class TestExtractJson:
    def test_plain_json(self):
        text = '{"key": "value"}'
        result = extract_json(text)
        assert result == {"key": "value"}

    def test_json_in_code_block(self):
        text = '```json\n{"key": "value"}\n```'
        result = extract_json(text)
        assert result == {"key": "value"}

    def test_json_with_surrounding_text(self):
        text = 'Here is the result:\n{"key": "value"}\nDone!'
        result = extract_json(text)
        assert result == {"key": "value"}

    def test_json_in_code_block_with_text(self):
        text = 'Sure, here you go:\n```json\n{"articles": []}\n```\nLet me know!'
        result = extract_json(text)
        assert result == {"articles": []}

    def test_invalid_json(self):
        result = extract_json("not json at all")
        assert result is None

    def test_empty_string(self):
        result = extract_json("")
        assert result is None

    def test_nested_json(self):
        data = {"executive_summary": ["요약1"], "articles": [{"title": "제목"}]}
        text = json.dumps(data, ensure_ascii=False)
        result = extract_json(text)
        assert result["executive_summary"] == ["요약1"]


class TestBuildFallback:
    def test_fallback_with_articles(self):
        articles = [
            Article(title="Test", link="http://a.com", summary="Summary text here", source_name="Src"),
        ]
        result = build_fallback(articles)
        assert result.is_fallback is True
        assert len(result.articles) == 1
        assert result.articles[0]["title"] == "Test"

    def test_fallback_truncates_summary(self):
        articles = [
            Article(title="Test", link="http://a.com", summary="x" * 300, source_name="Src"),
        ]
        result = build_fallback(articles)
        assert len(result.articles[0]["summary"]) == 200


class TestGenerate:
    def test_empty_articles(self):
        result = generate([], {})
        assert len(result.articles) == 0
        assert "없습니다" in result.executive_summary[0]

    @patch("cyber_news.generator.call_claude_cli")
    def test_successful_generation(self, mock_cli):
        mock_cli.return_value = json.dumps({
            "executive_summary": ["요약1", "요약2"],
            "articles": [
                {"title": "제목", "summary": "요약", "category": "cyber_attack",
                 "impact": "high", "source": "Test", "link": "http://a.com"}
            ]
        }, ensure_ascii=False)

        articles = [Article(title="Test", link="http://a.com", source_name="Test")]
        config = {"generator": {"batch_size": 10, "timeout_seconds": 60, "max_retries": 0}}
        result = generate(articles, config)
        assert len(result.articles) == 1
        assert result.is_fallback is False

    @patch("cyber_news.generator.call_claude_cli")
    def test_cli_failure_triggers_fallback(self, mock_cli):
        mock_cli.return_value = None

        articles = [Article(title="Test", link="http://a.com", source_name="Test")]
        config = {"generator": {"batch_size": 10, "timeout_seconds": 60, "max_retries": 0}}
        result = generate(articles, config)
        assert result.is_fallback is True

    @patch("cyber_news.generator.call_claude_cli")
    def test_json_parse_failure_triggers_fallback(self, mock_cli):
        mock_cli.return_value = "This is not JSON at all"

        articles = [Article(title="Test", link="http://a.com", source_name="Test")]
        config = {"generator": {"batch_size": 10, "timeout_seconds": 60, "max_retries": 0}}
        result = generate(articles, config)
        assert result.is_fallback is True

    @patch("cyber_news.generator.call_claude_cli")
    def test_articles_sorted_by_impact(self, mock_cli):
        mock_cli.return_value = json.dumps({
            "executive_summary": ["요약"],
            "articles": [
                {"title": "Low", "summary": "", "category": "tech", "impact": "low", "source": "T", "link": "http://1"},
                {"title": "High", "summary": "", "category": "tech", "impact": "high", "source": "T", "link": "http://2"},
                {"title": "Med", "summary": "", "category": "tech", "impact": "medium", "source": "T", "link": "http://3"},
            ]
        }, ensure_ascii=False)

        articles = [Article(title=f"A{i}", link=f"http://{i}", source_name="T") for i in range(3)]
        config = {"generator": {"batch_size": 10, "timeout_seconds": 60, "max_retries": 0}}
        result = generate(articles, config)
        assert result.articles[0]["impact"] == "high"
        assert result.articles[1]["impact"] == "medium"
        assert result.articles[2]["impact"] == "low"
