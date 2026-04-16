# 사이버전 일일 브리핑 자동 생성기

매일 사이버전/사이버작전/해킹 관련 뉴스를 자동 수집하고, AI로 요약/번역/분류하여 디지털 신문 형태의 브리핑 문서를 생성합니다.

## 기능

- RSS 기반 뉴스 자동 수집 (한국어 + 영어 소스)
- 키워드 필터링 + 중복 제거
- Claude Code CLI로 기사 요약/번역/분류 (JSON 출력)
- 디지털 신문 스타일 HTML 보고서 (반응형, 인쇄 최적화)
- PDF 변환 (WeasyPrint)
- 카카오톡 자동 발송 (피드형 메시지)
- GitHub Pages 자동 배포
- 날짜별 아카이브 인덱스 페이지

## 설치

```bash
git clone https://github.com/YOUR_USERNAME/cyber-news.git
cd cyber-news
pip install -r requirements.txt
```

## 설정

`config.yaml`을 편집하세요:

1. **RSS 소스** — `sources` 섹션에 수집할 뉴스 사이트 추가
2. **키워드** — `keywords` 섹션에 필터 키워드 설정
3. **카카오톡** — `kakao.rest_api_key`에 카카오 REST API 키 입력
4. **GitHub Pages** — `github_pages` 섹션에 저장소 정보 입력

### 카카오톡 설정

1. [Kakao Developers](https://developers.kakao.com/)에서 앱 등록
2. 카카오 로그인 + 카카오톡 메시지 API 활성화
3. REST API 키를 `config.yaml`에 입력
4. 최초 1회 토큰 발급 필요 (OAuth2)

### 설정 검증

```bash
python -m cyber_news.main --validate-only
```

## 실행

```bash
python -m cyber_news.main
```

### 자동 실행 (cron)

```bash
# 매일 아침 6시 실행 (Linux/Mac)
0 6 * * * cd /path/to/cyber-news && python -m cyber_news.main

# Windows Task Scheduler
# 작업 스케줄러에서 매일 06:00에 실행하도록 등록
```

## 출력

- `output/YYYY/MM/DD.html` — 일일 브리핑 HTML
- `output/YYYY/MM/DD.pdf` — PDF 버전
- `output/index.html` — 아카이브 인덱스
- `logs/YYYY-MM-DD.log` — 실행 로그

## 테스트

```bash
python -m pytest tests/ -v
```

## 프로젝트 구조

```
cyber-news/
├── config.yaml          # 설정 파일
├── requirements.txt     # 의존성
├── cyber_news/
│   ├── __init__.py
│   ├── main.py          # CLI 엔트리포인트
│   ├── config.py        # 설정 로드/검증
│   ├── collector.py     # RSS 수집/필터/중복제거
│   ├── generator.py     # Claude Code CLI 연동
│   ├── formatter.py     # Jinja2 HTML/PDF 생성
│   └── distributor.py   # 카카오톡/GitHub Pages 배포
├── templates/
│   ├── newspaper.html   # 디지털 신문 템플릿
│   └── index.html       # 아카이브 인덱스 템플릿
├── tests/               # pytest 테스트
├── output/              # 생성된 보고서
└── logs/                # 실행 로그
```
