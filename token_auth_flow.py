import http.server
import socketserver
import threading
import webbrowser
import requests
from urllib.parse import urlparse, parse_qs
import time

class TokenCapturer:
    def __init__(self, api_key, droplet_url, port=8765):
        self.api_key = api_key
        self.droplet_url = droplet_url
        self.port = port
        self.request_token = None
        self._httpd = None

    class Handler(http.server.SimpleHTTPRequestHandler):
        parent = None

        def do_GET(self):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            if "/callback" in parsed.path and "request_token" in params:
                request_token = params["request_token"][0]
                self.parent.request_token = request_token

                print(f"✅ Captured request token: {request_token}")
                try:
                    response = requests.post(self.parent.droplet_url, json={"request_token": request_token})
                    if response.status_code == 200:
                        self.respond("✅ Token successfully exchanged and stored!")
                    else:
                        self.respond(f"❌ Token exchange failed: {response.text}")
                except Exception as e:
                    self.respond(f"❌ Error sending token to server: {str(e)}")
                finally:
                    # Shut down server
                    threading.Thread(target=self.parent.stop_server, daemon=True).start()
            else:
                self.respond("❌ Invalid callback or missing request_token")

        def respond(self, message):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            html = f"<html><body><h2>{message}</h2><p>You can close this window.</p></body></html>"
            self.wfile.write(html.encode("utf-8"))

        def log_message(self, format, *args):
            return  # Suppress default logs

    def start_server(self):
        self.Handler.parent = self
        self._httpd = socketserver.TCPServer(("", self.port), self.Handler)
        print(f"🌐 Listening on http://localhost:{self.port}/callback ...")
        self._httpd.serve_forever()

    def stop_server(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            print("🛑 Server shut down")

    def start_flow(self):
        login_url = f"https://kite.trade/connect/login?api_key={self.api_key}&redirect_url=http://localhost:{self.port}/callback"
        threading.Thread(target=self.start_server, daemon=True).start()
        time.sleep(1)
        print("🚀 Opening browser for login...")
        webbrowser.open(login_url)

def start_token_auth_flow(api_key, droplet_url, port=8765):
    """
    Starts the fully automatic token auth flow:
    1. Opens login in browser.
    2. Captures token locally.
    3. Sends it to the droplet automatically.
    """
    capturer = TokenCapturer(api_key=api_key, droplet_url=droplet_url, port=port)
    capturer.start_flow()

# CLI fallback for testing
if __name__ == "__main__":
    # Replace with actual values or inject from environment
    KITE_API_KEY = "imtwpp6e5x9ozlwt"
    DROPLET_URL = "http://zap.zicuro.shop:5001/auth/exchange"
    start_token_auth_flow(KITE_API_KEY, DROPLET_URL)
