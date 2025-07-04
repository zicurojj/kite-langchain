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
from typing import Type, Optional


# LangChain imports (new)
# Replace the LangChain imports section in mcp_server.py (around line 18)

# LangChain imports (FIXED)
try:
    from langchain_core.tools import BaseTool
    from langchain.agents import AgentExecutor, create_tool_calling_agent  # Updated function name
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI
    from pydantic import BaseModel, Field
    import yfinance as yf
    import pandas as pd
    LANGCHAIN_AVAILABLE = True
    logging.info("✅ LangChain integration available")
except ImportError as e:
    LANGCHAIN_AVAILABLE = False
    logging.warning(f"⚠️ LangChain not available: {e}")
    logging.warning(f"⚠️ Install: pip install langchain langchain-openai langchain-core yfinance pandas")

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
    """Check current authentication status and auto-provide login URL if needed"""
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
                # Token exists but invalid - auto-provide login URL
                return get_smart_auth_response("TOKEN EXISTS BUT INVALID")
        else:
            # No valid token - auto-provide login URL
            return get_smart_auth_response("NOT AUTHENTICATED")

    except Exception as e:
        logger.error(f"Error checking auth status: {e}")
        return f"❌ Error checking authentication status: {e}"

def get_smart_auth_response(status_reason: str) -> str:
    """Smart authentication response that automatically provides login URL"""
    try:
        # Ensure callback server is running
        callback_available = ensure_callback_server()
        
        if not callback_available:
            return (f"❌ **Authentication Server Not Available**\n\n"
                   f"The OAuth callback server is not running on the droplet.\n"
                   f"Please ensure the callback server is deployed and accessible.\n"
                   f"💡 Run: docker-compose up -d")

        # Get the login URL automatically
        login_url = auth_manager.get_login_url(use_original_redirect=True)
        
        return (f"❌ **Authentication Status: {status_reason}**\n\n"
                f"🔐 **Click this link to authenticate:**\n"
                f"**{login_url}**\n\n"
                f"📱 This will open in your browser (any device/OS)\n"
                f"🔐 After login, tokens will be automatically saved\n"
                f"✅ You'll then be ready to place trades!\n\n"
                f"💡 Authentication is valid until token expires\n"
                f"🔄 Callback URL: https://zap.zicuro.shop/callback")
                
    except Exception as e:
        logger.error(f"Error generating smart auth response: {e}")
        return f"❌ Failed to generate authentication URL: {e}"

def buy_stock(stock: str, qty: int) -> str:
    """Buy shares with smart authentication handling"""
    try:
        # Check authentication first with smart response
        auth_status = auth_manager.get_token_status()
        if auth_status["status"] != "valid":
            return get_smart_auth_response("AUTHENTICATION REQUIRED FOR TRADING")

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
            return get_smart_auth_response("AUTHENTICATION EXPIRED")
        return f"❌ Buy order failed: {e}"

def sell_stock(stock: str, qty: int) -> str:
    """Sell shares with smart authentication handling"""
    try:
        # Check authentication first with smart response  
        auth_status = auth_manager.get_token_status()
        if auth_status["status"] != "valid":
            return get_smart_auth_response("AUTHENTICATION REQUIRED FOR TRADING")

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
            return get_smart_auth_response("AUTHENTICATION EXPIRED")
        return f"❌ Sell order failed: {e}"

def show_portfolio() -> str:
    """Show portfolio with smart authentication handling"""
    try:
        # Check authentication first with smart response
        auth_status = auth_manager.get_token_status()
        if auth_status["status"] != "valid":
            return get_smart_auth_response("AUTHENTICATION REQUIRED FOR PORTFOLIO")
            
        return get_positions()
    except Exception as e:
        if "token" in str(e).lower() or "auth" in str(e).lower():
            return get_smart_auth_response("AUTHENTICATION EXPIRED")
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

