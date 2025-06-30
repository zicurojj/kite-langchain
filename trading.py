
#!/usr/bin/env python3
"""
Trading functions for Zerodha Kite Connect
Handles order placement and portfolio management
"""
from logger import log_order_success, log_order_rejection, log_order_error, log_order_placed_but_rejected
from datetime import datetime
import json
import time
from auth_fully_automated import FullyAutomatedKiteAuth, TokenExpiredException
from auth_utils import get_auth_retry_message, get_manual_auth_instructions, is_token_expired_error
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Initialize authentication manager
auth_manager = FullyAutomatedKiteAuth()

# Global client variable
kc = None

def get_authenticated_kite_client(force_auth=False):
    """
    Get authenticated Kite Connect client

    Args:
        force_auth (bool): If True, force re-authentication even if token exists
    """
    global kc

    try:
        if force_auth:
            # Force re-authentication - always get fresh token
            logger.info("🔄 Forcing re-authentication...")
            logger.info("💡 This will replace any existing token with a fresh one")
            access_token = auth_manager.authenticate_fully_automated(force=True)
            if access_token:
                kc = auth_manager.kc
                logger.info("✅ Force re-authentication successful!")
                return kc
            else:
                raise Exception("Force authentication failed")
        else:
            # Try to get client without auto-authentication
            kc = auth_manager.get_authenticated_client(auto_authenticate=False)
            return kc

    except TokenExpiredException as e:
        # Token expired - inform user but don't auto-authenticate
        logger.warning(f"🔐 {e}")
        logger.info(get_manual_auth_instructions())
        raise
    except Exception as e:
        logger.error(f"❌ Error getting authenticated client: {e}")
        logger.info("💡 Use get_kite_login_url() to authenticate")
        raise

def ensure_authenticated():
    """Ensure we have a valid authenticated client, with user-friendly error messages"""
    try:
        return get_authenticated_kite_client()
    except TokenExpiredException:
        return None  # Let calling function handle this gracefully
    except Exception:
        return None

# Try to initialize client, but don't force authentication on import
try:
    kc = get_authenticated_kite_client()
    print("✅ Kite Connect client initialized successfully")
except TokenExpiredException:
    print("🔐 Authentication required. Use get_kite_login_url() when ready to trade.")
    kc = None
except Exception as e:
    print(f"⚠️ Could not initialize Kite Connect client: {e}")
    kc = None

