import { OptionRow } from "@/lib/types";

interface OIHeatmapProps {
  chain: OptionRow[];
}

export function OIHeatmap({ chain }: OIHeatmapProps) {
  const rows = [...chain]
    .sort((a, b) => b.volume - a.volume)
    .slice(0, 10)
    .map((row) => {
      const dominance = row.call_oi > row.put_oi ? "Call Heavy" : "Put Heavy";
      return {
        ...row,
        dominance
      };
    });

  return (
    <div className="panel-card">
      <div className="panel-title">OI Heatmap</div>
      <div className="heatmap-grid header">
        <div>Strike</div>
        <div>Call OI</div>
        <div>Put OI</div>
        <div>Zone</div>
      </div>

      <div className="heatmap-body">
        {rows.map((row) => (
          <div key={row.strike} className="heatmap-grid">
            <div>{row.strike}</div>
            <div>{row.call_oi.toLocaleString()}</div>
            <div>{row.put_oi.toLocaleString()}</div>
            <div className={row.dominance === "Call Heavy" ? "bearish" : "bullish"}>{row.dominance}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