# Define AI functions conditionally
if LANGCHAIN_AVAILABLE:
    def ai_market_analysis(symbol: str) -> str:
        """AI-powered market analysis using LangChain"""
        try:
            analysis_tool = MarketAnalysisTool()  # ✅ Now safe!
            result = analysis_tool._run(symbol)
            return result
        except Exception as e:
            return f"❌ Analysis failed: {e}"

    def ai_trading_assistant(message: str) -> str:
        """Natural language trading assistant using LangChain"""
        agent = initialize_smart_agent()  # ✅ Now safe!
        if not agent:
            return "❌ Smart agent not available. Please set OPENAI_API_KEY."
        
        try:
            result = agent.invoke({"input": message})
            return result["output"]
        except Exception as e:
            return f"❌ AI Assistant failed: {e}"

    def ai_stock_recommendation(symbol: str, action: str = "analyze") -> str:
        """Get AI-powered stock recommendations"""
        agent = initialize_smart_agent()  # ✅ Now safe!
        if not agent:
            return "❌ Smart agent not available. Please set OPENAI_API_KEY."
        
        try:
            query = f"Analyze {symbol} and provide {action} recommendation with reasoning"
            result = agent.invoke({"input": query})
            return result["output"]
        except Exception as e:
            return f"❌ Recommendation failed: {e}"

else:
    # Fallback functions when LangChain not available
    def ai_market_analysis(symbol: str) -> str:
        return "❌ LangChain not available. Please install dependencies."

    def ai_trading_assistant(message: str) -> str:
        return "❌ LangChain not available. Please install dependencies."

    def ai_stock_recommendation(symbol: str, action: str = "analyze") -> str:
        return "❌ LangChain not available. Please install dependencies."

