export type SignalType = "BUY_CALL" | "BUY_PUT" | "NO_TRADE";

export interface OptionRow {
  strike: number;
  call_oi: number;
  put_oi: number;
  call_oi_change: number;
  put_oi_change: number;
  call_ltp: number;
  put_ltp: number;
  call_ltp_change: number;
  put_ltp_change: number;
  iv: number;
  volume: number;
  gamma: number;
}

export interface MarketSnapshot {
  symbol: string;
  spot_price: number;
  timestamp: string;
  chain: OptionRow[];
}

export interface OptionAnalysis {
  pcr: number;
  max_pain: number;
  support_strike: number;
  resistance_strike: number;
  gamma_levels: number[];
  liquidity_zones: number[];
  regimes: string[];
}

export interface IndicatorSnapshot {
  vwap: number;
  ema_9: number;
  ema_21: number;
  rsi: number;
  macd: number;
  macd_signal: number;
  atr: number;
  bollinger_upper: number;
  bollinger_lower: number;
}

export interface RiskPlan {
  entry: number;
  stop_loss: number;
  target_1: number;
  target_2: number;
  quantity: number;
  risk_reward: number;
}

export interface TradeSignal {
  symbol: string;
  instrument: string;
  signal_type: SignalType;
  confidence: number;
  reason: string;
  lifecycle_status?: "NO_TRADE" | "NEW_CALL" | "MANAGE" | "TARGET1_BOOKED" | "EXIT_NOW" | "TARGET2_HIT";
  guidance?: string | null;
  exit_guidance?: string | null;
  unrealized_pnl_pct?: number | null;
  current_option_price?: number | null;
  daily_calls_used?: number | null;
  risk_plan?: RiskPlan | null;
}

export interface SignalEnvelope {
  timestamp: string;
  snapshot: MarketSnapshot;
  analysis: OptionAnalysis;
  indicators: IndicatorSnapshot;
  signal: TradeSignal;
  ai_reasoning: string;
}

export interface BacktestResult {
  symbol: string;
  trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  net_pnl: number;
  max_drawdown: number;
}

export interface PerformanceSummary {
  lookback_days: number;
  total_calls: number;
  open_trades: number;
  closed_trades: number;
  wins: number;
  losses: number;
  breakeven: number;
  win_rate: number;
  net_pnl: number;
  avg_pnl_per_trade: number;
  avg_pnl_pct: number;
  profit_factor: number;
  adaptive_min_confidence: number;
  adaptive_cooldown_minutes: number;
  updated_at: string;
}
