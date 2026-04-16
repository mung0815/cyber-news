"""Jinja2 HTML 렌더링 + WeasyPrint PDF 변환"""

import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from cyber_news.generator import GeneratorResult

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def get_issue_number(output_dir: Path) -> int:
    existing = list(output_dir.glob("**/*.html"))
    return len(existing) + 1


def render_html(result: GeneratorResult, config: dict, date: datetime | None = None) -> str:
    if date is None:
        date = datetime.now()

    output_dir = Path(config.get("output", {}).get("dir", "output"))
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    template = env.get_template("newspaper.html")

    weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
    weekday = weekday_names[date.weekday()]
    date_str = f"{date.year}년 {date.month}월 {date.day}일 ({weekday})"

    html = template.render(
        date_str=date_str,
        issue_number=get_issue_number(output_dir),
        source_count=len(config.get("sources", [])),
        is_fallback=result.is_fallback,
        executive_summary=result.executive_summary,
        articles=result.articles,
        total_articles=len(result.articles),
    )

    return html


def render_index(reports: list[dict], config: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    template = env.get_template("index.html")

    months = {}
    for report in sorted(reports, key=lambda r: r["date"], reverse=True):
        month_key = report["date"].strftime("%Y년 %m월")
        if month_key not in months:
            months[month_key] = []
        months[month_key].append(report)

    return template.render(months=months)


def save_html(html: str, config: dict, date: datetime | None = None) -> Path:
    if date is None:
        date = datetime.now()

    output_dir = Path(config.get("output", {}).get("dir", "output"))
    year_dir = output_dir / str(date.year) / f"{date.month:02d}"
    year_dir.mkdir(parents=True, exist_ok=True)

    filepath = year_dir / f"{date.day:02d}.html"
    filepath.write_text(html, encoding="utf-8")
    logger.info(f"HTML 저장: {filepath}")
    return filepath


def save_pdf(html: str, config: dict, date: datetime | None = None) -> Path | None:
    if not config.get("output", {}).get("generate_pdf", True):
        return None

    if date is None:
        date = datetime.now()

    try:
        from weasyprint import HTML
    except (ImportError, OSError) as e:
        logger.warning(f"WeasyPrint 사용 불가. PDF 생성 건너뜀: {e}")
        return None

    output_dir = Path(config.get("output", {}).get("dir", "output"))
    year_dir = output_dir / str(date.year) / f"{date.month:02d}"
    year_dir.mkdir(parents=True, exist_ok=True)

    filepath = year_dir / f"{date.day:02d}.pdf"

    try:
        HTML(string=html).write_pdf(str(filepath))
        logger.info(f"PDF 저장: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"PDF 생성 실패: {e}")
        return None


def save_index(config: dict) -> Path | None:
    if not config.get("output", {}).get("generate_index", True):
        return None

    output_dir = Path(config.get("output", {}).get("dir", "output"))
    base_url = config.get("github_pages", {}).get("base_url", "")

    reports = []
    for html_file in sorted(output_dir.glob("**/*.html"), reverse=True):
        if html_file.name == "index.html":
            continue
        try:
            parts = html_file.relative_to(output_dir).parts
            if len(parts) == 3:
                year, month, day_file = parts
                day = day_file.replace(".html", "")
                date = datetime(int(year), int(month), int(day))
                weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
                reports.append({
                    "date": date,
                    "date_str": f"{date.year}년 {date.month}월 {date.day}일 ({weekday_names[date.weekday()]})",
                    "url": f"{base_url}/{year}/{month}/{day_file}" if base_url else f"{year}/{month}/{day_file}",
                    "article_count": "—",
                })
        except (ValueError, IndexError):
            continue

    if not reports:
        return None

    html = render_index(reports, config)
    index_path = output_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    logger.info(f"인덱스 저장: {index_path}")
    return index_path
