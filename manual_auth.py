#!/usr/bin/env python3
"""
Manual Authentication for Kite Connect
Alternative authentication method for Docker/headless environments
"""

import sys
from datetime import datetime, timedelta
from kiteconnect import KiteConnect
from auth_fully_automated import AutoAuthConfig
from auth_utils import extract_profile_data
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ManualKiteAuth:
    """Manual authentication for Kite Connect - no browser automation"""
    
    def __init__(self):
        self.config = AutoAuthConfig()
        self.kc = KiteConnect(api_key=self.config.api_key)
    
    def get_login_url(self):
        """Generate the login URL for manual authentication"""
        login_url = f"https://kite.trade/connect/login?api_key={self.config.api_key}&redirect_url={self.config.original_redirect_url}"
        return login_url
    
    def extract_request_token(self, callback_url):
        """Extract request token from callback URL"""
        try:
            if "request_token=" in callback_url:
                # Extract request token from URL
                token_start = callback_url.find("request_token=") + len("request_token=")
                token_end = callback_url.find("&", token_start)
                if token_end == -1:
                    token_end = len(callback_url)
                request_token = callback_url[token_start:token_end]
                return request_token
            else:
                logger.error("No request_token found in callback URL")
                return None
        except Exception as e:
            logger.error(f"Error extracting request token: {e}")
            return None
    
    def authenticate_with_request_token(self, request_token):
        """Complete authentication using request token"""
        try:
            logger.info("🔄 Exchanging request token for access token...")
            
            # Generate session
            data = self.kc.generate_session(request_token, api_secret=self.config.api_secret)
            
            # Prepare token data
            token_data = {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token", ""),
                "expires_at": (datetime.now() + timedelta(hours=8)).isoformat(),
                "generated_at": datetime.now().isoformat()
            }
            
            # Save tokens
            self.config.save_tokens(
                token_data["access_token"],
                token_data["refresh_token"],
                token_data["expires_at"]
            )
            
            # Verify the token works
            self.kc.set_access_token(data["access_token"])
            profile = self.kc.profile()
            
            logger.info("✅ Authentication successful!")

            # Extract profile data using utility function
            profile_data = extract_profile_data(profile)
            logger.info(f"👤 User: {profile_data['user_name']}")
            logger.info(f"📧 Email: {profile_data['email']}")
            logger.info(f"🏢 Broker: {profile_data['broker']}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            return False
    
    def interactive_auth(self):
        """Interactive manual authentication process"""
        print("🔐 MANUAL KITE CONNECT AUTHENTICATION")
        print("=" * 50)
        print()
        
        # Step 1: Show login URL
        login_url = self.get_login_url()
        print("📋 STEP 1: Open this URL in your browser:")
        print(f"🔗 {login_url}")
        print()
        
        # Step 2: Instructions
        print("📋 STEP 2: Complete the login process:")
        print("1. 🌐 Open the URL above in your browser")
        print("2. 🔐 Log in with your Zerodha credentials")
        print("3. 📱 Complete 2FA if required")
        print("4. 📋 You'll be redirected to a callback URL")
        print("5. 📝 Copy the ENTIRE callback URL")
        print()
        
        # Step 3: Get callback URL
        print("📋 STEP 3: Paste the callback URL here:")
        print("💡 The URL should contain 'request_token=' parameter")
        print()
        
        while True:
            callback_url = input("🔗 Paste callback URL: ").strip()
            
            if not callback_url:
                print("❌ Please enter the callback URL")
                continue
            
            if "request_token=" not in callback_url:
                print("❌ Invalid URL - should contain 'request_token=' parameter")
                print("💡 Make sure you copied the complete URL after login")
                continue
            
            # Extract request token
            request_token = self.extract_request_token(callback_url)
            if not request_token:
                print("❌ Could not extract request token from URL")
                continue
            
            print(f"✅ Request token extracted: {request_token[:10]}...")
            break
        
        # Step 4: Complete authentication
        print()
        print("📋 STEP 4: Completing authentication...")
        success = self.authenticate_with_request_token(request_token)
        
        if success:
            print()
            print("🎉 AUTHENTICATION COMPLETED SUCCESSFULLY!")
            print("✅ You can now use the trading system")
            print("💡 Tokens are saved and will be used automatically")
        else:
            print()
            print("❌ AUTHENTICATION FAILED")
            print("💡 Please try again or check your credentials")
        
        return success
    
    def quick_auth_with_token(self, request_token):
        """Quick authentication if you already have the request token"""
        print(f"🔄 Authenticating with request token: {request_token[:10]}...")
        success = self.authenticate_with_request_token(request_token)
        
        if success:
            print("✅ Authentication successful!")
        else:
            print("❌ Authentication failed!")
        
        return success

def main():
    """Main function for command line usage"""
    auth = ManualKiteAuth()
    
    if len(sys.argv) > 1:
        # Quick mode with request token
        request_token = sys.argv[1]
        auth.quick_auth_with_token(request_token)
    else:
        # Interactive mode
        auth.interactive_auth()

if __name__ == "__main__":
    main()
