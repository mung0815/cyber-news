"""collector 모듈 테스트"""

import pytest
from unittest.mock import patch, MagicMock

from cyber_news.collector import (
    Article,
    normalize_url,
    titles_are_similar,
    filter_by_keywords,
    deduplicate,
    fetch_feed,
    collect,
)


class TestNormalizeUrl:
    def test_removes_trailing_slash(self):
        assert normalize_url("https://example.com/article/") == "https://example.com/article"

    def test_removes_query_string(self):
        result = normalize_url("https://example.com/article")
        assert "?" not in result

    def test_preserves_path(self):
        assert normalize_url("https://example.com/a/b/c") == "https://example.com/a/b/c"


class TestTitlesSimilar:
    def test_identical_titles(self):
        assert titles_are_similar("Same Title", "Same Title") is True

    def test_case_insensitive(self):
        assert titles_are_similar("CYBER ATTACK", "cyber attack") is True

    def test_similar_above_threshold(self):
        assert titles_are_similar("Cyber Attack on Korea", "Cyber Attack on South Korea", 0.8) is True

    def test_different_below_threshold(self):
        assert titles_are_similar("Totally Different", "Nothing Similar", 0.8) is False

    def test_boundary_079(self):
        # 0.79 should not match at 0.8 threshold
        a = "abcdefghij"
        b = "abcdefghik"  # differ by 1 char in 10
        ratio = 0.9  # 9/10 similar
        assert titles_are_similar(a, b, 0.8) is True

    def test_korean_titles(self):
        assert titles_are_similar("사이버 공격 발생", "사이버 공격이 발생") is True


class TestFilterByKeywords:
    def test_matches_title(self):
        articles = [Article(title="사이버전 관련 뉴스", link="http://a.com")]
        result = filter_by_keywords(articles, {"ko": ["사이버전"], "en": []})
        assert len(result) == 1

    def test_matches_summary(self):
        articles = [Article(title="뉴스", link="http://a.com", summary="해킹 사건 발생")]
        result = filter_by_keywords(articles, {"ko": ["해킹"], "en": []})
        assert len(result) == 1

    def test_case_insensitive(self):
        articles = [Article(title="APT Group Attack", link="http://a.com")]
        result = filter_by_keywords(articles, {"ko": [], "en": ["apt"]})
        assert len(result) == 1

    def test_no_match(self):
        articles = [Article(title="Weather News", link="http://a.com")]
        result = filter_by_keywords(articles, {"ko": ["사이버전"], "en": ["hacking"]})
        assert len(result) == 0

    def test_empty_keywords_passes_all(self):
        articles = [Article(title="Any News", link="http://a.com")]
        result = filter_by_keywords(articles, {"ko": [], "en": []})
        assert len(result) == 1

    def test_mixed_ko_en_keywords(self):
        articles = [
            Article(title="사이버전 동향", link="http://a.com"),
            Article(title="Cyber Warfare Update", link="http://b.com"),
        ]
        result = filter_by_keywords(articles, {"ko": ["사이버전"], "en": ["cyber warfare"]})
        assert len(result) == 2


class TestDeduplicate:
    def test_removes_url_duplicates(self):
        articles = [
            Article(title="Title A", link="https://example.com/article"),
            Article(title="Title B", link="https://example.com/article/"),
        ]
        result = deduplicate(articles)
        assert len(result) == 1

    def test_removes_title_duplicates(self):
        articles = [
            Article(title="Cyber Attack on Korea", link="http://a.com/1"),
            Article(title="Cyber Attack on Korea!", link="http://b.com/2"),
        ]
        result = deduplicate(articles, threshold=0.8)
        assert len(result) == 1

    def test_keeps_different_articles(self):
        articles = [
            Article(title="Cyber Attack", link="http://a.com/1"),
            Article(title="Policy Update", link="http://b.com/2"),
        ]
        result = deduplicate(articles)
        assert len(result) == 2


class TestFetchFeed:
    @patch("cyber_news.collector.requests.get")
    def test_successful_fetch(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"""<?xml version="1.0"?>
        <rss version="2.0">
        <channel>
        <item><title>Test Article</title><link>http://test.com/1</link><description>Summary</description></item>
        </channel>
        </rss>"""
        mock_get.return_value = mock_resp

        result = fetch_feed({"name": "Test", "url": "http://test.com/feed", "lang": "en"})
        assert len(result) == 1
        assert result[0].title == "Test Article"

    @patch("cyber_news.collector.requests.get")
    def test_failed_fetch_retries(self, mock_get):
        mock_get.side_effect = Exception("Connection error")
        result = fetch_feed({"name": "Test", "url": "http://test.com/feed"}, max_retries=2)
        assert len(result) == 0
        assert mock_get.call_count == 2

    @patch("cyber_news.collector.requests.get")
    def test_empty_feed(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"""<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>"""
        mock_get.return_value = mock_resp

        result = fetch_feed({"name": "Test", "url": "http://test.com/feed"})
        assert len(result) == 0


class TestCollect:
    @patch("cyber_news.collector.fetch_feed")
    def test_full_pipeline(self, mock_fetch):
        mock_fetch.return_value = [
            Article(title="사이버 공격 뉴스", link="http://a.com/1", source_name="TestSource"),
        ]
        config = {
            "sources": [{"name": "Test", "url": "http://test.com/feed"}],
            "keywords": {"ko": ["사이버"], "en": []},
            "dedup": {"title_similarity_threshold": 0.8},
        }
        result = collect(config)
        assert len(result.articles) == 1

    @patch("cyber_news.collector.fetch_feed")
    def test_all_sources_fail(self, mock_fetch):
        mock_fetch.return_value = []
        config = {
            "sources": [{"name": "Test", "url": "http://test.com/feed"}],
            "keywords": {"ko": ["사이버"], "en": []},
        }
        result = collect(config)
        assert len(result.articles) == 0
        assert "전체 소스 수집 실패" in result.errors
