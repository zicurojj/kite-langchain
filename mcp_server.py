#!/usr/bin/env python3
"""
MCP Server for Zerodha Kite Connect Trading - Enhanced with LangChain Integration
KEEPS all existing functionality while adding AI capabilities
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from trading import place_order, get_positions
from auth_fully_automated import FullyAutomatedKiteAuth
from datetime import datetime
import json
import logging
import os
import requests
import uvicorn

# LangChain imports (new)
try:
    from langchain.tools import BaseTool
    from langchain.agents import AgentExecutor, create_openai_functions_agent
    from langchain.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI
    from langchain.memory import ConversationBufferWindowMemory
    from pydantic import BaseModel, Field
    import yfinance as yf
    import pandas as pd
    LANGCHAIN_AVAILABLE = True
    logging.info("✅ LangChain integration available")
except ImportError as e:
    LANGCHAIN_AVAILABLE = False
    logging.warning(f"⚠️ LangChain not available: {e}")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app for MCP server
app = FastAPI(title="Enhanced Zerodha Kite MCP Server with LangChain")

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

# ============================================================================
# EXISTING MCP TOOLS (UNCHANGED - Keep exact same functions)
# ============================================================================

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
    """Sell shares of a stock"""
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

# Tool registry for MCP (UNCHANGED)
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

# ============================================================================
# NEW: LANGCHAIN INTEGRATION
# ============================================================================

# LangChain Tools that use your existing functions
if LANGCHAIN_AVAILABLE:
    
    class StockInput(BaseModel):
        stock: str = Field(description="Trading symbol (e.g., 'RELIANCE', 'TCS')")
        qty: int = Field(description="Number of shares")
    
    class ChatInput(BaseModel):
        message: str = Field(description="Natural language trading command")
    
    class AnalysisInput(BaseModel):
        symbol: str = Field(description="Stock symbol to analyze")
    
    class KiteBuyTool(BaseTool):
        """LangChain tool that uses your existing buy_stock function"""
        name = "kite_buy_stock"
        description = "Buy shares using Kite Connect"
        args_schema = StockInput
        
        def _run(self, stock: str, qty: int) -> str:
            return buy_stock(stock, qty)
    
    class KiteSellTool(BaseTool):
        """LangChain tool that uses your existing sell_stock function"""
        name = "kite_sell_stock"
        description = "Sell shares using Kite Connect"
        args_schema = StockInput
        
        def _run(self, stock: str, qty: int) -> str:
            return sell_stock(stock, qty)
    
    class KitePortfolioTool(BaseTool):
        """LangChain tool that uses your existing show_portfolio function"""
        name = "kite_show_portfolio"
        description = "Show current portfolio positions"
        
        def _run(self) -> str:
            return show_portfolio()
    
    class KiteAuthTool(BaseTool):
        """LangChain tool that uses your existing auth check function"""
        name = "kite_check_auth"
        description = "Check Kite Connect authentication status"
        
        def _run(self) -> str:
            return check_authentication_status()
    
    class MarketAnalysisTool(BaseTool):
        """Market analysis tool using Yahoo Finance"""
        name = "analyze_stock"
        description = "Analyze stock with real-time market data and technical indicators"
        args_schema = AnalysisInput
        
        def _run(self, symbol: str) -> str:
            try:
                # Add .NS for NSE stocks
                ticker_symbol = f"{symbol}.NS" if not symbol.endswith('.NS') else symbol
                ticker = yf.Ticker(ticker_symbol)
                
                # Get data
                hist = ticker.history(period="1mo")
                info = ticker.info
                
                if hist.empty:
                    return f"❌ No data found for {symbol}"
                
                current_price = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
                change = current_price - prev_close
                change_pct = (change / prev_close) * 100
                
                # Technical indicators
                volume_avg = hist['Volume'].mean()
                current_volume = hist['Volume'].iloc[-1]
                high_52w = hist['High'].max()
                low_52w = hist['Low'].min()
                
                analysis = f"""📊 **Market Analysis for {symbol}**