def place_order(tradingsymbol, quantity, transaction_type, exchange="NSE", product="CNC", order_type="MARKET", price=None, trigger_price=None, variety="regular", validity="DAY"):
    """
    Place an order and log the result with detailed error handling.

    Args:
        tradingsymbol (str): Trading symbol (e.g., 'RELIANCE', 'TCS')
        quantity (int): Number of shares to trade
        transaction_type (str): 'BUY' or 'SELL'
        exchange (str): Exchange name (NSE, BSE, etc.)
        product (str): Product type (CNC, MIS, NRML)
        order_type (str): Order type (MARKET, LIMIT, SL, SL-M)
        price (float, optional): Price for limit orders
        trigger_price (float, optional): Trigger price for stop loss orders
        variety (str): Order variety (regular, bo, co, amo)
        validity (str): Order validity (DAY, IOC)

    Returns:
        dict: Order result with status and details
    """
    # Input validation
    if not tradingsymbol or not isinstance(tradingsymbol, str):
        return {
            "status": "validation_error",
            "error": "Invalid trading symbol",
            "message": "Trading symbol must be a non-empty string"
        }

    if not isinstance(quantity, int) or quantity <= 0:
        return {
            "status": "validation_error",
            "error": "Invalid quantity",
            "message": "Quantity must be a positive integer"
        }

    if transaction_type not in ['BUY', 'SELL']:
        return {
            "status": "validation_error",
            "error": "Invalid transaction type",
            "message": "Transaction type must be 'BUY' or 'SELL'"
        }

    if exchange not in ['NSE', 'BSE', 'NFO', 'CDS', 'MCX']:
        return {
            "status": "validation_error",
            "error": "Invalid exchange",
            "message": "Exchange must be one of: NSE, BSE, NFO, CDS, MCX"
        }

    if order_type in ['LIMIT', 'SL'] and (price is None or price <= 0):
        return {
            "status": "validation_error",
            "error": "Invalid price",
            "message": f"Price is required and must be positive for {order_type} orders"
        }

    if order_type in ['SL', 'SL-M'] and (trigger_price is None or trigger_price <= 0):
        return {
            "status": "validation_error",
            "error": "Invalid trigger price",
            "message": f"Trigger price is required and must be positive for {order_type} orders"
        }

    timestamp = datetime.now().isoformat()

    # Check if we have an authenticated client
    global kc
    if kc is None:
        try:
            # Try automatic authentication when token expires
            print(get_auth_retry_message())
            kc = auth_manager.get_authenticated_client(auto_authenticate=True)
        except Exception as e:
            return {
                "status": "authentication_error",
                "error": str(e),
                "message": "Automatic authentication failed. Please use get_kite_login_url() to authenticate.",
                "action_required": "check_config"
            }

    try:
        params = {
            "exchange": exchange,
            "tradingsymbol": tradingsymbol,
            "transaction_type": transaction_type,
            "quantity": quantity,
            "product": product,
            "order_type": order_type,
            "validity": validity
        }
        if price is not None:
            params["price"] = price
        if trigger_price is not None:
            params["trigger_price"] = trigger_price

        # Place the order
        order_response = kc.place_order(variety=variety, **params)

        # Extract order ID from response - handle different response types
        order_id = None
        if order_response:
            if isinstance(order_response, dict):
                order_id = order_response.get("order_id")
            elif isinstance(order_response, str):
                # Sometimes API returns just the order ID as a string
                order_id = order_response

        # Check order status after placement to see if it was rejected
        order_status = None
        rejection_reason = None

        if order_id:
            try:
                # Wait a moment for order to be processed
                time.sleep(1)

                # Get order status
                orders = kc.orders()
                placed_order = None
                for order in orders:
                    if order.get('order_id') == order_id:
                        placed_order = order
                        break

                if placed_order:
                    order_status = placed_order.get('status')
                    rejection_reason = placed_order.get('status_message') or placed_order.get('rejection_reason')

                    # Check if order was rejected after placement
                    if order_status in ['REJECTED', 'CANCELLED']:
                        log_order_placed_but_rejected(
                            timestamp=timestamp,
                            type_=transaction_type,
                            stock=tradingsymbol,
                            quantity=quantity,
                            exchange=exchange,
                            product=product,
                            order_type=order_type,
                            price=price,
                            trigger_price=trigger_price,
                            order_id=order_id,
                            rejection_reason=rejection_reason,
                            order_status=order_status
                        )

                        print(f"Order {order_id} was placed but rejected. Status: {order_status}, Reason: {rejection_reason}")
                        return {
                            "status": "placed_but_rejected",
                            "order_id": order_id,
                            "order_status": order_status,
                            "rejection_reason": rejection_reason,
                            "message": f"Order was placed but rejected by exchange. Reason: {rejection_reason}"
                        }

            except Exception as status_check_error:
                print(f"Could not check order status: {status_check_error}")
                # Continue with success logging if status check fails

        # Log successful order placement
        log_order_success(
            timestamp=timestamp,
            type_=transaction_type,
            stock=tradingsymbol,
            quantity=quantity,
            exchange=exchange,
            product=product,
            order_type=order_type,
            price=price,
            trigger_price=trigger_price,
            order_id=order_id
        )

        print(f"Order placed successfully. Order ID: {order_id}")
        return {
            "status": "success",
            "order_id": order_id,
            "order_status": order_status or "PENDING",
            "message": f"Order placed successfully for {quantity} shares of {tradingsymbol}"
        }

    except Exception as e:
        # Check if this is a token expiry error and try auto-authentication
        if is_token_expired_error(e):
            print(get_auth_retry_message())
            try:
                # Try automatic re-authentication
                kc = auth_manager.get_authenticated_client(auto_authenticate=True)
                # Retry the order placement with new token
                order_response = kc.place_order(variety=variety, **params)

                # Process the retry response (simplified version)
                order_id = None
                if order_response:
                    if isinstance(order_response, dict):
                        order_id = order_response.get("order_id")
                    elif isinstance(order_response, str):
                        order_id = order_response

                log_order_success(
                    timestamp=timestamp,
                    type_=transaction_type,
                    stock=tradingsymbol,
                    quantity=quantity,
                    exchange=exchange,
                    product=product,
                    order_type=order_type,
                    price=price,
                    trigger_price=trigger_price,
                    order_id=order_id
                )

                print(f"Order placed successfully after re-authentication. Order ID: {order_id}")
                return {
                    "status": "success",
                    "order_id": order_id,
                    "order_status": "PENDING",
                    "message": f"Order placed successfully for {quantity} shares of {tradingsymbol} (after automatic re-authentication)"
                }

            except Exception as auth_error:
                return {
                    "status": "authentication_error",
                    "error": str(auth_error),
                    "message": f"Automatic re-authentication failed: {auth_error}. Please use get_kite_login_url() to authenticate.",
                    "action_required": "manual_auth"
                }

        # Handle different types of exceptions
        error_details = str(e)
        error_code = None
        error_message = None
        rejection_reason = None

        # Try to parse KiteConnect specific errors safely
        try:
            # Check if it's a KiteConnect API error with message attribute
            if hasattr(e, 'message') and e.message:
                error_message = str(e.message)

            # Try to extract error details from the exception args
            if hasattr(e, 'args') and e.args and len(e.args) > 0:
                error_str = str(e.args[0])

                # Try to parse JSON error response if it looks like JSON
                if error_str.strip().startswith('{') and error_str.strip().endswith('}'):
                    try:
                        error_json = json.loads(error_str)
                        if isinstance(error_json, dict):
                            error_code = error_json.get('error_type') or error_json.get('status')
                            error_message = error_json.get('message') or error_json.get('error')

                            # Safely extract rejection reason
                            data = error_json.get('data')
                            if isinstance(data, dict):
                                rejection_reason = data.get('rejection_reason')
                    except (json.JSONDecodeError, TypeError, AttributeError):
                        # If JSON parsing fails, use the raw error string
                        error_message = error_str
                else:
                    # Not JSON, use as error message
                    error_message = error_str

        except Exception:
            # If all parsing fails, just use the original error string
            error_message = error_details

        # Log the order rejection/error
        if error_code or rejection_reason:
            log_order_rejection(
                timestamp=timestamp,
                type_=transaction_type,
                stock=tradingsymbol,
                quantity=quantity,
                exchange=exchange,
                product=product,
                order_type=order_type,
                price=price,
                trigger_price=trigger_price,
                order_id=None,  # No order ID for rejected orders
                error_code=error_code,
                error_message=error_message,
                rejection_reason=rejection_reason
            )
        else:
            log_order_error(
                timestamp=timestamp,
                type_=transaction_type,
                stock=tradingsymbol,
                quantity=quantity,
                exchange=exchange,
                product=product,
                order_type=order_type,
                price=price,
                trigger_price=trigger_price,
                order_id=None,  # No order ID for error cases
                error_details=error_details
            )

        print(f"Order placement failed: {error_details}")
        return {
            "status": "failed",
            "error": error_details,
            "error_code": error_code,
            "error_message": error_message,
            "rejection_reason": rejection_reason
        }


