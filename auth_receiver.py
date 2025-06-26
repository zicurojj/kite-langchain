from flask import Flask, request
import os
import logging
from auth_manager import UnifiedAuthManager

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route("/auth/exchange")
def auth_exchange():
    """Accept request_token via query param and exchange for access token"""
    token = request.args.get("request_token")
    if not token:
        return "❌ request_token is missing in query string", 400

    try:
        logging.info(f"🔁 Received request_token: {token}")
        success = exchange_token(token)
        return "✅ Token exchange completed" if success else "❌ Token exchange failed", 200
    except Exception as e:
        logging.exception("Token exchange error")
        return f"❌ Error: {str(e)}", 500

@app.route('/callback')
def handle_callback():
    request_token = request.args.get("request_token")
    if not request_token:
        return "Missing request token", 400

    # Instantiate and use AuthManager to exchange the token
    auth_manager = UnifiedAuthManager()
    access_token = auth_manager.exchange_request_token(request_token)

    return f"Access Token stored: {access_token}"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    logging.info(f"🌐 Starting Auth Receiver on port {port}")
    app.run(host="0.0.0.0", port=port)
