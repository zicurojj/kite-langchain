#!/usr/bin/env python3
"""
Authentication utilities and common patterns
Consolidates duplicate code across authentication modules
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def extract_profile_data(profile: Dict[str, Any]) -> Dict[str, str]:
    """
    Safely extract and normalize profile data from Kite Connect API response
    
    Args:
        profile: Profile data from kc.profile() API call
        
    Returns:
        Dict with normalized user_name, email, and broker fields
    """
    # Safely extract user name, handling different data types
    user_name = profile.get('user_name', 'Unknown')
    if isinstance(user_name, dict):
        user_name = user_name.get('name', 'Unknown')
    elif not isinstance(user_name, str):
        user_name = str(user_name)

    # Safely extract email
    email = profile.get('email', 'Unknown')
    if not isinstance(email, str):
        email = str(email)

    # Safely extract broker
    broker = profile.get('broker', 'Unknown')
    if not isinstance(broker, str):
        broker = str(broker)

    return {
        'user_name': user_name,
        'email': email,
        'broker': broker
    }

def format_authentication_status(status: str, profile_data: Optional[Dict[str, str]] = None, 
                               tokens: Optional[Dict[str, Any]] = None) -> str:
    """
    Format authentication status message consistently
    
    Args:
        status: Authentication status ('valid', 'expired', 'no_tokens')
        profile_data: Optional profile data from extract_profile_data()
        tokens: Optional token data with generated_at, expires_at
        
    Returns:
        Formatted status message
    """
    if status == 'valid':
        message = "✅ Authentication Status: VALID"
        if profile_data:
            message += f"\n👤 User: {profile_data['user_name']}"
            message += f"\n📧 Email: {profile_data['email']}"
            message += f"\n🏢 Broker: {profile_data['broker']}"
        if tokens:
            message += f"\n📅 Token Generated: {tokens.get('generated_at', 'Unknown')}"
        return message
    elif status == 'expired':
        return "❌ Authentication Status: INVALID or EXPIRED\n💡 Please run 'python auth_manager.py auth' to re-authenticate."
    else:
        return "❌ No authentication tokens found. Please run 'python auth_manager.py auth' to authenticate."

def create_auth_error_response(error_type: str, error_message: str, action_required: str = None) -> Dict[str, Any]:
    """
    Create standardized authentication error response
    
    Args:
        error_type: Type of error (authentication_error, validation_error, etc.)
        error_message: Human-readable error message
        action_required: Optional action user should take
        
    Returns:
        Standardized error response dict
    """
    response = {
        "status": error_type,
        "error": error_message,
        "message": error_message
    }
    
    if action_required:
        response["action_required"] = action_required
    
    return response

def is_token_expired_error(error: Exception) -> bool:
    """
    Check if an exception indicates token expiration
    
    Args:
        error: Exception to check
        
    Returns:
        True if error indicates token expiration
    """
    error_str = str(error).lower()
    return "token" in error_str or "auth" in error_str

def get_auth_retry_message() -> str:
    """Get standardized authentication retry message"""
    return ("🔐 Access token expired. Starting automatic re-authentication...\n"
            "🌐 Browser will open for login - please complete authentication")

def get_manual_auth_instructions() -> str:
    """Get standardized manual authentication instructions"""
    return ("💡 Authentication required for trading operations.\n"
            "🚀 Options:\n"
            "   • Run: python auth_manager.py auth\n"
            "   • Run: python auth_manager.py force\n"
            "   • Use MCP tool: authenticate_now()")

class AuthenticationRetryHandler:
    """
    Handles authentication retry logic consistently across modules
    """
    
    def __init__(self, auth_manager):
        self.auth_manager = auth_manager
        
    def handle_auth_error(self, error: Exception, operation_name: str = "operation") -> Dict[str, Any]:
        """
        Handle authentication errors with consistent retry logic
        
        Args:
            error: The authentication error
            operation_name: Name of the operation that failed
            
        Returns:
            Error response dict
        """
        if is_token_expired_error(error):
            try:
                print(get_auth_retry_message())
                # Try automatic re-authentication
                client = self.auth_manager.get_authenticated_client(auto_authenticate=True)
                if client:
                    return {"status": "retry_available", "client": client}
            except Exception as auth_error:
                return create_auth_error_response(
                    "authentication_error",
                    f"Automatic re-authentication failed: {auth_error}",
                    "manual_auth"
                )
        
        return create_auth_error_response(
            "authentication_error",
            f"{operation_name} failed: {error}",
            "check_config"
        )
