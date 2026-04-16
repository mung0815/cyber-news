"""사이버전 일일 브리핑 — CLI 엔트리포인트"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from cyber_news.collector import collect
from cyber_news.config import load_config, validate_config
from cyber_news.distributor import distribute, send_error_notification
from cyber_news.formatter import render_html, save_html, save_index, save_pdf
from cyber_news.generator import generate


def setup_logging(date: datetime):
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"{date.strftime('%Y-%m-%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def run(config_path: str = "config.yaml"):
    now = datetime.now()
    setup_logging(now)
    logger = logging.getLogger("cyber_news")

    logger.info("=" * 60)
    logger.info(f"사이버전 일일 브리핑 시작 — {now.strftime('%Y-%m-%d %H:%M')}")
    logger.info("=" * 60)

    # 1. 설정 로드 및 검증
    config = load_config(config_path)
    errors = validate_config(config)
    if errors:
        for err in errors:
            logger.error(f"설정 오류: {err}")
        logger.error("설정 파일을 수정한 후 다시 실행하세요.")
        sys.exit(1)

    # 2. 뉴스 수집
    logger.info("--- 뉴스 수집 시작 ---")
    collect_result = collect(config)

    for name, count in collect_result.stats.items():
        logger.info(f"  {name}: {count}건")

    if collect_result.errors:
        for err in collect_result.errors:
            logger.warning(f"  수집 오류: {err}")

    if "전체 소스 수집 실패" in collect_result.errors:
        logger.error("모든 소스에서 수집 실패. 알림 발송 후 종료.")
        send_error_notification("모든 뉴스 소스에서 수집 실패", config)
        sys.exit(1)

    logger.info(f"총 {len(collect_result.articles)}건 수집 완료")

    # 3. AI 요약/번역/분류
    logger.info("--- AI 문서 생성 시작 ---")
    gen_result = generate(collect_result.articles, config)

    if gen_result.is_fallback:
        logger.warning("폴백 모드로 문서 생성됨 (AI 요약 미사용)")
    else:
        logger.info(f"AI 처리 완료: {len(gen_result.articles)}건")

    # 4. HTML/PDF 생성
    logger.info("--- 문서 출력 시작 ---")
    html = render_html(gen_result, config, now)
    html_path = save_html(html, config, now)
    pdf_path = save_pdf(html, config, now)
    index_path = save_index(config)

    # 5. 배포
    logger.info("--- 배포 시작 ---")
    dist_results = distribute(
        gen_result.executive_summary,
        len(gen_result.articles),
        config,
        now,
    )

    if dist_results["kakao"]:
        logger.info("카카오톡 발송 성공")
    else:
        logger.warning("카카오톡 발송 실패 (파일은 로컬에 저장됨)")

    # 6. 완료 요약
    logger.info("=" * 60)
    logger.info("완료 요약:")
    logger.info(f"  수집 기사: {len(collect_result.articles)}건")
    logger.info(f"  처리 기사: {len(gen_result.articles)}건")
    logger.info(f"  폴백 모드: {'예' if gen_result.is_fallback else '아니오'}")
    logger.info(f"  HTML: {html_path}")
    logger.info(f"  PDF: {pdf_path or '건너뜀'}")
    logger.info(f"  인덱스: {index_path or '건너뜀'}")
    logger.info(f"  카카오톡: {'성공' if dist_results['kakao'] else '실패'}")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="사이버전 일일 브리핑 자동 생성기")
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="설정 파일 경로 (기본: config.yaml)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="설정 파일 검증만 수행",
    )
    args = parser.parse_args()

    if args.validate_only:
        config = load_config(args.config)
        errors = validate_config(config)
        if errors:
            print("설정 오류:")
            for err in errors:
                print(f"  ✗ {err}")
            sys.exit(1)
        else:
            print("✓ 설정 파일 검증 완료. 문제 없음.")
            sys.exit(0)

    run(args.config)


if __name__ == "__main__":
    main()
