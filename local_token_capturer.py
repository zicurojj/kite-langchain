import http.server
import socketserver
import threading
import webbrowser
import requests
from urllib.parse import urlparse, parse_qs
import time

# Configuration
KITE_API_KEY = "your_api_key_here"  # Replace with your actual key
DROPLET_URL = "http://your_droplet_ip:5001/auth/exchange"  # Replace with actual droplet IP
LOCAL_PORT = 8765

# Request handler
class TokenCaptureHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "/callback" in parsed.path and "request_token" in params:
            request_token = params["request_token"][0]

            print(f"✅ Captured request token: {request_token}")

            try:
                response = requests.post(DROPLET_URL, json={"request_token": request_token})
                if response.status_code == 200:
                    self.respond("✅ Token successfully exchanged and stored!")
                else:
                    self.respond(f"❌ Token exchange failed: {response.text}")
            except Exception as e:
                self.respond(f"❌ Error sending token to server: {str(e)}")
        else:
            self.respond("❌ Invalid callback or missing request_token")

    def respond(self, message):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        html = f"<html><body><h2>{message}</h2><p>You can close this window.</p></body></html>"
        self.wfile.write(html.encode("utf-8"))

# Launch local server in a thread
def start_server():
    with socketserver.TCPServer(("", LOCAL_PORT), TokenCaptureHandler) as httpd:
        print(f"🌐 Listening on http://localhost:{LOCAL_PORT}/callback ...")
        httpd.serve_forever()

def main():
    login_url = f"https://kite.trade/connect/login?api_key={KITE_API_KEY}&redirect_url=http://localhost:{LOCAL_PORT}/callback"

    print("🚀 Opening browser for login...")
    threading.Thread(target=start_server, daemon=True).start()

    time.sleep(1)
    webbrowser.open(login_url)

    print("🕒 Waiting for user to complete login...")
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        print("🛑 Exiting...")

if __name__ == "__main__":
    main()
