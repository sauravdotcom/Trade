# System Architecture

## Logical Components

1. Market Data Service
- Connects to Zerodha Kite, Angel One SmartAPI, Upstox.
- Pulls spot + option chain every 3 seconds.
- Falls back to mock feed for resilience.
- Supports multi-symbol watchlist (default: NIFTY, BANKNIFTY).

2. Options Analysis Engine
- PCR, max pain, OI support/resistance.
- Gamma concentrations, liquidity zones.
- Regime labeling (call/put writing, short covering, long buildup).

3. Technical Indicator Engine
- VWAP, EMA 9/21, RSI, MACD, ATR, Bollinger.
- Uses rolling in-memory bars for live operation.

4. Signal Generator
- Applies bullish/bearish rules.
- Returns signal type, confidence score, textual reason.

5. Risk Manager
- Entry/SL/targets, quantity sizing, risk-reward.

6. AI Reasoning Layer
- Optional OpenAI model to generate concise trade rationale.
- Falls back to deterministic explanation if key is absent.

7. Alert Service
- Telegram, email, and Redis/web notification fan-out.

8. Backtesting Engine
- Candle-driven replay.
- Win rate, net PnL, drawdown outputs.

9. Frontend Dashboard (Next.js)
- Left panel: spot/PCR/max pain/OI heatmap.
- Center: live chart + indicators + regimes.
- Right: signal card + confidence + recent signal history.

## Runtime Flow

1. Orchestrator loop wakes every 3 seconds.
2. Fetches snapshot from best available adapter.
3. Runs options + indicator computations.
4. Generates rule-based signal and risk plan.
5. Generates AI explanation.
6. Stores payload in Redis and optional DB signal table.
7. Broadcasts via WebSocket to all connected clients.
8. Sends alerts for actionable signals.

## Data Stores

- PostgreSQL
  - users
  - broker_credentials (encrypted fields)
  - signal_records
  - trade_journal
- Redis
  - latest signal cache
  - alert pub/sub channel

## Security

- JWT authentication.
- Password hashing with bcrypt.
- Symmetric encryption (`Fernet`) for broker API secrets at rest.
- IP rate limiting middleware.

## Scalability Blueprint

- Split into microservices for market-ingestion, signal-engine, api-gateway.
- Redis stream or Kafka for event-driven signal transport.
- WebSocket gateway tier for 10k+ concurrent users.
- Auto-scaling with CPU + event loop lag metrics.
