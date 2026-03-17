import clsx from "clsx";

import { TradeSignal } from "@/lib/types";

interface SignalCardProps {
  signal: TradeSignal;
  aiReasoning: string;
}

export function SignalCard({ signal, aiReasoning }: SignalCardProps) {
  const sideClass = signal.signal_type === "BUY_CALL" ? "bullish" : signal.signal_type === "BUY_PUT" ? "bearish" : "neutral";
  const risk = signal.risk_plan;
  const lifecycle = signal.lifecycle_status ?? "NO_TRADE";

  return (
    <section className={clsx("panel-card", "signal-card", sideClass)}>
      <div className="panel-title">Live Trade Signal</div>
      <h2>{signal.instrument}</h2>
      <div className="signal-type">{signal.signal_type}</div>
      <div className="confidence">Confidence: {signal.confidence}%</div>
      <div className="signal-state">State: {lifecycle.replaceAll("_", " ")}</div>
      {typeof signal.daily_calls_used === "number" ? <div className="signal-state">Calls Today: {signal.daily_calls_used}</div> : null}
      {typeof signal.unrealized_pnl_pct === "number" ? (
        <div className={signal.unrealized_pnl_pct >= 0 ? "signal-state bullish" : "signal-state bearish"}>
          Unrealized PnL: {signal.unrealized_pnl_pct}%
        </div>
      ) : null}
      {typeof signal.current_option_price === "number" ? (
        <div className="signal-state">Option Price: {signal.current_option_price}</div>
      ) : null}

      {risk ? (
        <div className="signal-levels">
          <div>
            <span>Entry</span>
            <strong>{risk.entry}</strong>
          </div>
          <div>
            <span>Stop Loss</span>
            <strong>{risk.stop_loss}</strong>
          </div>
          <div>
            <span>Target 1</span>
            <strong>{risk.target_1}</strong>
          </div>
          <div>
            <span>Target 2</span>
            <strong>{risk.target_2}</strong>
          </div>
          <div>
            <span>Quantity</span>
            <strong>{risk.quantity}</strong>
          </div>
          <div>
            <span>R:R</span>
            <strong>{risk.risk_reward}</strong>
          </div>
        </div>
      ) : (
        <p className="muted">No executable trade at this tick.</p>
      )}

      <p className="reason">{signal.reason}</p>
      {signal.guidance ? <p className="reason">Guidance: {signal.guidance}</p> : null}
      {signal.exit_guidance ? <p className="reason">Exit Plan: {signal.exit_guidance}</p> : null}
      <p className="ai-reason">AI: {aiReasoning}</p>
    </section>
  );
}
