#!/usr/bin/env python3
"""
HTTP Callback Server for OAuth Token Exchange
Runs alongside the MCP server to handle Kite Connect OAuth callbacks
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from auth_fully_automated import FullyAutomatedKiteAuth
import uvicorn
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kite Connect OAuth Callback Server")
auth_manager = FullyAutomatedKiteAuth()

class TokenExchangeRequest(BaseModel):
    request_token: str

@app.get("/")
def root():
    """Root endpoint"""
    return {"message": "Kite Connect OAuth Callback Server", "status": "running"}

@app.get("/health")
def health():
    """Health check endpoint"""
    try:
        status = auth_manager.get_token_status()
        return {
            "server": "healthy",
            "auth_status": status["status"],
            "message": status["message"]
        }
    except Exception as e:
        return {"server": "healthy", "auth_status": "error", "message": str(e)}

@app.post("/auth/exchange")
def exchange_token(req: TokenExchangeRequest):
    """Exchange request token for access token via POST request"""
    logger.info(f"🔄 Received token exchange request")
    
    if not req.request_token:
        raise HTTPException(status_code=400, detail="No request_token provided")

    try:
        success = auth_manager.exchange_request_token(req.request_token)
        if success:
            logger.info("✅ Token exchange successful")
            return {"success": True, "message": "Access token generated and saved"}
        else:
            logger.error("❌ Token exchange failed")
            raise HTTPException(status_code=500, detail="Token exchange failed")
    except Exception as e:
        logger.error(f"❌ Token exchange error: {e}")
        raise HTTPException(status_code=500, detail=f"Token exchange error: {str(e)}")

@app.get("/callback", response_class=HTMLResponse)
def handle_callback(request_token: str = None):
    """Handle OAuth callback redirect from Kite Connect"""
    logger.info(f"🔗 Received OAuth callback")
    
    if not request_token:
        logger.error("❌ Missing request token in callback")
        return HTMLResponse(content="""
        <html>
        <head><title>Authentication Error</title></head>
        <body style="font-family: Arial; text-align: center; margin-top: 50px;">
            <h2>❌ Authentication Error</h2>
            <p>Missing request token in callback URL.</p>
            <p>Please try the authentication process again.</p>
        </body>
        </html>
        """, status_code=400)

    try:
        # Exchange token directly
        logger.info(f"🔄 Exchanging request token: {request_token[:10]}...")
        success = auth_manager.exchange_request_token(request_token)
        
        if success:
            logger.info("✅ OAuth callback successful - token exchanged and saved")
            return HTMLResponse(content="""
            <html>
            <head><title>Authentication Successful</title></head>
            <body style="font-family: Arial; text-align: center; margin-top: 50px;">
                <h2>✅ Authentication Successful!</h2>
                <p><strong>Your Kite Connect authentication is now complete.</strong></p>
                <p>🎉 Access token has been generated and saved on the server.</p>
                <p>💼 You can now use Claude Desktop to place trades.</p>
                <p>🔒 You can safely close this window.</p>
                <hr style="margin: 30px 0;">
                <p style="color: #666; font-size: 14px;">
                    Server: zap.zicuro.shop | Status: Ready for Trading
                </p>
            </body>
            </html>
            """)
        else:
            logger.error("❌ Token exchange failed during callback")
            return HTMLResponse(content="""
            <html>
            <head><title>Authentication Failed</title></head>
            <body style="font-family: Arial; text-align: center; margin-top: 50px;">
                <h2>❌ Authentication Failed</h2>
                <p>Token exchange failed during the authentication process.</p>
                <p>Please try again or contact support if the issue persists.</p>
                <button onclick="window.close()">Close Window</button>
            </body>
            </html>
            """, status_code=500)
            
    except Exception as e:
        logger.error(f"❌ Callback processing error: {e}")
        return HTMLResponse(content=f"""
        <html>
        <head><title>Authentication Error</title></head>
        <body style="font-family: Arial; text-align: center; margin-top: 50px;">
            <h2>❌ Authentication Error</h2>
            <p>An error occurred during authentication:</p>
            <p style="color: red; font-family: monospace;">{str(e)}</p>
            <p>Please try the authentication process again.</p>
        </body>
        </html>
        """, status_code=500)

if __name__ == "__main__":
    logger.info("🌐 Starting OAuth Callback Server on port 8080...")
    logger.info("🔗 Callback URL: https://zap.zicuro.shop/callback")
    uvicorn.run(app, host="0.0.0.0", port=8080)
