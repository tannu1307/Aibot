#!/usr/bin/env python3
"""
Binance Futures Testnet Trading Bot — CLI Entry Point

Usage examples:
  # Market BUY
  python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

  # Limit SELL
  python cli.py place --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 70000

  # Stop-Market BUY
  python cli.py place --symbol ETHUSDT --side BUY --type STOP_MARKET --quantity 0.01 --stop-price 3500

  # Check server time
  python cli.py ping

  # Show account balances
  python cli.py account
"""

from __future__ import annotations

import argparse
import os
import sys

from bot.client import BinanceFuturesClient, BinanceAPIError
from bot.logging_config import setup_logging, get_logger
from bot.orders import OrderManager

# ── Initialise logging first so every module can use it ──────────────
setup_logging(log_dir="logs")
logger = get_logger("cli")


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _get_client() -> BinanceFuturesClient:
    """
    Build the Binance client from environment variables.

    Required env vars:
      BINANCE_API_KEY     — your Testnet API key
      BINANCE_API_SECRET  — your Testnet API secret
    """
    api_key = os.getenv("BINANCE_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_API_SECRET", "").strip()

    if not api_key or not api_secret:
        print(
            "\n❌  Missing API credentials.\n"
            "    Set the following environment variables before running:\n\n"
            "      export BINANCE_API_KEY=<your_testnet_key>\n"
            "      export BINANCE_API_SECRET=<your_testnet_secret>\n"
        )
        sys.exit(1)

    return BinanceFuturesClient(api_key=api_key, api_secret=api_secret)


# ─────────────────────────────────────────────────────────────────────
# Sub-command handlers
# ─────────────────────────────────────────────────────────────────────

def cmd_ping(args: argparse.Namespace) -> None:  # noqa: ARG001
    """Test connectivity and print Binance server time."""
    client = _get_client()
    try:
        server_time = client.get_server_time()
        print(f"\n✅  Binance Futures Testnet is reachable.")
        print(f"    Server time: {server_time} ms\n")
        logger.info("Ping successful | serverTime=%s", server_time)
    except Exception as exc:
        print(f"\n❌  Ping failed: {exc}\n")
        logger.error("Ping failed: %s", exc)
        sys.exit(1)


def cmd_account(args: argparse.Namespace) -> None:  # noqa: ARG001
    """Display USDT balance and open positions."""
    client = _get_client()
    try:
        account = client.get_account()
    except BinanceAPIError as exc:
        print(f"\n❌  Could not fetch account: {exc}\n")
        logger.error("Account fetch failed: %s", exc)
        sys.exit(1)

    # Print USDT balance
    sep = "─" * 50
    print(f"\n{sep}")
    print("  ACCOUNT OVERVIEW")
    print(sep)
    for asset in account.get("assets", []):
        if asset.get("asset") == "USDT":
            print(f"  USDT Balance  : {asset.get('walletBalance', 'N/A')}")
            print(f"  Unrealised PnL: {asset.get('unrealizedProfit', 'N/A')}")
            break

    positions = [
        p for p in account.get("positions", [])
        if float(p.get("positionAmt", 0)) != 0
    ]
    if positions:
        print(f"\n  Open Positions ({len(positions)}):")
        for pos in positions:
            print(
                f"    {pos['symbol']} | amt={pos['positionAmt']} "
                f"| entryPrice={pos['entryPrice']} | pnl={pos['unrealizedProfit']}"
            )
    else:
        print("\n  No open positions.")
    print(f"{sep}\n")
    logger.info("Account info retrieved successfully.")


def cmd_place(args: argparse.Namespace) -> None:
    """Place a new futures order."""
    client = _get_client()
    manager = OrderManager(client)

    # Echo the request back to the user before sending
    print("\n┌─ ORDER REQUEST ─────────────────────────────────────┐")
    print(f"│  Symbol     : {args.symbol.upper():<38}│")
    print(f"│  Side       : {args.side.upper():<38}│")
    print(f"│  Type       : {args.type.upper():<38}│")
    print(f"│  Quantity   : {str(args.quantity):<38}│")
    if args.price is not None:
        print(f"│  Price      : {str(args.price):<38}│")
    if args.stop_price is not None:
        print(f"│  Stop Price : {str(args.stop_price):<38}│")
    print("└─────────────────────────────────────────────────────┘")

    result = manager.place(
        symbol=args.symbol,
        side=args.side,
        order_type=args.type,
        quantity=args.quantity,
        price=args.price,
        stop_price=args.stop_price,
    )

    result.print_summary()

    if not result.success:
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────
# Argument parser
# ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="Binance Futures Testnet Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # ── ping ──────────────────────────────────────────────────────────
    ping_p = sub.add_parser("ping", help="Test connectivity to Binance Testnet.")
    ping_p.set_defaults(func=cmd_ping)

    # ── account ───────────────────────────────────────────────────────
    acct_p = sub.add_parser("account", help="Show account balances and open positions.")
    acct_p.set_defaults(func=cmd_account)

    # ── place ─────────────────────────────────────────────────────────
    place_p = sub.add_parser("place", help="Place a market, limit, or stop-market order.")
    place_p.set_defaults(func=cmd_place)

    place_p.add_argument(
        "--symbol", "-s",
        required=True,
        metavar="SYMBOL",
        help="Trading pair, e.g. BTCUSDT",
    )
    place_p.add_argument(
        "--side",
        required=True,
        choices=["BUY", "SELL", "buy", "sell"],
        metavar="SIDE",
        help="Order side: BUY or SELL",
    )
    place_p.add_argument(
        "--type", "-t",
        required=True,
        choices=["MARKET", "LIMIT", "STOP_MARKET", "market", "limit", "stop_market"],
        metavar="TYPE",
        help="Order type: MARKET | LIMIT | STOP_MARKET",
    )
    place_p.add_argument(
        "--quantity", "-q",
        required=True,
        type=float,
        metavar="QTY",
        help="Order quantity (in base asset units)",
    )
    place_p.add_argument(
        "--price", "-p",
        type=float,
        default=None,
        metavar="PRICE",
        help="Limit price (required for LIMIT orders)",
    )
    place_p.add_argument(
        "--stop-price",
        type=float,
        default=None,
        metavar="STOP_PRICE",
        dest="stop_price",
        help="Stop trigger price (required for STOP_MARKET orders)",
    )

    return parser


# ─────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logger.debug("CLI args: %s", vars(args))
    args.func(args)


if __name__ == "__main__":
    main()
