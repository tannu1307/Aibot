"""
Order placement orchestration layer.

Sits between the CLI and the raw BinanceFuturesClient.
Responsibilities:
  - Accept validated parameters from the CLI
  - Delegate to the client
  - Format and return a human-readable OrderResult
  - Log the full order lifecycle
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Optional

from .client import BinanceAPIError, BinanceFuturesClient
from .logging_config import get_logger
from .validators import validate_order_params

logger = get_logger("orders")


@dataclass
class OrderResult:
    """
    Normalised result returned after an order attempt.

    Fields mirror the most useful fields from the Binance response
    while remaining easy to print / serialise.
    """

    success: bool
    symbol: str
    side: str
    order_type: str
    quantity: Decimal

    # Populated on success
    order_id: Optional[int] = None
    client_order_id: Optional[str] = None
    status: Optional[str] = None
    executed_qty: Optional[Decimal] = None
    avg_price: Optional[Decimal] = None
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None

    # Populated on failure
    error_code: Optional[int] = None
    error_message: Optional[str] = None

    # Full raw response for debugging
    raw: Dict[str, Any] = field(default_factory=dict)

    # -----------------------------------------------------------------
    # Display helpers
    # -----------------------------------------------------------------

    def print_summary(self) -> None:
        """Print a formatted order summary to stdout."""
        sep = "─" * 56
        print(f"\n{sep}")
        print(f"  ORDER {'SUBMITTED ✓' if self.success else 'FAILED ✗'}")
        print(sep)
        print(f"  Symbol      : {self.symbol}")
        print(f"  Side        : {self.side}")
        print(f"  Type        : {self.order_type}")
        print(f"  Quantity    : {self.quantity}")

        if self.price is not None:
            print(f"  Limit Price : {self.price}")
        if self.stop_price is not None:
            print(f"  Stop Price  : {self.stop_price}")

        if self.success:
            print(f"\n  Order ID    : {self.order_id}")
            print(f"  Client OID  : {self.client_order_id}")
            print(f"  Status      : {self.status}")
            print(f"  Executed Qty: {self.executed_qty}")
            if self.avg_price and self.avg_price > 0:
                print(f"  Avg Price   : {self.avg_price}")
            print(f"\n  ✅ Order placed successfully.")
        else:
            print(f"\n  ❌ Order failed.")
            print(f"  Error Code  : {self.error_code}")
            print(f"  Error Msg   : {self.error_message}")

        print(f"{sep}\n")


def _parse_response(
    response: Dict[str, Any],
    symbol: str,
    side: str,
    order_type: str,
    quantity: Decimal,
    price: Optional[Decimal],
    stop_price: Optional[Decimal],
) -> OrderResult:
    """Map a raw Binance order response to an OrderResult."""
    executed_qty_raw = response.get("executedQty", "0")
    avg_price_raw = response.get("avgPrice", "0")

    return OrderResult(
        success=True,
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=quantity,
        order_id=response.get("orderId"),
        client_order_id=response.get("clientOrderId"),
        status=response.get("status"),
        executed_qty=Decimal(executed_qty_raw) if executed_qty_raw else Decimal("0"),
        avg_price=Decimal(avg_price_raw) if avg_price_raw else Decimal("0"),
        price=price,
        stop_price=stop_price,
        raw=response,
    )


class OrderManager:
    """
    High-level order manager — validates inputs, delegates to client,
    and returns structured OrderResult objects.

    Args:
        client: An initialised BinanceFuturesClient instance.
    """

    def __init__(self, client: BinanceFuturesClient):
        self._client = client

    def place(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str | float | Decimal,
        price: Optional[str | float | Decimal] = None,
        stop_price: Optional[str | float | Decimal] = None,
    ) -> OrderResult:
        """
        Validate inputs and place a futures order.

        Args:
            symbol: Trading pair (e.g. 'BTCUSDT').
            side: 'BUY' or 'SELL'.
            order_type: 'MARKET', 'LIMIT', or 'STOP_MARKET'.
            quantity: Order quantity.
            price: Limit price (LIMIT orders only).
            stop_price: Stop trigger price (STOP_MARKET orders only).

        Returns:
            OrderResult with success/failure details.
        """
        # --- Validation ---
        try:
            params = validate_order_params(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_price=stop_price,
            )
        except ValueError as exc:
            logger.warning("Validation failed: %s", exc)
            return OrderResult(
                success=False,
                symbol=str(symbol).upper(),
                side=str(side).upper(),
                order_type=str(order_type).upper(),
                quantity=Decimal("0"),
                error_code=-1,
                error_message=str(exc),
            )

        logger.info(
            "Order validated | %s %s %s qty=%s price=%s stopPrice=%s",
            params["side"],
            params["order_type"],
            params["symbol"],
            params["quantity"],
            params["price"],
            params["stop_price"],
        )

        # --- Placement ---
        try:
            response = self._client.place_order(
                symbol=params["symbol"],
                side=params["side"],
                order_type=params["order_type"],
                quantity=params["quantity"],
                price=params["price"],
                stop_price=params["stop_price"],
            )
        except BinanceAPIError as exc:
            logger.error("Binance API error | code=%s msg=%s", exc.code, exc.message)
            return OrderResult(
                success=False,
                symbol=params["symbol"],
                side=params["side"],
                order_type=params["order_type"],
                quantity=params["quantity"],
                price=params["price"],
                stop_price=params["stop_price"],
                error_code=exc.code,
                error_message=exc.message,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error placing order: %s", exc, exc_info=True)
            return OrderResult(
                success=False,
                symbol=params["symbol"],
                side=params["side"],
                order_type=params["order_type"],
                quantity=params["quantity"],
                price=params["price"],
                stop_price=params["stop_price"],
                error_code=-2,
                error_message=str(exc),
            )

        result = _parse_response(
            response=response,
            symbol=params["symbol"],
            side=params["side"],
            order_type=params["order_type"],
            quantity=params["quantity"],
            price=params["price"],
            stop_price=params["stop_price"],
        )

        logger.info(
            "Order placed successfully | orderId=%s status=%s executedQty=%s avgPrice=%s",
            result.order_id,
            result.status,
            result.executed_qty,
            result.avg_price,
        )

        return result
