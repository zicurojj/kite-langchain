
#!/usr/bin/env python3
"""
Order logging utilities for trading operations
Provides structured logging for order placement, success, and failures
"""
from typing import Optional
import os

# Use logs directory for Docker compatibility
os.makedirs('logs', exist_ok=True)
log_file_path = os.path.join('logs', 'order.log')

def log_order_success(timestamp: str, type_: str, stock: str, quantity: int,
                     exchange: str = "NSE", product: str = "CNC",
                     order_type: str = "MARKET", price: Optional[float] = None,
                     trigger_price: Optional[float] = None, order_id: Optional[str] = None):
    """Log successful order placement"""
    log_entry = f"{timestamp} | SUCCESS | {type_} | {stock} | Qty: {quantity} | {exchange} | {product} | {order_type}"

    if price is not None:
        log_entry += f" | Price: {price}"
    if trigger_price is not None:
        log_entry += f" | Trigger: {trigger_price}"
    if order_id is not None:
        log_entry += f" | OrderID: {order_id}"

    log_entry += "\n"

    with open(log_file_path, "a", encoding="utf-8") as f:
        f.write(log_entry)

def log_order_rejection(timestamp: str, type_: str, stock: str, quantity: int,
                       exchange: str = "NSE", product: str = "CNC",
                       order_type: str = "MARKET", price: Optional[float] = None,
                       trigger_price: Optional[float] = None,
                       order_id: Optional[str] = None,
                       error_code: Optional[str] = None,
                       error_message: Optional[str] = None,
                       rejection_reason: Optional[str] = None):
    """Log order rejection with detailed error information"""
    log_entry = f"{timestamp} | REJECTED | {type_} | {stock} | Qty: {quantity} | {exchange} | {product} | {order_type}"

    if price is not None:
        log_entry += f" | Price: {price}"
    if trigger_price is not None:
        log_entry += f" | Trigger: {trigger_price}"

    # Add order ID with appropriate status message
    if order_id is not None and order_id.strip():
        log_entry += f" | OrderID: {order_id} | Status: PLACED_BUT_REJECTED"
    else:
        log_entry += f" | OrderID: NOT_CREATED | Status: REJECTED_BEFORE_PLACEMENT"

    # Add error details
    if error_code is not None:
        log_entry += f" | ErrorCode: {error_code}"
    if error_message is not None:
        log_entry += f" | ErrorMsg: {error_message}"
    if rejection_reason is not None:
        log_entry += f" | Reason: {rejection_reason}"

    log_entry += "\n"

    with open(log_file_path, "a", encoding="utf-8") as f:
        f.write(log_entry)

def log_order_placed_but_rejected(timestamp: str, type_: str, stock: str, quantity: int,
                                 exchange: str = "NSE", product: str = "CNC",
                                 order_type: str = "MARKET", price: Optional[float] = None,
                                 trigger_price: Optional[float] = None,
                                 order_id: str = None,
                                 rejection_reason: Optional[str] = None,
                                 order_status: Optional[str] = None):
    """Log orders that were placed successfully but rejected by exchange"""
    log_entry = f"{timestamp} | PLACED_BUT_REJECTED | {type_} | {stock} | Qty: {quantity} | {exchange} | {product} | {order_type}"

    if price is not None:
        log_entry += f" | Price: {price}"
    if trigger_price is not None:
        log_entry += f" | Trigger: {trigger_price}"

    # Order ID should always be present for placed orders
    if order_id is not None:
        log_entry += f" | OrderID: {order_id}"
    else:
        log_entry += f" | OrderID: UNKNOWN"

    if order_status is not None:
        log_entry += f" | OrderStatus: {order_status}"

    if rejection_reason is not None:
        log_entry += f" | Reason: {rejection_reason}"

    log_entry += "\n"

    with open(log_file_path, "a", encoding="utf-8") as f:
        f.write(log_entry)

def log_order_error(timestamp: str, type_: str, stock: str, quantity: int,
                   exchange: str = "NSE", product: str = "CNC",
                   order_type: str = "MARKET", price: Optional[float] = None,
                   trigger_price: Optional[float] = None,
                   order_id: Optional[str] = None,
                   error_details: Optional[str] = None):
    """Log general order processing errors (network, API issues, etc.)"""
    log_entry = f"{timestamp} | ERROR | {type_} | {stock} | Qty: {quantity} | {exchange} | {product} | {order_type}"

    if price is not None:
        log_entry += f" | Price: {price}"
    if trigger_price is not None:
        log_entry += f" | Trigger: {trigger_price}"

    # Add order ID or indicate no order was created
    if order_id is not None:
        log_entry += f" | OrderID: {order_id}"
    else:
        log_entry += f" | OrderID: NOT_CREATED"

    if error_details is not None:
        log_entry += f" | Error: {error_details}"

    log_entry += "\n"

    with open(log_file_path, "a", encoding="utf-8") as f:
        f.write(log_entry)

# Backward compatibility - keep the old function name but mark as deprecated
def log_order(timestamp, type_, stock, quantity, exchange="NSE", product="CNC", order_type="MARKET", price=None, trigger_price=None):
    """
    DEPRECATED: Use log_order_success, log_order_rejection, or log_order_error instead.
    This function assumes successful order placement.
    """
    log_order_success(timestamp, type_, stock, quantity, exchange, product, order_type, price, trigger_price)
