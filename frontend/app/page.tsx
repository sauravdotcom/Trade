"use client";

import dayjs from "dayjs";
import { useState } from "react";
import useSWR from "swr";

import { LiveChart } from "@/components/LiveChart";
import { MetricTile } from "@/components/MetricTile";
import { OIHeatmap } from "@/components/OIHeatmap";
import { SignalCard } from "@/components/SignalCard";
import { fetchPerformanceSummary, fetchSignalHistory } from "@/lib/api";
import { useLiveSignal } from "@/lib/useLiveSignal";

export default function Home() {
  const [selectedSymbol, setSelectedSymbol] = useState<"NIFTY" | "BANKNIFTY">("NIFTY");
  const { payload, connected, history, latestSpot } = useLiveSignal(selectedSymbol);
  const { data: signalHistory } = useSWR(["signal-history", selectedSymbol], () => fetchSignalHistory(12, selectedSymbol), {
    refreshInterval: 30000,
    revalidateOnFocus: false
  });
  const { data: perfSummary } = useSWR("performance-summary", () => fetchPerformanceSummary(30), {
    refreshInterval: 45000,
    revalidateOnFocus: false
  });

  if (!payload) {
    return <main className="loading">Connecting to live market feed...</main>;
  }

  const { snapshot, analysis, indicators, signal, ai_reasoning } = payload;

  return (
    <main className="dashboard-root">
      <header className="dashboard-header">
        <div>
          <h1>Indian Options Signal Console</h1>
          <p>NIFTY / BANKNIFTY | Refresh every 3 seconds | Latency target &lt; 2s</p>
        </div>
        <div className="header-actions">
          <div className="symbol-toggle">
            {(["NIFTY", "BANKNIFTY"] as const).map((symbol) => (
              <button
                key={symbol}
                className={selectedSymbol === symbol ? "active" : ""}
                onClick={() => setSelectedSymbol(symbol)}
              >
                {symbol}
              </button>
            ))}
          </div>
          <div className={connected ? "status live" : "status stale"}>{connected ? "LIVE" : "RECONNECTING"}</div>
        </div>
      </header>

      <section className="dashboard-grid">
        <aside className="left-panel">
          <MetricTile label="Index" value={snapshot.symbol} />
          <MetricTile label="Spot" value={latestSpot.toFixed(2)} />
          <MetricTile
            label="PCR"
            value={analysis.pcr.toFixed(2)}
            tone={analysis.pcr > 1.2 ? "bull" : analysis.pcr < 0.8 ? "bear" : "neutral"}
          />
          <MetricTile label="Max Pain" value={analysis.max_pain} />
          <MetricTile label="Support" value={analysis.support_strike} tone="bull" />
          <MetricTile label="Resistance" value={analysis.resistance_strike} tone="bear" />

          <OIHeatmap chain={snapshot.chain} />
        </aside>

        <section className="center-panel">
          <LiveChart data={history} />

          <div className="panel-card">
            <div className="panel-title">Indicator Engine</div>
            <div className="indicator-grid">
              <MetricTile label="VWAP" value={indicators.vwap.toFixed(2)} />
              <MetricTile label="EMA9" value={indicators.ema_9.toFixed(2)} />
              <MetricTile label="EMA21" value={indicators.ema_21.toFixed(2)} />
              <MetricTile label="RSI" value={indicators.rsi.toFixed(2)} />
              <MetricTile label="MACD" value={indicators.macd.toFixed(2)} />
              <MetricTile label="ATR" value={indicators.atr.toFixed(2)} />
              <MetricTile label="BB Upper" value={indicators.bollinger_upper.toFixed(2)} />
              <MetricTile label="BB Lower" value={indicators.bollinger_lower.toFixed(2)} />
            </div>
          </div>

          <div className="panel-card">
            <div className="panel-title">OI Regime Classification</div>
            <div className="regime-tags">
              {analysis.regimes.map((regime) => (
                <span key={regime}>{regime.replaceAll("_", " ")}</span>
              ))}
            </div>
          </div>
        </section>

        <aside className="right-panel">
          <SignalCard signal={signal} aiReasoning={ai_reasoning} />

          <div className="panel-card">
            <div className="panel-title">30D Paper Performance</div>
            {perfSummary ? (
              <div className="perf-grid">
                <MetricTile label="Calls" value={perfSummary.total_calls} />
                <MetricTile label="Closed" value={perfSummary.closed_trades} />
                <MetricTile label="Win Rate" value={`${perfSummary.win_rate}%`} tone={perfSummary.win_rate >= 60 ? "bull" : "bear"} />
                <MetricTile label="Net PnL" value={perfSummary.net_pnl.toFixed(2)} tone={perfSummary.net_pnl >= 0 ? "bull" : "bear"} />
                <MetricTile label="Avg PnL %" value={perfSummary.avg_pnl_pct.toFixed(2)} tone={perfSummary.avg_pnl_pct >= 0 ? "bull" : "bear"} />
                <MetricTile label="Profit Factor" value={perfSummary.profit_factor.toFixed(2)} tone={perfSummary.profit_factor >= 1.2 ? "bull" : "bear"} />
                <MetricTile label="Adaptive Conf" value={perfSummary.adaptive_min_confidence.toFixed(0)} />
                <MetricTile label="Adaptive Cooldown" value={`${perfSummary.adaptive_cooldown_minutes}m`} />
              </div>
            ) : (
              <p className="muted">Performance summary not available yet.</p>
            )}
          </div>

          <div className="panel-card">
            <div className="panel-title">Recent Signals</div>
            <div className="history-list">
              {Array.isArray(signalHistory) && signalHistory.length > 0 ? (
                signalHistory.map((item: any) => (
                  <div className="history-item" key={item.id}>
                    <strong>{item.instrument}</strong>
                    <span>{item.signal_type}</span>
                    <span>{item.confidence}%</span>
                    <span>{dayjs(item.created_at).format("HH:mm:ss")}</span>
                  </div>
                ))
              ) : (
                <p className="muted">Signal history is not available yet.</p>
              )}
            </div>
          </div>
        </aside>
      </section>
    </main>
  );
}
