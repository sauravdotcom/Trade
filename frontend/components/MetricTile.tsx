import clsx from "clsx";

interface MetricTileProps {
  label: string;
  value: string | number;
  tone?: "neutral" | "bull" | "bear";
}

export function MetricTile({ label, value, tone = "neutral" }: MetricTileProps) {
  return (
    <div className={clsx("metric-tile", tone)}>
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
    </div>
  );
}
