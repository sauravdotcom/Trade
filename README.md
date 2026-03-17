# Trade Signal AI (NIFTY / BANKNIFTY)

Production-grade full-stack system for generating live Indian options trading signals with rule-based logic, options chain analytics, and AI reasoning.

## What it does

- Streams live/near-live market snapshots every 3 seconds via broker adapters (Kite, Angel One, Upstox, with robust mock fallback).
- Tracks `NIFTY` and `BANKNIFTY` concurrently through a configurable `WATCHLIST`.
- Enforces NSE trading-session gating (IST, weekdays, holiday-aware, 09:15-15:30 by default).
- Computes options-chain analytics: PCR, OI support/resistance, max pain, gamma levels, liquidity zones, and market regimes.
- Computes technical indicators: VWAP, EMA 9/21, RSI, MACD, ATR, Bollinger Bands.
- Generates actionable trade calls (`BUY_CALL`, `BUY_PUT`, `NO_TRADE`) with confidence and reasons.
- High-conviction mode: new calls only above configured confidence threshold (`MIN_SIGNAL_CONFIDENCE`, default 90).
- Strategy throttling: maximum 4 fresh calls/day (`DAILY_MAX_CALLS`) with cooldown between entries.
- Builds risk plans: entry, stop loss, target 1, target 2, quantity, R:R.
- Live trade management guidance: post-entry hold/scale/exit instructions with reversal/time-stop exits.
- Paper-trade ledger stores each call, its closure, result (WIN/LOSS/BREAKEVEN), and exact PnL.
- Adaptive strategy tuning uses rolling trade outcomes to tighten/relax confidence and cooldown settings.
- Adds AI explanation layer (OpenAI optional) for human-readable signal context.
- Publishes alerts through Telegram, web notifications (browser + Redis channel), and email.
- Supports strategy backtesting using historical candles.
- Includes JWT auth, encrypted broker credential storage, and in-app rate limiting.
- In strict live mode (`ALLOW_MOCK_FALLBACK=false`), no synthetic calls are emitted when live chain data is unavailable.
- Dashboard includes symbol toggle for `NIFTY` / `BANKNIFTY`.

## Architecture

See [ARCHITECTURE.md](/Users/mac/Documents/GrowDash/Trade/ARCHITECTURE.md).

## Folder Structure

```text
Trade/
  backend/
    app/
      api/v1/endpoints/      # Auth, market, signals, backtest, journal, credentials
      core/                  # Settings, security, rate-limit logic
      db/                    # SQLAlchemy base/session
      models/                # Users, signal records, journal, encrypted credentials
      schemas/               # Request/response contracts
      services/              # Data adapters, analysis, indicators, signal, risk, AI, alerts, backtesting, orchestration
      utils/                 # Redis JSON cache + WebSocket manager
      main.py
    tests/
    Dockerfile
    requirements.txt
    .env.example
  frontend/
    app/                     # Next.js app router pages/layout
    components/              # Dashboard widgets
    lib/                     # API client, websocket hook, types
    Dockerfile
    .env.example
  infra/
    aws-deployment.md
  docker-compose.yml
  README.md
  ARCHITECTURE.md
```

## Quick Start (Docker)

1. Copy env templates:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

2. Start stack:

```bash
docker compose up --build
```

3. Open apps:

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## Manual Run

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## API Endpoints

- `GET /api/v1/health`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/token`
- `GET /api/v1/auth/me`
- `POST /api/v1/credentials` (encrypted broker keys)
- `GET /api/v1/credentials`
- `GET /api/v1/market/snapshot`
- `GET /api/v1/signals/latest`
- `GET /api/v1/signals/history`
- `WS /api/v1/signals/ws`
- `GET /api/v1/performance/summary?days=30`
- `GET /api/v1/performance/trades?days=30&limit=200`
- `POST /api/v1/backtest/run`
- `POST /api/v1/journal/entries`
- `GET /api/v1/journal/entries`

## Trading Rule Summary

### Bearish setup -> BUY PUT

- Spot below VWAP
- PCR below 0.8
- Call writing concentration
- Support breakdown
- EMA9 below EMA21

### Bullish setup -> BUY CALL

- Spot above VWAP
- PCR above 1.2
- Put writing concentration
- Resistance breakout
- EMA9 above EMA21

Risk defaults:

- SL = `entry * 0.8`
- Target1 = `entry * 1.3`
- Target2 = `entry * 1.6`
- Position sizing uses `capital * max_risk_per_trade`

Operational constraints:

- `MIN_SIGNAL_CONFIDENCE=90`
- `DAILY_MAX_CALLS=4`
- `CALL_COOLDOWN_MINUTES=35`

Adaptive learning defaults:

- `ADAPTIVE_LEARNING_ENABLED=true`
- `ADAPTIVE_LOOKBACK_DAYS=30`
- `ADAPTIVE_MIN_CLOSED_TRADES=12`
- `ADAPTIVE_LEARNING_INTERVAL_MINUTES=30`
- `ADAPTIVE_CONFIDENCE_FLOOR=88`
- `ADAPTIVE_CONFIDENCE_CEILING=96`

## One-Month Live Paper Test

1. Run the app continuously for 30 days in paper mode.
2. Every generated call is saved in `trade_performance` with open/close timestamps.
3. On exit, pnl amount and pnl % are stored automatically.
4. Strategy controls are auto-tuned from rolling results.
5. Review performance:
   - `GET /api/v1/performance/summary?days=30`
   - `GET /api/v1/performance/trades?days=30`

## Notes on broker APIs

- Public NSE feed is used for session/spot alignment; option-chain public endpoints may intermittently throttle.
- Upstox chain parsing is implemented for authenticated live options data.
- Kite/Angel adapters are wired for spot and can be extended with instrument-map based option chain fetch.
- For production, wire your specific instrument master and quote basket for option-chain contracts.
- Keep `ALLOW_MOCK_FALLBACK=false` in production to prevent synthetic trade calls.

## Performance / Scale Recommendations (10k users)

- Horizontal scale FastAPI (ASGI workers behind ALB/Nginx).
- Use Redis pub/sub for fan-out and sticky-free WebSocket delivery.
- Move orchestration to dedicated worker pod and publish signals to Redis stream.
- Add read replicas and partition signal history tables by day/week.
- Add CloudWatch + Prometheus alerts on signal loop latency and WS fan-out lag.

## Disclaimer

This project is an educational and engineering template. It is not financial advice. Validate strategy behavior with real historical data and exchange-compliant risk controls before live deployment.