**Current Price:** ₹{current_price:.2f}
**Change:** ₹{change:+.2f} ({change_pct:+.2f}%)
**Volume:** {current_volume:,.0f} (Avg: {volume_avg:,.0f})
**52W Range:** ₹{low_52w:.2f} - ₹{high_52w:.2f}

**Trading Recommendation:**"""
                
                # Simple trading logic
                if change_pct > 2 and current_volume > volume_avg * 1.2:
                    analysis += "\n🚀 **STRONG BUY** - Strong momentum with volume support"
                elif change_pct > 0.5:
                    analysis += "\n✅ **BUY** - Positive trend"
                elif change_pct < -2:
                    analysis += "\n⚠️ **SELL** - Heavy selling pressure"
                else:
                    analysis += "\n⏳ **HOLD** - Wait for clearer signals"
                
                return analysis
                
            except Exception as e:
                return f"❌ Error analyzing {symbol}: {e}"
    
    # Initialize LangChain agent
    smart_agent = None
    if os.getenv('OPENAI_API_KEY'):
        try:
            # Create tools using your existing functions
            langchain_tools = [
                KiteBuyTool(),
                KiteSellTool(), 
                KitePortfolioTool(),
                KiteAuthTool(),
                MarketAnalysisTool()
            ]
            
            # Initialize LLM
            llm = ChatOpenAI(model="gpt-4", temperature=0.1)
            
            # Create prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert Indian stock market trading assistant using Zerodha Kite Connect.

You have access to:
- Real-time trading through Kite Connect
- Live market data analysis
- Portfolio management functions
- Authentication management

Guidelines:
- Always check authentication before trading
- Analyze market data before suggesting trades
- Use Indian stock symbols (RELIANCE, TCS, INFY, etc.)
- Provide clear reasoning for trade recommendations
- Consider risk management in all suggestions

Be professional and prioritize user's financial safety."""),
                ("user", "{input}")
            ])
            
            # Create agent
            agent = create_openai_functions_agent(llm, langchain_tools, prompt)
            smart_agent = AgentExecutor(agent=agent, tools=langchain_tools, verbose=True)
            
            logger.info("✅ LangChain Smart Agent initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize LangChain agent: {e}")
            smart_agent = None
    else:
        logger.warning("⚠️ OPENAI_API_KEY not set - Smart Agent unavailable")

# ============================================================================
# EXISTING FASTAPI ENDPOINTS (UNCHANGED)
# ============================================================================

@app.get("/")
def root():
    """Root endpoint"""
    return {
        "name": "Enhanced Zerodha Kite MCP Server", 
        "version": "2.0.0",
        "mcp_enabled": True,
        "langchain_enabled": LANGCHAIN_AVAILABLE,
        "smart_agent_ready": smart_agent is not None
    }

@app.get("/health")
def health():
    """Health check endpoint"""
    try:
        status = auth_manager.get_token_status()
        return {
            "status": "healthy",
            "server": "enhanced_mcp",
            "port": MCP_SERVER_PORT,
            "auth_status": status["status"],
            "callback_server": DROPLET_CALLBACK_URL,
            "langchain_available": LANGCHAIN_AVAILABLE,
            "smart_agent_ready": smart_agent is not None
        }
    except Exception as e:
        return {"status": "healthy", "server": "enhanced_mcp", "port": MCP_SERVER_PORT, "error": str(e)}

async def process_mcp_request(json_request: dict, session_id: str = None) -> dict:
    """Process MCP request and return response - UNCHANGED"""
    try:
        method = json_request.get("method")
        request_id = json_request.get("id")
        params = json_request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "zerodha-kite-trading",
                        "version": "2.0.0"
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

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """MCP endpoint for Claude Desktop - UNCHANGED"""
    try:
        body = await request.body()
        json_request = json.loads(body.decode())

        logger.info(f"Received MCP request: {json_request.get('method')} (ID: {json_request.get('id')})")

        response = await process_mcp_request(json_request, session_id=None)

        return JSONResponse(content=response)

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"}
            },
            status_code=400
        )
    except Exception as e:
        logger.error(f"MCP endpoint error: {e}")
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": json_request.get("id") if 'json_request' in locals() else None,
                "error": {"code": -32603, "message": f"Server error: {str(e)}"}
            },
            status_code=500
        )