# Base tools (always available)
BASE_TOOLS = {
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

# AI tools (only if LangChain available)
if LANGCHAIN_AVAILABLE:
    AI_TOOLS = {
        "ai_market_analysis": {
            "function": ai_market_analysis,
            "description": "AI-powered market analysis with technical indicators and recommendations",
            "parameters": {
                "symbol": {"type": "string", "description": "Stock symbol to analyze"}
            }
        },
        "ai_trading_assistant": {
            "function": ai_trading_assistant,
            "description": "Natural language trading assistant",
            "parameters": {
                "message": {"type": "string", "description": "Your trading question"}
            }
        },
        "ai_stock_recommendation": {
            "function": ai_stock_recommendation,
            "description": "Get AI-powered stock recommendations",
            "parameters": {
                "symbol": {"type": "string", "description": "Stock symbol"},
                "action": {"type": "string", "description": "buy, sell, hold, or analyze"}
            }
        }
    }
    
    # Combine base tools with AI tools
    TOOLS = {**BASE_TOOLS, **AI_TOOLS}
else:
    # Only base tools when LangChain not available
    TOOLS = BASE_TOOLS

# ============================================================================
# NEW: LANGCHAIN INTEGRATION (Fixed to match your original auth pattern)
# ============================================================================

# LangChain Tools that use your existing functions
# Add this import at the top of your mcp_server.py file (around line 18):
from typing import Type, Optional

# Then replace your LangChain tool classes (starting around line 290) with these:

# Replace the LangChain tool classes in mcp_server.py

if LANGCHAIN_AVAILABLE:
    
    class StockInput(BaseModel):
        stock: str = Field(description="Trading symbol (e.g., 'RELIANCE', 'TCS')")
        qty: int = Field(description="Number of shares")
    
    class AnalysisInput(BaseModel):
        symbol: str = Field(description="Stock symbol to analyze")
    
    class KiteAuthTool(BaseTool):
        """Smart authentication tool that always provides login URL when needed"""
        name: str = "kite_check_auth"
        description: str = "Check authentication status and automatically provide login URL if needed"
            
        def _run(self) -> str:
            return check_authentication_status()  # Now uses smart auth
        
    class KiteBuyTool(BaseTool):
        """Smart buy tool with automatic authentication handling"""
        name: str = "kite_buy_stock"
        description: str = "Buy shares - automatically handles authentication and provides login URL if needed"
        args_schema: Type[BaseModel] = StockInput
            
        def _run(self, stock: str, qty: int) -> str:
            return buy_stock(stock, qty)  # Now uses smart auth
        
    class KiteSellTool(BaseTool):
        """Smart sell tool with automatic authentication handling"""
        name: str = "kite_sell_stock"
        description: str = "Sell shares - automatically handles authentication and provides login URL if needed"
        args_schema: Type[BaseModel] = StockInput
            
        def _run(self, stock: str, qty: int) -> str:
            return sell_stock(stock, qty)  # Now uses smart auth
        
    class KitePortfolioTool(BaseTool):
        """Smart portfolio tool with automatic authentication handling"""
        name: str = "kite_show_portfolio"
        description: str = "Show portfolio - automatically handles authentication and provides login URL if needed"
            
        def _run(self) -> str:
            return show_portfolio()  # Now uses smart auth
        
    class MarketAnalysisTool(BaseTool):
        """Market analysis tool using Yahoo Finance"""
        name: str = "analyze_stock"
        description: str = "Analyze stock with real-time market data and technical indicators"
        args_schema: Type[BaseModel] = AnalysisInput
            
        def _run(self, symbol: str) -> str:
            """Execute the tool"""
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
smart_agent = None

def initialize_smart_agent():
    """Initialize smart agent only when first needed - with robust error handling"""
    global smart_agent
    
    if smart_agent is not None:
        return smart_agent
        
    if not LANGCHAIN_AVAILABLE:
        logger.warning("⚠️ LangChain not available")
        return None
        
    openai_key = os.getenv('OPENAI_API_KEY')
    if not openai_key:
        logger.warning("⚠️ OPENAI_API_KEY not set - AI features disabled")
        return None
    
    try:
        logger.info("🤖 Initializing LangChain agent...")
        
        # Import only when needed to avoid startup crashes
        from langchain_core.tools import BaseTool
        from langchain.agents import AgentExecutor, create_tool_calling_agent
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI
        
        # Create tools using your existing functions  
        langchain_tools = [
            KiteBuyTool(),
            KiteSellTool(), 
            KitePortfolioTool(),
            KiteAuthTool(),
            MarketAnalysisTool()
        ]
        
        # Initialize LLM
        llm = ChatOpenAI(
            model="gpt-4", 
            temperature=0.1,
            openai_api_key=openai_key,
            timeout=30  # Add timeout to prevent hanging
        )
        
        # Create prompt
        prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an expert Indian stock market trading assistant using Zerodha Kite Connect.

IMPORTANT: You have intelligent authentication handling. When any trading operation requires authentication:
- The system automatically provides the login URL in the response
- You should present this URL clearly to the user
- No need to call separate authentication functions first

Your tools automatically handle authentication and provide login URLs when needed.

Guidelines:
- Always attempt trading operations directly - authentication is handled automatically
- When you receive a login URL in any response, present it clearly to the user
- Analyze market data before suggesting trades using the market analysis tool
- Use Indian stock symbols (RELIANCE, TCS, INFY, etc.)
- Provide clear reasoning for trade recommendations
- Consider risk management in all suggestions

Be intelligent and user-friendly - don't make users jump through multiple steps."""),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}")
])
        
        # Create agent
        agent = create_tool_calling_agent(llm, langchain_tools, prompt)
        smart_agent = AgentExecutor(
            agent=agent, 
            tools=langchain_tools, 
            verbose=False,  # Reduce noise in logs
            handle_parsing_errors=True,
            max_iterations=5,  # Prevent infinite loops
            max_execution_time=60  # Add execution timeout
        )
        
        logger.info("✅ LangChain Smart Agent initialized successfully")
        return smart_agent
        
    except Exception as e:
        logger.error(f"❌ LangChain agent initialization failed: {e}")
        # Don't crash the server - just disable AI features
        smart_agent = None
        return None
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

# REPLACE the /health endpoint in mcp_server.py with this robust version:

