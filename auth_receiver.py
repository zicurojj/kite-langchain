from flask import Flask, request, jsonify
from auth_fully_automated import FullyAutomatedKiteAuth

app = Flask(__name__)
auth_manager = FullyAutomatedKiteAuth()

@app.route("/auth/exchange", methods=["POST"])
def exchange_token():
    data = request.get_json()
    request_token = data.get("request_token")
    if not request_token:
        return jsonify({"success": False, "error": "No request_token provided"}), 400

    success = auth_manager.exchange_request_token(request_token)
    if success:
        return jsonify({"success": True, "message": "Access token generated and saved"})
    else:
        return jsonify({"success": False, "error": "Token exchange failed"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
