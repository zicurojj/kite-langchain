from mcp.server.fastmcp import FastMCP
from trading import place_order, get_positions
from auth_fully_automated import FullyAutomatedKiteAuth

mcp = FastMCP("Zerodha MCP Server")

@mcp.tool()
def check_authentication_status() -> dict:
    try:
        auth_manager = FullyAutomatedKiteAuth()
        tokens = auth_manager.config.load_tokens()

        if not tokens:
            return {"content": [{"type": "text", "text": "❌ No authentication tokens found. Please run 'python auth_manager.py auth' to authenticate."}]}

        if auth_manager.is_token_valid(tokens):
            try:
                auth_manager.kc.set_access_token(tokens['access_token'])
                profile = auth_manager.kc.profile()
                user_name = profile.get('user_name', 'Unknown')
                if isinstance(user_name, dict):
                    user_name = user_name.get('name', 'Unknown')
                elif not isinstance(user_name, str):
                    user_name = str(user_name)
                email = profile.get('email', 'Unknown')
                if not isinstance(email, str):
                    email = str(email)
                broker = profile.get('broker', 'Unknown')
                if not isinstance(broker, str):
                    broker = str(broker)

                message = f"✅ Authentication Status: VALID\n👤 User: {user_name}\n📧 Email: {email}\n🏢 Broker: {broker}\n📅 Token Generated: {tokens.get('generated_at', 'Unknown')}"
            except Exception as e:
                message = f"✅ Authentication Status: VALID\n❌ Could not fetch user details: {e}"
        else:
            message = "❌ Authentication Status: INVALID or EXPIRED\n💡 Please run 'python auth_manager.py auth' to re-authenticate."

        return {"content": [{"type": "text", "text": message}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"❌ Error checking authentication: {e}"}]}

@mcp.tool()
def authenticate_now() -> dict:
    try:
        import subprocess
        subprocess.Popen(['python', 'token_auth_flow.py'])

        auth_manager = FullyAutomatedKiteAuth()
        status = auth_manager.get_token_status()

        if status['status'] == 'valid':
            tokens = auth_manager.config.load_tokens()
            message = "🔍 AUTHENTICATION STATUS CHECK\n\n✅ You already have a valid access token!\n\n"
            message += f"📅 Generated: {tokens.get('generated_at', 'Unknown')}\n⏰ Expires: {tokens.get('expires_at', 'Unknown')}\n\n"
            message += "❓ Do you want to re-authenticate anyway?\n"
            return {"content": [{"type": "text", "text": message}]}
        else:
            message = "🚀 Starting authentication flow...\n\n📋 What will happen:\n1. 🌐 Browser will open with Zerodha login\n2. 🔐 You log in\n3. 🤖 System automatically captures callback\n4. ⚡ Token saved\n5. ✅ Ready to trade!"
            return {"content": [{"type": "text", "text": message}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"❌ Authentication error: {e}"}]}

@mcp.tool()
def confirm_reauthenticate() -> dict:
    from trading import get_authenticated_kite_client
    kc = get_authenticated_kite_client(force_auth=True)
    profile = kc.profile()
    user = profile.get("user_name", "Unknown")
    return {"content": [{"type": "text", "text": f"🔄 Re-authenticated successfully for user: {user}"}]}

@mcp.tool()
def force_reauthenticate() -> dict:
    auth_manager = FullyAutomatedKiteAuth()
    access_token = auth_manager.authenticate_fully_automated(force=True)
    return {"content": [{"type": "text", "text": "🔄 Forced re-authentication complete"}]} if access_token else {"content": [{"type": "text", "text": "❌ Re-authentication failed"}]}

@mcp.tool()
def buy_a_stock(stock: str, qty: int) -> dict:
    result = place_order(stock, qty, "BUY")
    return {"content": [{"type": "text", "text": result.get("message", "❌ Error occurred")}]} if result else {"content": [{"type": "text", "text": "❌ No response from trading system"}]}

@mcp.tool()
def sell_a_stock(stock: str, qty: int) -> dict:
    result = place_order(stock, qty, "SELL")
    return {"content": [{"type": "text", "text": result.get("message", "❌ Error occurred")}]} if result else {"content": [{"type": "text", "text": "❌ No response from trading system"}]}

@mcp.tool()
def show_portfolio() -> dict:
    holdings = get_positions()
    return {"content": [{"type": "text", "text": holdings}]}

if __name__ == "__main__":
    from fastmcp.web import serve_web
    print("🌐 Launching Zerodha MCP server on 0.0.0.0:7860 ...")
    serve_web(mcp, host="0.0.0.0", port=7860)
