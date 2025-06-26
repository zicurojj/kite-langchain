from flask import Flask, request, jsonify
from auth_fully_automated import FullyAutomatedKiteAuth

app = Flask(__name__)
auth_manager = FullyAutomatedKiteAuth()

@app.route("/auth/exchange", methods=["POST"])
def exchange_token():
    """Exchange request token for access token via POST request"""
    data = request.get_json()
    request_token = data.get("request_token")
    if not request_token:
        return jsonify({"success": False, "error": "No request_token provided"}), 400

    success = auth_manager.exchange_request_token(request_token)
    if success:
        return jsonify({"success": True, "message": "Access token generated and saved"})
    else:
        return jsonify({"success": False, "error": "Token exchange failed"}), 500

@app.route("/callback")
def handle_callback():
    """Handle OAuth callback redirect"""
    request_token = request.args.get("request_token")
    if not request_token:
        return "❌ Missing request token", 400

    # Exchange token directly
    success = auth_manager.exchange_request_token(request_token)

    if success:
        return """
        <html>
        <head><title>Authentication Successful</title></head>
        <body style="font-family: Arial; text-align: center; margin-top: 50px;">
            <h2>✅ Authentication Successful!</h2>
            <p>Your access token has been generated and saved.</p>
            <p>You can close this window.</p>
        </body>
        </html>
        """
    else:
        return """
        <html>
        <head><title>Authentication Failed</title></head>
        <body style="font-family: Arial; text-align: center; margin-top: 50px;">
            <h2>❌ Authentication Failed</h2>
            <p>Token exchange failed. Please try again.</p>
        </body>
        </html>
        """, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
