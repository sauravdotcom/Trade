"use client";

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface SpotPoint {
  t: string;
  spot: number;
  vwap: number;
}

interface LiveChartProps {
  data: SpotPoint[];
}

export function LiveChart({ data }: LiveChartProps) {
  return (
    <div className="panel-card chart-card">
      <div className="panel-title">Live Spot vs VWAP</div>
      <div className="chart-wrapper">
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <XAxis dataKey="t" hide />
            <YAxis domain={["auto", "auto"]} width={70} />
            <Tooltip
              contentStyle={{
                background: "#1f2937",
                border: "1px solid #334155",
                borderRadius: "10px"
              }}
            />
            <Line type="monotone" dataKey="spot" stroke="#f9a826" strokeWidth={3} dot={false} />
            <Line type="monotone" dataKey="vwap" stroke="#23c9a9" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
