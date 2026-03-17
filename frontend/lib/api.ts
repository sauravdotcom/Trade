import { BacktestResult, PerformanceSummary, SignalEnvelope } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export async function fetchLatestSignal(symbol = "NIFTY"): Promise<SignalEnvelope | null> {
  const response = await fetch(`${API_BASE}/signals/latest?symbol=${symbol}`, { cache: "no-store" });
  if (!response.ok) {
    return null;
  }
  return (await response.json()) as SignalEnvelope | null;
}

export async function fetchSignalHistory(limit = 25, symbol = "NIFTY"): Promise<unknown[]> {
  const response = await fetch(`${API_BASE}/signals/history?limit=${limit}&symbol=${symbol}`, { cache: "no-store" });
  if (!response.ok) {
    return [];
  }
  return (await response.json()) as unknown[];
}

export async function runBacktest(payload: {
  symbol: string;
  candles: Array<{
    timestamp: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }>;
}): Promise<BacktestResult | null> {
  const response = await fetch(`${API_BASE}/backtest/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    return null;
  }

  return (await response.json()) as BacktestResult;
}

export async function fetchPerformanceSummary(days = 30): Promise<PerformanceSummary | null> {
  const response = await fetch(`${API_BASE}/performance/summary?days=${days}`, { cache: "no-store" });
  if (!response.ok) {
    return null;
  }
  return (await response.json()) as PerformanceSummary;
}
