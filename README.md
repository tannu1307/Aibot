# Binance Futures Testnet Trading Bot

A clean, structured Python CLI application for placing orders on the **Binance USDT-M Futures Testnet**.

## Features

- **Market**, **Limit**, and **Stop-Market** orders (bonus order type ✓)
- **BUY / SELL** support
- Full **input validation** with descriptive error messages
- **Structured logging** to both file and console
- Clean separation of concerns: `client → orders → CLI`
- No third-party Binance SDK required — uses plain `requests`

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py
│   ├── client.py          # Binance REST client (signing, requests, error mapping)
│   ├── orders.py          # OrderManager + OrderResult (business logic layer)
│   ├── validators.py      # All input validation logic
│   └── logging_config.py  # File + console logging setup
├── cli.py                 # CLI entry point (argparse)
├── logs/                  # Log files (auto-created)
├── README.md
└── requirements.txt
```

---

## Setup

### 1. Get Testnet Credentials

1. Visit [https://testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Log in / register (GitHub auth supported)
3. Navigate to **API Management** and generate a key pair
4. Copy your **API Key** and **Secret Key**

### 2. Install Dependencies

```bash
# Python 3.8+ required
pip install -r requirements.txt
```

### 3. Set Environment Variables

```bash
# Linux / macOS
export BINANCE_API_KEY="your_testnet_api_key_here"
export BINANCE_API_SECRET="your_testnet_api_secret_here"

# Windows (PowerShell)
$env:BINANCE_API_KEY="your_testnet_api_key_here"
$env:BINANCE_API_SECRET="your_testnet_api_secret_here"
```

> ⚠️ Never commit credentials to source control. Use a `.env` file or secret manager in production.

---

## How to Run

### Test Connectivity

```bash
python cli.py ping
```

Expected output:
```
✅  Binance Futures Testnet is reachable.
    Server time: 1736933581423 ms
```

### View Account Balances

```bash
python cli.py account
```

### Place a Market Order

```bash
python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

### Place a Limit Order

```bash
python cli.py place --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 44000
```

### Place a Stop-Market Order (Bonus)

```bash
python cli.py place --symbol ETHUSDT --side BUY --type STOP_MARKET --quantity 0.05 --stop-price 2200
```

### Full Help

```bash
python cli.py --help
python cli.py place --help
```

---

## Example Output

```
┌─ ORDER REQUEST ─────────────────────────────────────┐
│  Symbol     : BTCUSDT                               │
│  Side       : BUY                                   │
│  Type       : MARKET                                │
│  Quantity   : 0.001                                 │
└─────────────────────────────────────────────────────┘

────────────────────────────────────────────────────────
  ORDER SUBMITTED ✓
────────────────────────────────────────────────────────
  Symbol      : BTCUSDT
  Side        : BUY
  Type        : MARKET
  Quantity    : 0.001

  Order ID    : 4751382910
  Client OID  : x-HNA2BFMY-abc123
  Status      : FILLED
  Executed Qty: 0.001
  Avg Price   : 42583.10

  ✅ Order placed successfully.
────────────────────────────────────────────────────────
```

---

## Logging

Logs are written to `logs/trading_bot_YYYYMMDD.log`.

- **File handler**: `DEBUG` level — full request/response details, parameters (signature omitted)
- **Console handler**: `INFO` level — clean human-readable output

Log file includes:
- Every API request (method, URL, params)
- Every API response (status code, truncated body)
- Validation failures with reason
- Order lifecycle events (validated → placed → result)
- Any errors or exceptions with stack traces

---

## Validation Rules

| Field | Rule |
|-------|------|
| symbol | Non-empty alphanumeric string |
| side | Must be `BUY` or `SELL` (case-insensitive) |
| type | Must be `MARKET`, `LIMIT`, or `STOP_MARKET` |
| quantity | Positive decimal number |
| price | Required for `LIMIT`; must not be supplied for `MARKET` |
| stop_price | Required for `STOP_MARKET` |

---

## Error Handling

| Error type | Handling |
|------------|----------|
| Missing credentials | Clear message + `sys.exit(1)` |
| Invalid CLI input | Validation error printed; order not sent |
| Binance API error (4xx) | Code + message extracted from JSON body |
| Network failure | Retried 3× with backoff; error reported |
| Unexpected exception | Logged with stack trace; graceful failure returned |

---

## Assumptions

- **Testnet only**: The base URL is hardcoded to `https://testnet.binancefuture.com`. Swap `TESTNET_BASE_URL` in `bot/client.py` for mainnet use (with real funds — use with caution).
- **BOTH position side**: Orders use `positionSide=BOTH` (hedge mode not required on testnet).
- **Quantity precision**: Validation applies soft minimum guards. Binance enforces exact `LOT_SIZE` filters per symbol — if you hit a precision error, adjust your quantity to match the symbol's step size.
- **Time sync**: Requests use local system time. If you receive `-1021 INVALID_TIMESTAMP` errors, ensure your system clock is accurate (NTP sync recommended).

---

## Requirements

```
requests>=2.31.0
urllib3>=2.0.0
```

Python 3.8 or higher required.