# ============================================================================
# NEW: LANGCHAIN ENDPOINTS
# ============================================================================

if LANGCHAIN_AVAILABLE:
    
    @app.post("/ai-chat")
    async def ai_chat(request: Request):
        """Natural language trading interface using LangChain"""
        if not smart_agent:
            return JSONResponse(
                content={"error": "Smart agent not available. Please set OPENAI_API_KEY."},
                status_code=503
            )
        
        try:
            body = await request.body()
            data = json.loads(body.decode())
            message = data.get("message", "")
            
            if not message:
                return JSONResponse(
                    content={"error": "Message is required"},
                    status_code=400
                )
            
            logger.info(f"AI Chat: {message}")
            
            # Execute through smart agent
            result = smart_agent.invoke({"input": message})
            
            return JSONResponse(content={
                "status": "success",
                "response": result["output"],
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"AI Chat error: {e}")
            return JSONResponse(
                content={"error": f"AI Chat failed: {e}"},
                status_code=500
            )
    
    @app.post("/ai-analyze")
    async def ai_analyze(request: Request):
        """Stock analysis with AI insights"""
        try:
            body = await request.body()
            data = json.loads(body.decode())
            symbol = data.get("symbol", "")
            
            if not symbol:
                return JSONResponse(
                    content={"error": "Symbol is required"},
                    status_code=400
                )
            
            logger.info(f"AI Analyze: {symbol}")
            
            # Use market analysis tool directly
            analysis_tool = MarketAnalysisTool()
            result = analysis_tool._run(symbol)
            
            return JSONResponse(content={
                "status": "success",
                "symbol": symbol,
                "analysis": result,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"AI Analyze error: {e}")
            return JSONResponse(
                content={"error": f"Analysis failed: {e}"},
                status_code=500
            )
    
    @app.post("/ai-trade")
    async def ai_trade(request: Request):
        """Intelligent trading with confirmation"""
        if not smart_agent:
            return JSONResponse(
                content={"error": "Smart agent not available. Please set OPENAI_API_KEY."},
                status_code=503
            )
        
        try:
            body = await request.body()
            data = json.loads(body.decode())
            command = data.get("command", "")
            confirm = data.get("confirm", False)
            
            if not command:
                return JSONResponse(
                    content={"error": "Command is required"},
                    status_code=400
                )
            
            # Add safety check for large trades
            if not confirm and any(word in command.lower() for word in ['buy', 'sell']):
                return JSONResponse(content={
                    "status": "confirmation_required",
                    "message": "Trade command requires confirmation. Set 'confirm': true",
                    "command": command
                })
            
            logger.info(f"AI Trade: {command}")
            
            # Execute through smart agent
            result = smart_agent.invoke({"input": command})
            
            return JSONResponse(content={
                "status": "success",
                "command": command,
                "result": result["output"],
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"AI Trade error: {e}")
            return JSONResponse(
                content={"error": f"Trade failed: {e}"},
                status_code=500
            )

if __name__ == "__main__":
    logger.info("🚀 Starting Enhanced Zerodha Kite MCP Server with LangChain...")
    logger.info(f"🌐 MCP Server will run on port {MCP_SERVER_PORT}")
    logger.info(f"🔗 Claude Desktop URL: https://zap.zicuro.shop:{MCP_SERVER_PORT}/mcp")
    
    if LANGCHAIN_AVAILABLE and smart_agent:
        logger.info(f"🤖 AI Chat URL: https://zap.zicuro.shop:{MCP_SERVER_PORT}/ai-chat")
        logger.info(f"📊 AI Analysis URL: https://zap.zicuro.shop:{MCP_SERVER_PORT}/ai-analyze")
        logger.info(f"⚡ AI Trade URL: https://zap.zicuro.shop:{MCP_SERVER_PORT}/ai-trade")
    else:
        logger.info("⚠️ LangChain features unavailable - set OPENAI_API_KEY to enable")

    uvicorn.run(app, host="0.0.0.0", port=MCP_SERVER_PORT)