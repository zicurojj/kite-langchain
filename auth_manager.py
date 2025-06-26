#!/usr/bin/env python3
"""
Unified Authentication Manager for Kite Connect
Combines all authentication functionality into one script
"""

from auth_fully_automated import FullyAutomatedKiteAuth
from auth_utils import extract_profile_data
import sys
import os

# Try to import python-dotenv for .env file support
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class UnifiedAuthManager:
    """Unified authentication manager with all functionality"""
    
    def __init__(self):
        # Validate environment configuration
        api_key = os.getenv('KITE_API_KEY')
        api_secret = os.getenv('KITE_API_SECRET')

        if not api_key or not api_secret:
            print("❌ Environment configuration error: Missing KITE_API_KEY or KITE_API_SECRET")
            print("💡 Copy .env.example to .env and add your API credentials")
            raise ValueError("Missing required environment variables")

        self.auth = FullyAutomatedKiteAuth()
    
    def check_status(self, verbose=True):
        """Check authentication status"""
        if verbose:
            print("🔍 Kite Connect Authentication Status")
            print("=" * 50)
        
        try:
            status = self.auth.get_token_status()
            
            if verbose:
                print(f"📋 Status: {status['status'].upper()}")
                print(f"💬 Message: {status['message']}")
                
                if status.get('generated_at'):
                    print(f"📅 Generated: {status['generated_at']}")
                if status.get('expires_at'):
                    print(f"⏰ Expires: {status['expires_at']}")
                
                if status['status'] == 'valid':
                    try:
                        tokens = self.auth.config.load_tokens()
                        self.auth.kc.set_access_token(tokens['access_token'])
                        profile = self.auth.kc.profile()

                        # Extract profile data using utility function
                        profile_data = extract_profile_data(profile)
                        print(f"👤 User: {profile_data['user_name']}")
                        print(f"📧 Email: {profile_data['email']}")
                        print("✅ Ready for trading!")
                    except Exception as e:
                        print(f"⚠️ Could not fetch user details: {e}")
                
                if status.get('action_required'):
                    print(f"💡 Action: {status['action_required']}")
            
            return status['status'] == 'valid'
            
        except Exception as e:
            if verbose:
                print(f"❌ Error checking status: {e}")
            return False
    
    def authenticate(self, force=False):
        """Smart authentication - checks existing token first unless force=True"""
        print("🚀 Kite Connect Authentication")
        print("=" * 40)
        
        if not force:
            # Check existing token first
            if self.check_status(verbose=False):
                print("✅ You already have a valid access token!")
                tokens = self.auth.config.load_tokens()
                print(f"📅 Generated: {tokens.get('generated_at', 'Unknown')}")
                print(f"⏰ Expires: {tokens.get('expires_at', 'Unknown')}")
                print()

                choice = input("Re-authenticate anyway? (y/N): ").strip().lower()
                if choice not in ['y', 'yes']:
                    print("👍 Using existing token!")
                    return True
                else:
                    # User confirmed re-authentication, so force it
                    force = True
                print()

        print("🔄 Starting authentication flow...")
        print("💡 Browser will open for login")
        print()

        try:
            access_token = self.auth.authenticate_fully_automated(timeout=300, force=force)
            
            if access_token:
                print("\n🎉 AUTHENTICATION SUCCESSFUL!")
                print("🚀 Ready for trading!")
                return True
            else:
                print("\n❌ Authentication failed!")
                return False
                
        except KeyboardInterrupt:
            print("\n⏹️ Authentication cancelled")
            return False
        except Exception as e:
            print(f"\n❌ Error: {e}")
            return False

def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("🤖 Unified Kite Connect Authentication Manager")
        print("=" * 50)
        print()
        print("Usage:")
        print("  python auth_manager.py check          # Check auth status")
        print("  python auth_manager.py auth           # Smart authentication")
        print("  python auth_manager.py force          # Force re-authentication")
        print("  python auth_manager.py manual         # Manual authentication")
        print("  python auth_manager.py status         # Detailed status")
        print()
        return
    
    command = sys.argv[1].lower()

    try:
        manager = UnifiedAuthManager()
    except Exception as e:
        print(f"❌ Failed to initialize authentication manager: {e}")
        sys.exit(1)

    if command in ['check', 'status']:
        manager.check_status(verbose=True)
        
    elif command == 'auth':
        success = manager.authenticate(force=False)
        sys.exit(0 if success else 1)
        
    elif command == 'force':
        print("🔄 FORCE RE-AUTHENTICATION")
        print("⚠️ This will replace any existing token")
        print()
        choice = input("Continue? (y/N): ").strip().lower()
        if choice in ['y', 'yes']:
            success = manager.authenticate(force=True)
            sys.exit(0 if success else 1)
        else:
            print("⏹️ Cancelled")

    elif command == 'manual':
        print("🔐 MANUAL AUTHENTICATION")
        print("💡 This method doesn't require browser automation")
        print("🐳 Perfect for Docker containers and headless servers")
        print()

        try:
            from manual_auth import ManualKiteAuth
            manual_auth = ManualKiteAuth()
            success = manual_auth.interactive_auth()
            sys.exit(0 if success else 1)

        except ImportError:
            print("❌ Manual authentication module not found")
            print("💡 Make sure manual_auth.py is in the same directory")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Manual authentication error: {e}")
            sys.exit(1)

    else:
        print(f"❌ Unknown command: {command}")
        print("💡 Use: check, auth, force, manual, or status")
        sys.exit(1)

if __name__ == "__main__":
    main()