@app.get("/health")
def health():
    """Health check endpoint - NEVER check auth during health check"""
    try:
        return {
            "status": "healthy",
            "server": "enhanced_mcp", 
            "port": MCP_SERVER_PORT,
            "callback_server": DROPLET_CALLBACK_URL,
            "langchain_available": LANGCHAIN_AVAILABLE,
            "openai_configured": bool(os.getenv('OPENAI_API_KEY')),
            "timestamp": datetime.now().isoformat(),
            "message": "MCP server is responding"
        }
    except Exception as e:
        # Even if there's an error, return 200 for health check
        return {
            "status": "healthy_with_warnings", 
            "server": "enhanced_mcp", 
            "port": MCP_SERVER_PORT, 
            "warning": str(e),
            "timestamp": datetime.now().isoformat(),
            "message": "Server responding despite warnings"
        }

# Replace the process_mcp_request function in your mcp_server.py with this fixed version:

async def process_mcp_request(json_request: dict, session_id: str = None) -> dict:
    """Process MCP request and return response - FIXED for JSON-RPC compliance"""
    # Ensure we always have a valid request ID
    request_id = json_request.get("id")
    if request_id is None:
        request_id = "unknown"  # Fallback for missing ID
    
    try:
        method = json_request.get("method")
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
            "id": request_id,  # Always use the request_id we set at the beginning
            "error": {"code": -32603, "message": f"Internal server error: {str(e)}"}
        }

# Also replace the mcp_endpoint function with this fixed version:

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """MCP endpoint for Claude Desktop - FIXED for JSON-RPC compliance"""
    json_request = None
    
    try:
        # Parse JSON-RPC request
        body = await request.body()
        json_request = json.loads(body.decode())

        # Validate that we have a proper JSON-RPC request
        if not isinstance(json_request, dict):
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error: Request must be a JSON object"}
                },
                status_code=400
            )

        # Ensure request has required fields
        if "method" not in json_request:
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": json_request.get("id", "unknown"),
                    "error": {"code": -32600, "message": "Invalid Request: Missing method field"}
                },
                status_code=400
            )

        logger.info(f"Received MCP request: {json_request.get('method')} (ID: {json_request.get('id')})")

        # Process the request
        response = await process_mcp_request(json_request, session_id=None)

        # Return JSON response
        return JSONResponse(content=response)

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error: Invalid JSON"}
            },
            status_code=400
        )
    except Exception as e:
        logger.error(f"MCP endpoint error: {e}")
        # Always ensure we have a valid ID in error responses
        error_id = "unknown"
        if json_request and isinstance(json_request, dict):
            error_id = json_request.get("id", "unknown")
        
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": error_id,
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
        # Initialize agent only when needed
        agent = initialize_smart_agent()
        if not agent:
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
            result = agent.invoke({"input": message})
            
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
        # Initialize agent only when needed
        agent = initialize_smart_agent()
        if not agent:
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
            result = agent.invoke({"input": command})
            
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
    try:
        logger.info("🚀 Starting Enhanced Zerodha Kite MCP Server...")
        logger.info(f"🌐 MCP Server will run on port {MCP_SERVER_PORT}")
        logger.info(f"🔗 Claude Desktop URL: https://zap.zicuro.shop:{MCP_SERVER_PORT}/mcp")
        
        # SAFE check for LangChain without trying to initialize agent
        if LANGCHAIN_AVAILABLE:
            openai_key = os.getenv('OPENAI_API_KEY')
            if openai_key:
                logger.info("✅ LangChain available with OpenAI API key")
                logger.info(f"🤖 AI Chat URL: https://zap.zicuro.shop:{MCP_SERVER_PORT}/ai-chat")
                logger.info(f"📊 AI Analysis URL: https://zap.zicuro.shop:{MCP_SERVER_PORT}/ai-analyze")
                logger.info(f"⚡ AI Trade URL: https://zap.zicuro.shop:{MCP_SERVER_PORT}/ai-trade")
            else:
                logger.info("⚠️ LangChain available but OPENAI_API_KEY not set")
        else:
            logger.info("⚠️ LangChain not available - basic trading only")

        logger.info("🔄 Starting server...")
        uvicorn.run(app, host="0.0.0.0", port=MCP_SERVER_PORT, access_log=False)
        
    except Exception as e:
        logger.error(f"❌ Failed to start MCP server: {e}")
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        sys.exit(1)