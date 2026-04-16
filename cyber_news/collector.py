"""RSS 뉴스 수집, 키워드 필터링, 중복 제거"""

import logging
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from urllib.parse import urlparse, urlunparse

import feedparser
import requests

logger = logging.getLogger(__name__)


@dataclass
class Article:
    title: str
    link: str
    summary: str = ""
    published: str = ""
    source_name: str = ""
    lang: str = "en"


@dataclass
class CollectorResult:
    articles: list[Article] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def titles_are_similar(a: str, b: str, threshold: float = 0.8) -> bool:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= threshold


def fetch_feed(source: dict, max_retries: int = 3) -> list[Article]:
    name = source["name"]
    url = source["url"]
    lang = source.get("lang", "en")

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, timeout=30, headers={
                "User-Agent": "CyberNewsBriefing/1.0"
            })
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)

            articles = []
            for entry in feed.entries:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue

                summary = ""
                if hasattr(entry, "summary"):
                    summary = entry.summary.strip()
                elif hasattr(entry, "description"):
                    summary = entry.description.strip()

                published = ""
                if hasattr(entry, "published"):
                    published = entry.published

                articles.append(Article(
                    title=title,
                    link=link,
                    summary=summary,
                    published=published,
                    source_name=name,
                    lang=lang,
                ))

            logger.info(f"[{name}] {len(articles)}건 수집 완료")
            return articles

        except Exception as e:
            wait = 2 ** attempt
            logger.warning(f"[{name}] 시도 {attempt + 1}/{max_retries} 실패: {e}")
            if attempt < max_retries - 1:
                time.sleep(wait)

    logger.error(f"[{name}] 모든 재시도 실패")
    return []


def filter_by_keywords(articles: list[Article], keywords: dict) -> list[Article]:
    ko_keywords = [k.lower() for k in keywords.get("ko", [])]
    en_keywords = [k.lower() for k in keywords.get("en", [])]
    all_keywords = ko_keywords + en_keywords

    if not all_keywords:
        logger.warning("키워드가 비어 있습니다. 전체 기사를 통과시킵니다.")
        return articles

    filtered = []
    for article in articles:
        text = f"{article.title} {article.summary}".lower()
        if any(kw in text for kw in all_keywords):
            filtered.append(article)

    logger.info(f"키워드 필터: {len(articles)}건 → {len(filtered)}건")
    return filtered


def deduplicate(articles: list[Article], threshold: float = 0.8) -> list[Article]:
    seen_urls = set()
    unique = []

    for article in articles:
        normalized = normalize_url(article.link)
        if normalized in seen_urls:
            continue

        is_dup = False
        for existing in unique:
            if titles_are_similar(article.title, existing.title, threshold):
                is_dup = True
                break

        if not is_dup:
            seen_urls.add(normalized)
            unique.append(article)

    logger.info(f"중복 제거: {len(articles)}건 → {len(unique)}건")
    return unique


def collect(config: dict) -> CollectorResult:
    sources = config.get("sources", [])
    keywords = config.get("keywords", {})
    threshold = config.get("dedup", {}).get("title_similarity_threshold", 0.8)

    result = CollectorResult()
    all_articles = []

    for source in sources:
        articles = fetch_feed(source)
        if articles:
            all_articles.extend(articles)
            result.stats[source["name"]] = len(articles)
        else:
            result.errors.append(f"{source['name']}: 수집 실패")
            result.stats[source["name"]] = 0

    if not all_articles:
        logger.error("모든 소스에서 수집 실패")
        result.errors.append("전체 소스 수집 실패")
        return result

    filtered = filter_by_keywords(all_articles, keywords)
    unique = deduplicate(filtered, threshold)
    result.articles = unique
    return result
