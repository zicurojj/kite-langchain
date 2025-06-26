#!/usr/bin/env python3
"""
Fully Automated Kite Connect Authentication
No manual token copying required - everything happens automatically
"""

import os
import json
import webbrowser
import threading
import socket
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
from kiteconnect import KiteConnect
from auth_utils import extract_profile_data
import logging

# Try to import python-dotenv for .env file support
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file if it exists
except ImportError:
    pass  # python-dotenv not installed, use system env vars only

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TokenExpiredException(Exception):
    """Exception raised when access token is expired or invalid"""
    pass

class AutoAuthConfig:
    """Configuration for fully automated Kite Connect authentication"""
    
    def __init__(self):
        self.config_file = "kite_auth_config.json"
        # Use data directory for Docker compatibility
        os.makedirs('data', exist_ok=True)
        self.tokens_file = os.path.join('data', 'kite_tokens.json')
        self.load_config()
    
    def load_config(self):
        """Load API credentials from environment variables or config file"""
        try:
            # Try environment variables first (more secure)
            self.api_key = os.getenv('KITE_API_KEY')
            self.api_secret = os.getenv('KITE_API_SECRET')
            self.original_redirect_url = os.getenv('KITE_REDIRECT_URL')

            # If environment variables not found, try config file
            if not all([self.api_key, self.api_secret]):
                if os.path.exists(self.config_file):
                    logger.info("Environment variables not found, loading from config file")
                    with open(self.config_file, 'r') as f:
                        config = json.load(f)
                        self.api_key = self.api_key or config.get('api_key')
                        self.api_secret = self.api_secret or config.get('api_secret')
                        self.original_redirect_url = self.original_redirect_url or config.get('redirect_url')
                else:
                    raise FileNotFoundError(
                        "Neither environment variables nor config file found. "
                        "Please set KITE_API_KEY, KITE_API_SECRET environment variables "
                        "or create kite_auth_config.json file"
                    )

            # Validate required credentials
            if not self.api_key or not self.api_secret:
                raise ValueError(
                    "Missing required credentials. Please set:\n"
                    "- KITE_API_KEY environment variable\n"
                    "- KITE_API_SECRET environment variable\n"
                    "- KITE_REDIRECT_URL environment variable (optional)"
                )

            # Use localhost for automated capture
            self.redirect_url = self.original_redirect_url or "http://localhost:8080/callback"

            logger.info("✅ Configuration loaded successfully")
            logger.info(f"📋 API Key: {self.api_key[:8]}...")
            logger.info(f"🔗 Original Redirect: {self.original_redirect_url}")

        except Exception as e:
            logger.error(f"❌ Error loading config: {e}")
            raise
    
    def save_tokens(self, access_token, refresh_token=None, expires_at=None):
        """Save tokens to file"""
        tokens = {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_at': expires_at,
            'generated_at': datetime.now().isoformat()
        }
        with open(self.tokens_file, 'w') as f:
            json.dump(tokens, f, indent=2)
        logger.info(f"Tokens saved to {self.tokens_file}")
    
    def load_tokens(self):
        """Load tokens from file"""
        try:
            if os.path.exists(self.tokens_file):
                with open(self.tokens_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading tokens: {e}")
        return None

class AutoAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for automated OAuth callback capture"""
    
    def __init__(self, auth_manager, *args, **kwargs):
        self.auth_manager = auth_manager
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET request for OAuth callback"""
        try:
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)

            # Security: Only accept callback path
            if parsed_url.path != '/callback':
                self.send_error_response("Invalid callback path")
                return

            # Extract and validate parameters
            request_token = query_params.get('request_token', [None])[0]
            action = query_params.get('action', [None])[0]
            status = query_params.get('status', [None])[0]

            # Validate required parameters
            if not request_token:
                self.send_error_response("Missing request token")
                return

            # Security: Validate request token format (basic check)
            if not request_token.isalnum() or len(request_token) < 10:
                self.send_error_response("Invalid request token format")
                return

            if action == 'login' and status == 'success':
                logger.info("✅ Automatically captured request token")

                # Exchange request token for access token
                success = self.auth_manager.exchange_request_token(request_token)

                if success:
                    self.send_success_response()
                else:
                    self.send_error_response("Failed to exchange request token")
            else:
                error_msg = f"Authentication failed. Status: {status}, Action: {action}"
                logger.error(error_msg)
                self.send_error_response(error_msg)

        except Exception as e:
            logger.error(f"Error handling callback: {e}")
            self.send_error_response("Internal server error")
    
    def send_success_response(self):
        """Send success response to browser"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Kite Connect - Authentication Successful</title>
            <style>
                body { 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                    text-align: center; 
                    margin-top: 50px; 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .container { 
                    max-width: 600px; 
                    margin: 0 auto; 
                    padding: 40px; 
                    background: rgba(255,255,255,0.1);
                    border-radius: 20px;
                    backdrop-filter: blur(10px);
                    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
                }
                .success { color: #4CAF50; font-size: 3em; margin-bottom: 20px; }
                h1 { margin-bottom: 30px; }
                p { font-size: 1.2em; line-height: 1.6; margin-bottom: 20px; }
                .highlight { background: rgba(255,255,255,0.2); padding: 10px; border-radius: 10px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✅</div>
                <h1>Authentication Successful!</h1>
                <p>Your Kite Connect access token has been automatically generated and saved.</p>
                <div class="highlight">
                    <p><strong>🚀 Your MCP server is now ready to use!</strong></p>
                </div>
                <p>You can close this window and return to your application.</p>
                <p><em>This window will automatically close in 10 seconds...</em></p>
            </div>
            <script>
                setTimeout(function() {
                    window.close();
                }, 10000);
            </script>
        </body>
        </html>
        """
        self.wfile.write(html.encode())
    
    def send_error_response(self, error_msg):
        """Send error response to browser"""
        self.send_response(400)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Kite Connect - Authentication Error</title>
            <style>
                body {{ 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                    text-align: center; 
                    margin-top: 50px; 
                    background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
                    color: white;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                .container {{ 
                    max-width: 600px; 
                    margin: 0 auto; 
                    padding: 40px; 
                    background: rgba(255,255,255,0.1);
                    border-radius: 20px;
                    backdrop-filter: blur(10px);
                    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
                }}
                .error {{ color: #ff4757; font-size: 3em; margin-bottom: 20px; }}
                h1 {{ margin-bottom: 30px; }}
                p {{ font-size: 1.2em; line-height: 1.6; margin-bottom: 20px; }}
                .error-details {{ background: rgba(255,255,255,0.2); padding: 15px; border-radius: 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="error">❌</div>
                <h1>Authentication Failed</h1>
                <div class="error-details">
                    <p><strong>Error:</strong> {error_msg}</p>
                </div>
                <p>Please close this window and try again.</p>
                <p>Check your configuration and ensure your credentials are correct.</p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode())
    
    def log_message(self, format, *args):
        """Override to reduce HTTP server logging"""
        # Intentionally suppress HTTP server logging to reduce noise
        # Parameters are required by the base class but not used
        pass

class FullyAutomatedKiteAuth:
    """Fully automated Kite Connect authentication manager"""
    
    def __init__(self):
        self.config = AutoAuthConfig()
        self.kc = KiteConnect(api_key=self.config.api_key)
        self.server = None
        self.server_thread = None
        self.auth_complete = threading.Event()
        self.auth_success = False
    
    def find_available_port(self, start_port=8080, max_attempts=10):
        """Find an available port starting from start_port"""
        for port in range(start_port, start_port + max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except OSError:
                continue
        raise Exception(f"No available ports found in range {start_port}-{start_port + max_attempts}")
    
    def start_auth_server(self):
        """Start HTTP server to handle OAuth callback"""
        try:
            # Find available port
            port = self.find_available_port()
            
            # Update redirect URL with the port we're using
            self.config.redirect_url = f"http://localhost:{port}/callback"
            
            def handler(*args, **kwargs):
                return AutoAuthCallbackHandler(self, *args, **kwargs)
            
            self.server = HTTPServer(('localhost', port), handler)
            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            logger.info(f"🌐 Auth server started on http://localhost:{port}")
            return port
            
        except Exception as e:
            logger.error(f"Failed to start auth server: {e}")
            return None
    
    def stop_auth_server(self):
        """Stop the HTTP server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            if self.server_thread:
                self.server_thread.join(timeout=5)
            logger.info("🛑 Auth server stopped")
    
    def get_login_url(self):
        """Generate Kite Connect login URL with localhost redirect"""
        # Generate login URL with localhost redirect
        login_url = f"https://kite.trade/connect/login?api_key={self.config.api_key}&redirect_url={self.config.redirect_url}"
        return login_url
    
    def exchange_request_token(self, request_token):
        """Exchange request token for access token"""
        try:
            logger.info("🔄 Exchanging request token for access token...")
            
            # Generate session
            data = self.kc.generate_session(request_token, self.config.api_secret)
            
            access_token = data.get('access_token')
            refresh_token = data.get('refresh_token')
            
            if access_token:
                # Calculate expiry time (Kite tokens typically expire at end of trading day)
                expires_at = (datetime.now() + timedelta(hours=8)).isoformat()
                
                # Save tokens
                self.config.save_tokens(access_token, refresh_token, expires_at)
                
                # Set access token for current session
                self.kc.set_access_token(access_token)
                
                logger.info("✅ Access token generated successfully!")
                
                # Signal that authentication is complete
                self.auth_complete.set()
                self.auth_success = True
                
                return True
            else:
                logger.error("❌ No access token received from Kite Connect")
                self.auth_complete.set()
                return False
                
        except Exception as e:
            logger.error(f"❌ Error exchanging request token: {e}")
            self.auth_complete.set()
            return False
    
    def authenticate_fully_automated(self, timeout=300, force=False):
        """Start the complete automated authentication flow

        Args:
            timeout (int): Timeout in seconds for authentication
            force (bool): If True, force re-authentication even if valid token exists
        """
        logger.info("🚀 Starting fully automated Kite Connect authentication...")

        # Check if running in Docker (no display available)
        is_docker = os.getenv('DOCKER_ENV') == 'true' or not os.getenv('DISPLAY')

        if is_docker:
            logger.warning("🐳 Running in Docker environment - browser authentication not available")
            logger.info("💡 Please authenticate manually on the host system:")
            logger.info("   1. Run: docker-compose exec kite-mcp-server python auth_manager.py auth")
            logger.info("   2. Or authenticate outside Docker and copy tokens to data/ directory")
            raise Exception("Browser authentication not available in Docker environment")

        # Check if we have valid tokens (unless force=True)
        if not force:
            tokens = self.config.load_tokens()
            if tokens and self.is_token_valid(tokens):
                logger.info("✅ Valid access token found, skipping authentication")
                return tokens['access_token']
        else:
            logger.info("🔄 Force authentication requested - ignoring existing tokens")
        
        # Start auth server
        port = self.start_auth_server()
        if not port:
            logger.error("❌ Failed to start authentication server")
            return None
        
        try:
            # Get login URL and open browser
            login_url = self.get_login_url()
            
            print("\n" + "🎉" * 25)
            print("🚀 FULLY AUTOMATED KITE CONNECT AUTHENTICATION")
            print("🎉" * 25)
            print()
            print("📋 What's happening:")
            print("1. 🌐 Opening browser with Zerodha login page")
            print("2. 🔐 You log in with your credentials")
            print("3. 🤖 System automatically captures the callback")
            print("4. ⚡ Tokens are exchanged and saved automatically")
            print("5. ✅ Ready to use!")
            print()
            print("💡 No manual copying required - everything is automated!")
            print()
            
            logger.info(f"🌐 Opening browser: {login_url}")
            webbrowser.open(login_url)
            
            print("⏳ Waiting for authentication to complete...")
            print("🔐 Please log in to your Zerodha account in the browser")
            print()
            
            # Wait for authentication to complete
            if self.auth_complete.wait(timeout=timeout):
                if self.auth_success:
                    print("🎉 AUTHENTICATION COMPLETED SUCCESSFULLY!")
                    print("✅ Your MCP server is now ready to use!")
                    tokens = self.config.load_tokens()
                    return tokens['access_token'] if tokens else None
                else:
                    print("❌ Authentication failed during token exchange")
                    return None
            else:
                print(f"⏰ Authentication timed out after {timeout} seconds")
                print("💡 Please try again and complete the login process faster")
                return None
                
        finally:
            self.stop_auth_server()
    
    def is_token_valid(self, tokens):
        """Check if stored token is still valid"""
        try:
            if not tokens or not tokens.get('access_token'):
                return False
            
            # Check expiry time
            expires_at = tokens.get('expires_at')
            if expires_at:
                expiry_time = datetime.fromisoformat(expires_at)
                if datetime.now() >= expiry_time:
                    logger.info("Token has expired")
                    return False
            
            # Test token by making a simple API call
            self.kc.set_access_token(tokens['access_token'])
            profile = self.kc.profile()

            if profile:
                # Extract profile data using utility function
                profile_data = extract_profile_data(profile)
                logger.info(f"Token is valid for user: {profile_data['user_name']}")
                return True
            
        except Exception as e:
            # Safely convert exception to string to avoid concatenation errors
            try:
                if hasattr(e, 'message'):
                    error_msg = str(e.message)
                elif hasattr(e, 'args') and e.args:
                    error_msg = str(e.args[0])
                else:
                    error_msg = str(e)
            except Exception:
                error_msg = "Unknown error during token validation"

            logger.info(f"Token validation failed: {error_msg}")
        
        return False

    def get_token_status(self):
        """
        Get current token status without triggering authentication

        Returns:
            dict: Token status information
        """
        tokens = self.config.load_tokens()

        if not tokens:
            return {
                "status": "no_tokens",
                "message": "No authentication tokens found",
                "action_required": "Run 'python auth_manager.py auth' to authenticate"
            }

        # Safely check token validity
        try:
            token_is_valid = self.is_token_valid(tokens)
        except Exception as e:
            logger.info(f"Token status check failed: {type(e).__name__}")
            token_is_valid = False

        if token_is_valid:
            return {
                "status": "valid",
                "message": "Access token is valid and ready to use",
                "expires_at": tokens.get('expires_at'),
                "generated_at": tokens.get('generated_at'),
                "action_required": None
            }
        else:
            return {
                "status": "expired",
                "message": "Access token has expired or is invalid",
                "expires_at": tokens.get('expires_at'),
                "generated_at": tokens.get('generated_at'),
                "action_required": "Run 'python auth_manager.py auth' to re-authenticate"
            }

    def get_authenticated_client(self, auto_authenticate=False):
        """
        Get authenticated Kite Connect client

        Args:
            auto_authenticate (bool): If True, automatically re-authenticate when token is invalid.
                                    If False, raise exception when token is invalid.
        """
        tokens = self.config.load_tokens()

        # Safely check token validity with robust error handling
        token_is_valid = False
        if tokens:
            try:
                token_is_valid = self.is_token_valid(tokens)
            except Exception as e:
                logger.info(f"Token validation check failed: {type(e).__name__}")
                token_is_valid = False

        if token_is_valid:
            self.kc.set_access_token(tokens['access_token'])
            return self.kc
        else:
            if auto_authenticate:
                # Only re-authenticate if explicitly requested
                print("🔐 Access token expired or invalid. Starting re-authentication...")
                access_token = self.authenticate_fully_automated(force=True)
                if access_token:
                    self.kc.set_access_token(access_token)
                    return self.kc
                else:
                    raise Exception("Automated authentication failed")
            else:
                # Don't auto-authenticate, just inform user
                raise TokenExpiredException("Access token expired or invalid. Please run 'python auth_manager.py auth' to re-authenticate.")

def main():
    """Main function for fully automated authentication"""
    auth_manager = FullyAutomatedKiteAuth()
    
    try:
        access_token = auth_manager.authenticate_fully_automated()
        
        if access_token:
            print(f"\n🎉 AUTHENTICATION SUCCESSFUL!")
            print(f"💾 Token saved to: {auth_manager.config.tokens_file}")
            print(f"\n🚀 Your MCP server is now ready to use!")
        else:
            print(f"\n❌ AUTHENTICATION FAILED!")
            print(f"💡 Please check your configuration and try again.")
            
    except KeyboardInterrupt:
        print(f"\n⏹️ Authentication cancelled by user")
    except Exception as e:
        print(f"\n💥 Error during authentication: {e}")

if __name__ == "__main__":
    main()
