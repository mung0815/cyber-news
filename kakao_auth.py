"""카카오 OAuth2 토큰 발급 스크립트

브라우저에서 카카오 로그인 -> 인증 코드 -> access_token + refresh_token 발급
"""

import json
import threading
import webbrowser
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests
import yaml

# 설정 로드
config = yaml.safe_load(open("config.yaml", encoding="utf-8"))
REST_API_KEY = str(config["kakao"]["rest_api_key"])
REDIRECT_URI = "http://localhost:9876/callback"
TOKEN_FILE = "kakao_token.json"

auth_code = None
server_done = threading.Event()


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urlparse(self.path)

        if parsed.path == "/callback":
            params = parse_qs(parsed.query)
            if "code" in params:
                auth_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    "<html><body><h1>인증 성공!</h1>"
                    "<p>이 창을 닫아도 됩니다.</p></body></html>".encode("utf-8")
                )
                server_done.set()
            else:
                error = params.get("error_description", ["알 수 없는 에러"])[0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    f"<html><body><h1>인증 실패</h1><p>{error}</p></body></html>".encode("utf-8")
                )
                server_done.set()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # suppress logs


def main():
    global auth_code

    print("=" * 50)
    print("카카오 OAuth2 토큰 발급")
    print("=" * 50)
    print(f"REST API Key: {REST_API_KEY[:10]}...")
    print(f"Redirect URI: {REDIRECT_URI}")
    print()
    print("중요: 카카오 개발자 콘솔에서 다음을 확인하세요:")
    print(f"  1. 카카오 로그인 활성화")
    print(f"  2. Redirect URI에 '{REDIRECT_URI}' 등록")
    print(f"  3. 동의항목에서 '카카오톡 메시지 전송' 활성화")
    print()

    # 로컬 서버 시작
    server = HTTPServer(("localhost", 9876), CallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    # 브라우저에서 카카오 로그인 페이지 열기
    auth_url = (
        f"https://kauth.kakao.com/oauth/authorize"
        f"?client_id={REST_API_KEY}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=talk_message"
    )
    print("브라우저에서 카카오 로그인 페이지를 엽니다...")
    print(f"URL: {auth_url}")
    print()
    webbrowser.open(auth_url)

    print("카카오 로그인 대기 중... (브라우저에서 로그인하세요)")
    server_done.wait(timeout=120)
    server.shutdown()

    if not auth_code:
        print("에러: 인증 코드를 받지 못했습니다.")
        return

    print(f"인증 코드 수신: {auth_code[:20]}...")
    print()

    # 인증 코드 -> 토큰 교환
    print("토큰 교환 중...")

    token_data = {
        "grant_type": "authorization_code",
        "client_id": REST_API_KEY,
        "redirect_uri": REDIRECT_URI,
        "code": auth_code,
    }

    # Client Secret이 설정되어 있으면 추가
    client_secret = config.get("kakao", {}).get("client_secret", "")
    if client_secret:
        token_data["client_secret"] = str(client_secret)
        print(f"  client_secret 포함: {str(client_secret)[:6]}...")

    resp = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data=token_data,
        timeout=10,
    )

    if resp.status_code != 200:
        print(f"토큰 교환 실패: {resp.status_code}")
        print(resp.text)
        return

    tokens = resp.json()
    tokens["saved_at"] = datetime.now().isoformat()

    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, ensure_ascii=False, indent=2)

    print()
    print("토큰 발급 성공!")
    print(f"  access_token: {tokens['access_token'][:20]}...")
    print(f"  refresh_token: {tokens.get('refresh_token', 'N/A')[:20]}...")
    print(f"  scope: {tokens.get('scope', 'N/A')}")
    print(f"  저장: {TOKEN_FILE}")
    print()

    # 토큰 테스트 - 나에게 메시지 보내기
    print("테스트 메시지 발송 중...")
    test_resp = requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={
            "Authorization": f"Bearer {tokens['access_token']}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "template_object": json.dumps({
                "object_type": "text",
                "text": "사이버전 일일 브리핑 - 카카오톡 연동 테스트 성공!",
                "link": {"web_url": "", "mobile_web_url": ""},
            }, ensure_ascii=False)
        },
        timeout=10,
    )

    if test_resp.status_code == 0 or test_resp.status_code == 200:
        print("테스트 메시지 발송 성공! 카카오톡을 확인하세요.")
    else:
        print(f"테스트 메시지 실패: {test_resp.status_code} - {test_resp.text}")


if __name__ == "__main__":
    main()
