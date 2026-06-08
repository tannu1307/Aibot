"""
Input validation for trading bot CLI parameters.
All validators raise ValueError with descriptive messages on failure.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET"}

# Soft guards — Binance enforces precise limits per symbol via exchange info,
# but these catch obviously bad values before any network call is made.
MIN_QUANTITY = Decimal("0.000001")
MIN_PRICE = Decimal("0.000001")


def validate_symbol(symbol: str) -> str:
    """
    Ensure the symbol is a non-empty uppercase alphanumeric string.

    Args:
        symbol: Raw symbol string from CLI (e.g. 'btcusdt').

    Returns:
        Uppercased symbol.

    Raises:
        ValueError: If the symbol is empty or contains invalid characters.
    """
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("Symbol must not be empty.")
    if not symbol.isalnum():
        raise ValueError(
            f"Symbol '{symbol}' contains invalid characters. "
            "Use only letters and digits (e.g. BTCUSDT)."
        )
    return symbol


def validate_side(side: str) -> str:
    """
    Validate the order side.

    Args:
        side: 'BUY' or 'SELL' (case-insensitive).

    Returns:
        Uppercased side string.

    Raises:
        ValueError: If the side is not recognised.
    """
    side = side.strip().upper()
    if side not in VALID_SIDES:
        raise ValueError(
            f"Invalid side '{side}'. Allowed values: {', '.join(sorted(VALID_SIDES))}."
        )
    return side


def validate_order_type(order_type: str) -> str:
    """
    Validate the order type.

    Args:
        order_type: 'MARKET', 'LIMIT', or 'STOP_MARKET' (case-insensitive).

    Returns:
        Uppercased order type string.

    Raises:
        ValueError: If the order type is not recognised.
    """
    order_type = order_type.strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Invalid order type '{order_type}'. "
            f"Allowed values: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )
    return order_type


def validate_quantity(quantity: str | float | Decimal) -> Decimal:
    """
    Parse and validate order quantity.

    Args:
        quantity: Raw quantity value.

    Returns:
        Validated Decimal quantity.

    Raises:
        ValueError: If quantity is not a valid positive number.
    """
    try:
        qty = Decimal(str(quantity))
    except InvalidOperation:
        raise ValueError(f"Quantity '{quantity}' is not a valid number.")
    if qty <= 0:
        raise ValueError(f"Quantity must be positive, got {qty}.")
    if qty < MIN_QUANTITY:
        raise ValueError(f"Quantity {qty} is below minimum allowed ({MIN_QUANTITY}).")
    return qty


def validate_price(price: Optional[str | float | Decimal]) -> Optional[Decimal]:
    """
    Parse and validate order price (required for LIMIT orders).

    Args:
        price: Raw price value, or None for MARKET orders.

    Returns:
        Validated Decimal price, or None.

    Raises:
        ValueError: If price is provided but invalid.
    """
    if price is None:
        return None
    try:
        p = Decimal(str(price))
    except InvalidOperation:
        raise ValueError(f"Price '{price}' is not a valid number.")
    if p <= 0:
        raise ValueError(f"Price must be positive, got {p}.")
    if p < MIN_PRICE:
        raise ValueError(f"Price {p} is below minimum allowed ({MIN_PRICE}).")
    return p


def validate_stop_price(stop_price: Optional[str | float | Decimal]) -> Optional[Decimal]:
    """
    Parse and validate stop price (required for STOP_MARKET orders).

    Args:
        stop_price: Raw stop price value, or None.

    Returns:
        Validated Decimal stop price, or None.

    Raises:
        ValueError: If stop price is provided but invalid.
    """
    if stop_price is None:
        return None
    try:
        sp = Decimal(str(stop_price))
    except InvalidOperation:
        raise ValueError(f"Stop price '{stop_price}' is not a valid number.")
    if sp <= 0:
        raise ValueError(f"Stop price must be positive, got {sp}.")
    return sp


def validate_order_params(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | float | Decimal,
    price: Optional[str | float | Decimal] = None,
    stop_price: Optional[str | float | Decimal] = None,
) -> dict:
    """
    Run all field validators and enforce cross-field rules.

    Returns:
        Dict of validated, normalised parameters.

    Raises:
        ValueError: On any validation failure.
    """
    validated = {
        "symbol": validate_symbol(symbol),
        "side": validate_side(side),
        "order_type": validate_order_type(order_type),
        "quantity": validate_quantity(quantity),
        "price": validate_price(price),
        "stop_price": validate_stop_price(stop_price),
    }

    # Cross-field rules
    if validated["order_type"] == "LIMIT" and validated["price"] is None:
        raise ValueError("Price is required for LIMIT orders.")
    if validated["order_type"] == "MARKET" and validated["price"] is not None:
        raise ValueError("Price must not be supplied for MARKET orders.")
    if validated["order_type"] == "STOP_MARKET" and validated["stop_price"] is None:
        raise ValueError("Stop price (--stop-price) is required for STOP_MARKET orders.")

    return validated
