"""Claude Code CLI를 통한 기사 요약/번역/분류"""

import json
import logging
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from cyber_news.collector import Article

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """다음은 오늘 수집된 사이버전 관련 뉴스 기사 목록입니다.
각 기사를 분석하여 아래 JSON 형식으로 출력해주세요.

규칙:
1. 모든 제목과 요약은 한국어로 작성 (영어 기사는 번역)
2. 요약은 2-3문장으로 핵심만
3. 카테고리: "cyber_attack" (사이버공격/사건), "nation_state" (국가 사이버전), "policy" (정책/규제), "tech" (기술동향/취약점)
4. 영향도: "high", "medium", "low"
5. 반드시 유효한 JSON만 출력하세요. 다른 텍스트는 포함하지 마세요.

기사 데이터:
{articles_json}

출력 JSON 형식:
{{
  "executive_summary": ["핵심 요약 1", "핵심 요약 2", "핵심 요약 3"],
  "articles": [
    {{
      "title": "한국어 제목",
      "summary": "한국어 요약 2-3문장",
      "category": "cyber_attack|nation_state|policy|tech",
      "impact": "high|medium|low",
      "source": "출처명",
      "link": "원문 URL"
    }}
  ]
}}"""


@dataclass
class GeneratorResult:
    executive_summary: list[str] = field(default_factory=list)
    articles: list[dict] = field(default_factory=list)
    is_fallback: bool = False
    error: str = ""


def extract_json(text: str) -> dict | None:
    # 마크다운 코드블록 제거
    pattern = r"```(?:json)?\s*([\s\S]*?)```"
    match = re.search(pattern, text)
    if match:
        text = match.group(1).strip()

    # 앞뒤 비-JSON 텍스트 제거
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def call_claude_cli(prompt: str, timeout: int = 120) -> str | None:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(prompt)
        prompt_file = Path(f.name)

    try:
        result = subprocess.run(
            ["claude", "-p"],
            stdin=open(prompt_file, "r", encoding="utf-8"),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "login" in stderr.lower() or "auth" in stderr.lower():
                logger.error("Claude Code CLI 인증 실패. 'claude login' 실행 필요")
                return None
            logger.error(f"Claude Code CLI 에러: {stderr}")
            return None

        output = result.stdout.strip()
        if not output:
            logger.error("Claude Code CLI 빈 응답")
            return None

        return output

    except subprocess.TimeoutExpired:
        logger.error(f"Claude Code CLI 타임아웃 ({timeout}초)")
        return None
    except FileNotFoundError:
        logger.error("Claude Code CLI를 찾을 수 없습니다. 설치 확인 필요")
        return None
    finally:
        prompt_file.unlink(missing_ok=True)


def build_fallback(articles: list[Article]) -> GeneratorResult:
    logger.warning("폴백 모드: AI 요약 없이 원문 기반 보고서 생성")

    categorized = []
    for a in articles:
        categorized.append({
            "title": a.title,
            "summary": a.summary[:200] if a.summary else "",
            "category": "tech",
            "impact": "medium",
            "source": a.source_name,
            "link": a.link,
        })

    return GeneratorResult(
        executive_summary=["AI 요약을 사용할 수 없어 원문 기반으로 보고서를 생성했습니다."],
        articles=categorized,
        is_fallback=True,
    )


def generate(articles: list[Article], config: dict) -> GeneratorResult:
    if not articles:
        return GeneratorResult(
            executive_summary=["오늘 수집된 사이버전 관련 뉴스가 없습니다."],
            articles=[],
        )

    gen_config = config.get("generator", {})
    batch_size = gen_config.get("batch_size", 10)
    timeout = gen_config.get("timeout_seconds", 120)
    max_retries = gen_config.get("max_retries", 1)

    all_processed = []
    all_summaries = []

    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        batch_data = [
            {
                "title": a.title,
                "summary": a.summary[:300],
                "source": a.source_name,
                "link": a.link,
                "lang": a.lang,
            }
            for a in batch
        ]

        prompt = PROMPT_TEMPLATE.format(articles_json=json.dumps(batch_data, ensure_ascii=False, indent=2))

        output = None
        for attempt in range(max_retries + 1):
            output = call_claude_cli(prompt, timeout)
            if output:
                break
            if attempt < max_retries:
                logger.warning(f"재시도 {attempt + 1}/{max_retries}")

        if not output:
            logger.error(f"배치 {i // batch_size + 1} 처리 실패, 폴백 모드 전환")
            return build_fallback(articles)

        parsed = extract_json(output)
        if not parsed:
            logger.error(f"배치 {i // batch_size + 1} JSON 파싱 실패, 폴백 모드 전환")
            return build_fallback(articles)

        if "articles" in parsed:
            all_processed.extend(parsed["articles"])
        if "executive_summary" in parsed:
            all_summaries.extend(parsed["executive_summary"])

    # 영향도순 정렬
    impact_order = {"high": 0, "medium": 1, "low": 2}
    all_processed.sort(key=lambda a: impact_order.get(a.get("impact", "low"), 2))

    return GeneratorResult(
        executive_summary=all_summaries[:5],
        articles=all_processed,
    )