def get_positions():
    """Get current positions with authentication handling"""
    global kc

    # Check if we have an authenticated client
    if kc is None:
        try:
            # Try automatic authentication when token expires
            print(get_auth_retry_message())
            kc = auth_manager.get_authenticated_client(auto_authenticate=True)
        except Exception as e:
            return f"❌ Automatic authentication failed: {e}\n💡 Please use get_kite_login_url() to authenticate"

    try:
        positions = kc.positions()
        if positions and positions.get("net"):
            return "\n".join([f"stock: {p['tradingsymbol']}, qty: {p['quantity']}, currentPrice: {p['last_price']}" for p in positions["net"]])
        else:
            return "No positions found."
    except Exception as e:
        # Token might have expired during the call
        if is_token_expired_error(e):
            print(get_auth_retry_message())
            kc = None  # Reset client
            try:
                # Try automatic re-authentication
                kc = auth_manager.get_authenticated_client(auto_authenticate=True)
                # Retry the positions call with new token
                positions = kc.positions()
                if positions and positions.get("net"):
                    return "\n".join([f"stock: {p['tradingsymbol']}, qty: {p['quantity']}, currentPrice: {p['last_price']}" for p in positions["net"]])
                else:
                    return "No positions found."
            except Exception as auth_error:
                return f"❌ Automatic re-authentication failed: {auth_error}\n💡 Please use get_kite_login_url() to authenticate"
        return f"❌ Error fetching positions: {e}"
