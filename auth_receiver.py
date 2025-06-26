from flask import Flask, request
import os
import logging

from token_auth_flow import exchange_token

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

@app.route("/callback")
def auth_callback_redirect():
    """Redirect handler for /callback to forward token to /auth/exchange"""
    token = request.args.get("request_token")
    if token:
        logging.info(f"🔀 Redirecting to /auth/exchange with token: {token}")
        return f'''
            <html>
              <head>
                <meta http-equiv="refresh" content="0;url=/auth/exchange?request_token={token}" />
              </head>
              <body>
                <p>Redirecting to authentication exchange...</p>
              </body>
            </html>
        '''
    return "❌ request_token missing in callback", 400

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    logging.info(f"🌐 Starting Auth Receiver on port {port}")
    app.run(host="0.0.0.0", port=port)
