from mcp.server.fastmcp import FastMCP
from trading import place_order, get_positions
from auth_fully_automated import FullyAutomatedKiteAuth
from auth_utils import extract_profile_data, format_authentication_status
from datetime import datetime

mcp = FastMCP("Zerodha MCP Server")

auth_manager = FullyAutomatedKiteAuth()

@mcp.tool()
def get_kite_login_url() -> dict:
    try:
        login_url = auth_manager.get_login_url()
        return {
            "content": [{
                "type": "text",
                "text": f"🔗 Please open this URL in your browser to log in:\n\n{login_url}\n\nYour access token will be automatically saved after login."
            }]
        }
    except Exception as e:
        return {"content": [{"type": "text", "text": f"❌ Failed to generate login URL: {e}"}]}

@mcp.tool()
def check_authentication_status() -> dict:
    try:
        tokens = auth_manager.config.load_tokens()
        if not tokens:
            return {"content": [{"type": "text", "text": "❌ No authentication tokens found. Please run get_kite_login_url() to authenticate."}]}

        if auth_manager.is_token_valid(tokens):
            try:
                auth_manager.kc.set_access_token(tokens['access_token'])
                profile = auth_manager.kc.profile()
                profile_data = extract_profile_data(profile)
                message = format_authentication_status('valid', profile_data, tokens)
            except Exception as e:
                message = f"✅ Authentication Status: VALID\n❌ Could not fetch user details: {e}"
        else:
            message = format_authentication_status('expired')
        return {"content": [{"type": "text", "text": message}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"❌ Error checking authentication: {e}"}]}

@mcp.tool()
def buy_a_stock(stock: str, qty: int) -> dict:
    if not stock or not isinstance(stock, str):
        return {"content": [{"type": "text", "text": "❌ Invalid stock symbol."}]}
    if not isinstance(qty, int) or qty <= 0:
        return {"content": [{"type": "text", "text": "❌ Quantity must be a positive integer."}]}
    result = place_order(stock.upper(), qty, "BUY")
    return {"content": [{"type": "text", "text": result.get("message", "❌ Order failed.")}]} 

@mcp.tool()
def sell_a_stock(stock: str, qty: int) -> dict:
    if not stock or not isinstance(stock, str):
        return {"content": [{"type": "text", "text": "❌ Invalid stock symbol."}]}
    if not isinstance(qty, int) or qty <= 0:
        return {"content": [{"type": "text", "text": "❌ Quantity must be a positive integer."}]}
    result = place_order(stock.upper(), qty, "SELL")
    return {"content": [{"type": "text", "text": result.get("message", "❌ Order failed.")}]} 

@mcp.tool()
def show_portfolio() -> dict:
    try:
        holdings = get_positions()
        return {"content": [{"type": "text", "text": holdings}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"❌ Error fetching portfolio: {str(e)}"}]}

@mcp.tool()
def health_check() -> dict:
    try:
        status = auth_manager.get_token_status()
        health_status = {
            "server": "✅ MCP Server Running",
            "authentication": f"{'✅' if status['status'] == 'valid' else '❌'} {status['message']}",
            "timestamp": datetime.now().isoformat()
        }
        return {
            "content": [{"type": "text", "text": "\n".join(f"{k}: {v}" for k, v in health_status.items())}]
        }
    except Exception as e:
        return {"content": [{"type": "text", "text": f"❌ Health check failed: {str(e)}"}]}

if __name__ == "__main__":
    from fastmcp.web import serve_web
    print("🌐 Launching Zerodha MCP server on 0.0.0.0:7860 ...")
    serve_web(mcp, host="0.0.0.0", port=7860)
