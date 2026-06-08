"""
Low-level Binance Futures Testnet REST client.

Handles:
  - HMAC-SHA256 request signing
  - Timestamp synchronisation
  - HTTP request execution with retries
  - Structured logging of every request/response
  - Mapping of Binance API error codes to meaningful exceptions
"""

from __future__ import annotations

import hashlib
import hmac
import time
from decimal import Decimal
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .logging_config import get_logger

logger = get_logger("client")

TESTNET_BASE_URL = "https://testnet.binancefuture.com"

# Binance API paths
_ENDPOINTS = {
    "server_time": "/fapi/v1/time",
    "exchange_info": "/fapi/v1/exchangeInfo",
    "new_order": "/fapi/v1/order",
    "account": "/fapi/v2/account",
}

# HTTP retry config — retries on transient network errors, NOT on 4xx/5xx
_RETRY_CONFIG = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST", "DELETE"],
)


class BinanceAPIError(Exception):
    """Raised when Binance returns a structured error payload."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Binance API error {code}: {message}")


class BinanceFuturesClient:
    """
    Thin wrapper around the Binance USDT-M Futures REST API (Testnet).

    Args:
        api_key: Your Binance Futures Testnet API key.
        api_secret: Your Binance Futures Testnet API secret.
        base_url: Base URL (defaults to Testnet).
        recv_window: Maximum milliseconds the request is valid for (default 5000).
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = TESTNET_BASE_URL,
        recv_window: int = 5000,
    ):
        if not api_key or not api_secret:
            raise ValueError("Both api_key and api_secret must be non-empty strings.")

        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._recv_window = recv_window

        self._session = self._build_session()
        logger.info("BinanceFuturesClient initialised | base_url=%s", self._base_url)

    # ------------------------------------------------------------------
    # Session / transport
    # ------------------------------------------------------------------

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        adapter = HTTPAdapter(max_retries=_RETRY_CONFIG)
        session.mount("https://", adapter)
        session.headers.update(
            {
                "X-MBX-APIKEY": self._api_key,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )
        return session

    # ------------------------------------------------------------------
    # Signing helpers
    # ------------------------------------------------------------------

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Append HMAC-SHA256 signature to the parameter dict (in-place + return)."""
        query_string = urlencode(params)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    def _timestamp(self) -> int:
        """Return current UTC timestamp in milliseconds."""
        return int(time.time() * 1000)

    # ------------------------------------------------------------------
    # Core request dispatcher
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute an HTTP request and return the parsed JSON response.

        Args:
            method: HTTP verb ('GET', 'POST', 'DELETE').
            endpoint: API path (e.g. '/fapi/v1/order').
            params: Query / body parameters.
            signed: Whether to add timestamp + HMAC signature.

        Returns:
            Parsed response dict.

        Raises:
            BinanceAPIError: On Binance-level errors.
            requests.RequestException: On network/transport errors.
        """
        params = params or {}

        if signed:
            params["timestamp"] = self._timestamp()
            params["recvWindow"] = self._recv_window
            self._sign(params)

        url = f"{self._base_url}{endpoint}"

        logger.debug(
            "→ REQUEST  method=%s url=%s params=%s",
            method,
            url,
            {k: v for k, v in params.items() if k != "signature"},  # omit signature
        )

        try:
            if method == "GET":
                response = self._session.get(url, params=params, timeout=10)
            elif method == "POST":
                response = self._session.post(url, data=params, timeout=10)
            elif method == "DELETE":
                response = self._session.delete(url, params=params, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except requests.ConnectionError as exc:
            logger.error("Network connection error: %s", exc)
            raise
        except requests.Timeout as exc:
            logger.error("Request timed out: %s", exc)
            raise

        logger.debug(
            "← RESPONSE status=%s body=%s",
            response.status_code,
            response.text[:500],  # truncate large bodies
        )

        try:
            data = response.json()
        except ValueError:
            logger.error("Non-JSON response (status %s): %s", response.status_code, response.text)
            response.raise_for_status()
            raise

        # Binance returns error details in the body even on 4xx
        if isinstance(data, dict) and "code" in data and data["code"] != 200:
            raise BinanceAPIError(code=data["code"], message=data.get("msg", "Unknown error"))

        response.raise_for_status()
        return data

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def get_server_time(self) -> int:
        """Return Binance server time in milliseconds (unsigned)."""
        data = self._request("GET", _ENDPOINTS["server_time"])
        return data["serverTime"]

    def get_exchange_info(self) -> Dict[str, Any]:
        """Return exchange info including all symbol trading rules."""
        return self._request("GET", _ENDPOINTS["exchange_info"])

    def get_account(self) -> Dict[str, Any]:
        """Return account balances and positions (signed)."""
        return self._request("GET", _ENDPOINTS["account"], signed=True)

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        time_in_force: str = "GTC",
    ) -> Dict[str, Any]:
        """
        Submit a new futures order.

        Args:
            symbol: Trading pair (e.g. 'BTCUSDT').
            side: 'BUY' or 'SELL'.
            order_type: 'MARKET', 'LIMIT', or 'STOP_MARKET'.
            quantity: Order quantity.
            price: Limit price (required for LIMIT orders).
            stop_price: Stop trigger price (required for STOP_MARKET).
            time_in_force: 'GTC' | 'IOC' | 'FOK' (LIMIT only).

        Returns:
            Binance order response dict.
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": str(quantity),
        }

        if order_type == "LIMIT":
            params["price"] = str(price)
            params["timeInForce"] = time_in_force
        elif order_type == "STOP_MARKET":
            params["stopPrice"] = str(stop_price)

        logger.info(
            "Placing order | symbol=%s side=%s type=%s qty=%s price=%s stopPrice=%s",
            symbol,
            side,
            order_type,
            quantity,
            price,
            stop_price,
        )

        return self._request("POST", _ENDPOINTS["new_order"], params=params, signed=True)
