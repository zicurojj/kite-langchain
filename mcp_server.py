#!/usr/bin/env python3
"""
MCP Server for Zerodha Kite Connect Trading - Droplet Deployment
Runs on droplet and serves MCP over Streamable HTTP for Claude Desktop
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from trading import place_order, get_positions
from auth_fully_automated import FullyAutomatedKiteAuth
from datetime import datetime
import asyncio
import json
import logging
import os
import requests
import uvicorn
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app for MCP server
app = FastAPI(title="Zerodha Kite MCP Server")

# Add CORS middleware for Claude Desktop
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize authentication manager
auth_manager = FullyAutomatedKiteAuth()

# Server configuration
MCP_SERVER_PORT = int(os.getenv('MCP_SERVER_PORT', '3000'))
CALLBACK_SERVER_PORT = int(os.getenv('CALLBACK_SERVER_PORT', '8080'))
DROPLET_CALLBACK_URL = os.getenv('DROPLET_CALLBACK_URL', f"https://zap.zicuro.shop:{CALLBACK_SERVER_PORT}")

# Session management
sessions = {}  # Store session data



def ensure_callback_server():
    """Ensure the callback server is running for OAuth handling"""
    try:
        # Try to ping the callback server
        response = requests.get(f"{DROPLET_CALLBACK_URL}/health", timeout=5)
        if response.status_code == 200:
            logger.info("✅ Callback server is running")
            return True
    except Exception:
        pass

    logger.warning("⚠️ Callback server not accessible")
    logger.info("💡 Make sure callback_server.py is running on the droplet")
    return False

# MCP Tools Implementation
def get_kite_login_url() -> str:
    """Get Kite Connect login URL for authentication"""
    try:
        # Check if callback server is running
        callback_available = ensure_callback_server()

        if not callback_available:
            return (f"❌ **Authentication Server Not Available**\n\n"
                   f"The OAuth callback server is not running on the droplet.\n"
                   f"Please ensure the callback server is deployed and accessible at:\n"
                   f"{DROPLET_CALLBACK_URL}\n\n"
                   f"💡 Run: docker-compose up -d")

        # Use original redirect URL for client authentication (not localhost)
        logger.info("🔗 Generating Kite Connect login URL...")
        url = auth_manager.get_login_url(use_original_redirect=True)
        logger.info(f"🔗 Generated URL: {url}")

        # Validate the URL contains the correct redirect
        if "zap.zicuro.shop" not in url:
            logger.warning(f"⚠️ Generated URL doesn't contain droplet domain: {url}")
            logger.warning("⚠️ Check KITE_REDIRECT_URL environment variable")

        return (f"🔗 **Kite Connect Authentication Required**\n\n"
                f"Click this link to login with your Zerodha credentials:\n\n"
                f"**{url}**\n\n"
                f"📱 This will open in your browser (any device/OS)\n"
                f"🔐 After login, tokens will be automatically saved on the server\n"
                f"✅ You'll then be ready to place trades through Claude!\n\n"
                f"💡 The authentication is valid until the token expires.\n"
                f"🔄 Callback URL: https://zap.zicuro.shop/callback")

    except Exception as e:
        logger.error(f"Error generating login URL: {e}")
        return f"❌ Failed to get login URL: {e}"

def check_authentication_status() -> str:
    """Check current authentication status"""
    try:
        status = auth_manager.get_token_status()

        if status["status"] == "valid":
            # Try to get user profile to confirm token works
            try:
                tokens = auth_manager.config.load_tokens()
                auth_manager.kc.set_access_token(tokens['access_token'])
                profile = auth_manager.kc.profile()
                user_name = profile.get('user_name', 'Unknown')
                if isinstance(user_name, dict):
                    user_name = user_name.get('name', 'Unknown')

                return (f"✅ **Authentication Status: ACTIVE**\n\n"
                       f"👤 User: {user_name}\n"
                       f"📅 Token Generated: {tokens.get('generated_at', 'Unknown')}\n"
                       f"🎯 Ready for trading operations!")

            except Exception:
                return (f"⚠️ **Authentication Status: TOKEN EXISTS BUT INVALID**\n\n"
                       f"The stored token appears to be expired or invalid.\n"
                       f"Please use get_kite_login_url() to re-authenticate.")
        else:
            return (f"❌ **Authentication Status: NOT AUTHENTICATED**\n\n"
                   f"No valid authentication token found.\n"
                   f"Use get_kite_login_url() to authenticate before trading.")

    except Exception as e:
        logger.error(f"Error checking auth status: {e}")
        return f"❌ Error checking authentication status: {e}"

def buy_stock(stock: str, qty: int) -> str:
    """Buy shares of a stock"""
    try:
        # Check authentication first
        auth_status = auth_manager.get_token_status()
        if auth_status["status"] != "valid":
            return (f"❌ **Authentication Required**\n\n"
                   f"Please authenticate first using get_kite_login_url()\n"
                   f"Current status: {auth_status['message']}")

        # Validate inputs
        if not stock or not isinstance(stock, str):
            return "❌ Invalid stock symbol. Please provide a valid trading symbol."

        if not isinstance(qty, int) or qty <= 0:
            return "❌ Invalid quantity. Please provide a positive integer."

        # Place the order
        result = place_order(stock.upper().strip(), qty, "BUY")

        if result and result.get("status") == "success":
            return f"✅ **BUY Order Successful!**\n\n{result.get('message', 'Order placed successfully')}"
        elif result and result.get("status") == "validation_error":
            return f"❌ **Validation Error**\n\n{result.get('message', 'Invalid order parameters')}"
        else:
            return f"❌ **Order Failed**\n\n{result.get('message', 'Unknown error occurred')}"

    except Exception as e:
        logger.error(f"Buy order error: {e}")
        if "token" in str(e).lower() or "auth" in str(e).lower():
            return (f"❌ **Authentication Expired**\n\n"
                   f"Your session has expired. Please use get_kite_login_url() to re-authenticate.")
        return f"❌ Buy order failed: {e}"

def sell_stock(stock: str, qty: int) -> str:
    """Sell shares of a stock

    Args:
        stock: Trading symbol (e.g., 'RELIANCE', 'TCS')
        qty: Number of shares to sell
    """
    try:
        # Check authentication first
        auth_status = auth_manager.get_token_status()
        if auth_status["status"] != "valid":
            return (f"❌ **Authentication Required**\n\n"
                   f"Please authenticate first using get_kite_login_url()\n"
                   f"Current status: {auth_status['message']}")

        # Validate inputs
        if not stock or not isinstance(stock, str):
            return "❌ Invalid stock symbol. Please provide a valid trading symbol."

        if not isinstance(qty, int) or qty <= 0:
            return "❌ Invalid quantity. Please provide a positive integer."

        # Place the order
        result = place_order(stock.upper().strip(), qty, "SELL")

        if result and result.get("status") == "success":
            return f"✅ **SELL Order Successful!**\n\n{result.get('message', 'Order placed successfully')}"
        elif result and result.get("status") == "validation_error":
            return f"❌ **Validation Error**\n\n{result.get('message', 'Invalid order parameters')}"
        else:
            return f"❌ **Order Failed**\n\n{result.get('message', 'Unknown error occurred')}"

    except Exception as e:
        logger.error(f"Sell order error: {e}")
        if "token" in str(e).lower() or "auth" in str(e).lower():
            return (f"❌ **Authentication Expired**\n\n"
                   f"Your session has expired. Please use get_kite_login_url() to re-authenticate.")
        return f"❌ Sell order failed: {e}"

def show_portfolio() -> str:
    """Show current portfolio positions and holdings"""
    try:
        return get_positions()
    except Exception as e:
        return f"❌ Error fetching portfolio: {e}"

def server_health_check() -> str:
    """Check server health and authentication status"""
    try:
        status = auth_manager.get_token_status()
        return (f"✅ **Server Status: HEALTHY**\n\n"
                f"🔐 Authentication: {status['status'].upper()}\n"
                f"📝 Details: {status['message']}\n"
                f"🕐 Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        return f"❌ Server health check failed: {e}"

# Tool registry for MCP
TOOLS = {
    "get_kite_login_url": {
        "function": get_kite_login_url,
        "description": "Get Kite Connect login URL for authentication",
        "parameters": {}
    },
    "check_authentication_status": {
        "function": check_authentication_status,
        "description": "Check current authentication status",
        "parameters": {}
    },
    "buy_stock": {
        "function": buy_stock,
        "description": "Buy shares of a stock",
        "parameters": {
            "stock": {"type": "string", "description": "Trading symbol (e.g., 'RELIANCE', 'TCS')"},
            "qty": {"type": "integer", "description": "Number of shares to buy"}
        }
    },
    "sell_stock": {
        "function": sell_stock,
        "description": "Sell shares of a stock",
        "parameters": {
            "stock": {"type": "string", "description": "Trading symbol (e.g., 'RELIANCE', 'TCS')"},
            "qty": {"type": "integer", "description": "Number of shares to sell"}
        }
    },
    "show_portfolio": {
        "function": show_portfolio,
        "description": "Show current portfolio positions and holdings",
        "parameters": {}
    },
    "server_health_check": {
        "function": server_health_check,
        "description": "Check server health and authentication status",
        "parameters": {}
    }
}

# FastAPI endpoints for MCP protocol
@app.get("/")
def root():
    """Root endpoint"""
    return {"name": "Zerodha Kite MCP Server", "version": "1.0.0"}

@app.get("/health")
def health():
    """Health check endpoint"""
    try:
        status = auth_manager.get_token_status()
        return {
            "status": "healthy",
            "server": "mcp",
            "port": MCP_SERVER_PORT,
            "auth_status": status["status"],
            "callback_server": DROPLET_CALLBACK_URL
        }
    except Exception as e:
        return {"status": "healthy", "server": "mcp", "port": MCP_SERVER_PORT, "error": str(e)}

# Session management for Streamable HTTP
sessions = {}  # session_id -> session_data
pending_sse_streams = {}  # session_id -> response_queue

@app.post("/mcp")
async def mcp_streamable_http_endpoint(request: Request):
    """Streamable HTTP endpoint for Claude Desktop MCP communication"""
    try:
        # Parse JSON-RPC request
        body = await request.body()
        json_request = json.loads(body.decode())

        # Get or create session
        session_id = request.headers.get("Mcp-Session-Id")
        if not session_id and json_request.get("method") == "initialize":
            session_id = str(uuid.uuid4())
            sessions[session_id] = {"initialized": False}

        logger.info(f"Received MCP request: {json_request.get('method')} (ID: {json_request.get('id')}) Session: {session_id}")

        # Process the request
        response = await process_mcp_request(json_request, session_id)

        # Check if client accepts SSE streaming
        accept_header = request.headers.get("Accept", "")
        supports_sse = "text/event-stream" in accept_header

        # For certain operations, we might want to stream responses
        should_stream = (
            json_request.get("method") in ["tools/call"] and
            supports_sse and
            json_request.get("params", {}).get("name") in ["show_portfolio", "check_authentication_status"]
        )

        if should_stream:
            # Return SSE stream for real-time updates
            return StreamingResponse(
                generate_sse_response(response, session_id),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "*",
                    "Mcp-Session-Id": session_id or "",
                }
            )
        else:
            # Return single JSON response
            json_response = JSONResponse(content=response)
            if session_id:
                json_response.headers["Mcp-Session-Id"] = session_id
            return json_response

    except Exception as e:
        logger.error(f"MCP Streamable HTTP error: {e}")
        error_response = {
            "jsonrpc": "2.0",
            "id": json_request.get("id") if 'json_request' in locals() else None,
            "error": {"code": -32603, "message": f"Server error: {str(e)}"}
        }
        return JSONResponse(content=error_response, status_code=500)

@app.get("/mcp")
async def mcp_sse_stream_endpoint(request: Request):
    """Optional SSE stream endpoint for server-initiated messages"""
    session_id = request.headers.get("Mcp-Session-Id")

    if not session_id:
        return JSONResponse(
            content={"error": "Session ID required for SSE stream"},
            status_code=400
        )

    logger.info(f"🔗 Starting SSE stream for session: {session_id}")

    return StreamingResponse(
        generate_server_events(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

async def generate_sse_response(response: dict, session_id: str):
    """Generate SSE stream for a single response"""
    try:
        # Send the main response
        yield f"data: {json.dumps(response)}\n\n"

        # For certain tool calls, we might send additional updates
        if (response.get("result", {}).get("content") and
            isinstance(response["result"]["content"], list) and
            len(response["result"]["content"]) > 0):

            # Send completion event
            completion_event = {
                "type": "completion",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            }
            yield f"event: completion\ndata: {json.dumps(completion_event)}\n\n"

    except Exception as e:
        logger.error(f"SSE response generation error: {e}")
        error_event = {
            "type": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        yield f"event: error\ndata: {json.dumps(error_event)}\n\n"

async def generate_server_events(session_id: str):
    """Generate server-initiated SSE events"""
    try:
        # Send connection confirmation
        connection_event = {
            "type": "connection",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        yield f"event: connection\ndata: {json.dumps(connection_event)}\n\n"

        # Keep connection alive and send periodic updates
        while True:
            try:
                # Check for any pending events for this session
                if session_id in pending_sse_streams:
                    queue = pending_sse_streams[session_id]
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=30.0)
                        yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
                    except asyncio.TimeoutError:
                        # Send keepalive
                        keepalive_event = {
                            "type": "keepalive",
                            "timestamp": datetime.now().isoformat()
                        }
                        yield f"event: keepalive\ndata: {json.dumps(keepalive_event)}\n\n"
                else:
                    # No queue for this session, just send keepalive
                    await asyncio.sleep(30)
                    keepalive_event = {
                        "type": "keepalive",
                        "timestamp": datetime.now().isoformat()
                    }
                    yield f"event: keepalive\ndata: {json.dumps(keepalive_event)}\n\n"

            except asyncio.CancelledError:
                logger.info(f"🔌 SSE stream cancelled for session: {session_id}")
                break

    except Exception as e:
        logger.error(f"❌ SSE server events error for session {session_id}: {e}")
        error_event = {
            "type": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        yield f"event: error\ndata: {json.dumps(error_event)}\n\n"
    finally:
        # Cleanup
        if session_id in pending_sse_streams:
            del pending_sse_streams[session_id]

@app.delete("/mcp")
async def mcp_session_cleanup(request: Request):
    """Handle session termination as per MCP Streamable HTTP specification"""
    session_id = request.headers.get("Mcp-Session-Id")

    if not session_id:
        return JSONResponse(
            content={"error": "Session ID required for cleanup"},
            status_code=400
        )

    # Cleanup session data
    if session_id in sessions:
        del sessions[session_id]
        logger.info(f"🗑️ Cleaned up session: {session_id}")

    if session_id in pending_sse_streams:
        del pending_sse_streams[session_id]
        logger.info(f"🗑️ Cleaned up SSE stream for session: {session_id}")

    return JSONResponse(content={"status": "session_terminated", "session_id": session_id})



async def process_mcp_request(json_request: dict, session_id: str) -> dict:
    """Process MCP request and return response"""
    try:
        method = json_request.get("method")
        request_id = json_request.get("id")
        params = json_request.get("params", {})

        if method == "initialize":
            # Handle initialization
            sessions[session_id] = {"initialized": True}

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "zerodha-kite-trading",
                        "version": "1.0.0"
                    }
                }
            }

        elif method == "tools/list":
            # Return available tools
            tools = []
            for name, info in TOOLS.items():
                tools.append({
                    "name": name,
                    "description": info["description"],
                    "inputSchema": {
                        "type": "object",
                        "properties": info["parameters"],
                        "required": list(info["parameters"].keys()) if info["parameters"] else []
                    }
                })

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": tools}
            }

        elif method == "tools/call":
            # Execute tool call
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if not tool_name or tool_name not in TOOLS:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"}
                }

            # Execute the tool
            tool_func = TOOLS[tool_name]["function"]
            try:
                if arguments:
                    result = tool_func(**arguments)
                else:
                    result = tool_func()

                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": str(result)}]
                    }
                }
            except Exception as e:
                logger.error(f"Tool execution error: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32603, "message": f"Tool execution failed: {str(e)}"}
                }

        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method '{method}' not supported"}
            }

    except Exception as e:
        logger.error(f"MCP processing error: {e}")
        return {
            "jsonrpc": "2.0",
            "id": json_request.get("id"),
            "error": {"code": -32603, "message": f"Internal server error: {str(e)}"}
        }

if __name__ == "__main__":
    logger.info("🚀 Starting Zerodha Kite MCP Server with Streamable HTTP support...")
    logger.info(f"🌐 MCP Server will run on port {MCP_SERVER_PORT}")
    logger.info(f"🔗 Claude Desktop Streamable HTTP endpoint: https://zap.zicuro.shop:{MCP_SERVER_PORT}/mcp")
    logger.info(f"📡 Authentication stays HTTP - Callback server on port {CALLBACK_SERVER_PORT}")
    logger.info(f"🎯 Transport: Streamable HTTP (HTTP POST + Optional SSE streaming)")

    # Run the FastAPI server
    uvicorn.run(app, host="0.0.0.0", port=MCP_SERVER_PORT)
