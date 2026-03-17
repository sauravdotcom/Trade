"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { fetchLatestSignal } from "@/lib/api";
import { SignalEnvelope } from "@/lib/types";

const BASE_WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/api/v1/signals/ws";

interface SpotPoint {
  t: string;
  spot: number;
  vwap: number;
}

function notifySignal(signal: SignalEnvelope): void {
  if (typeof window === "undefined") {
    return;
  }

  if (signal.signal.signal_type === "NO_TRADE" || !signal.signal.risk_plan) {
    return;
  }

  if (Notification.permission === "granted") {
    const rp = signal.signal.risk_plan;
    new Notification(`${signal.signal.instrument} ${signal.signal.signal_type}`, {
      body: `Entry ${rp.entry}, SL ${rp.stop_loss}, T1 ${rp.target_1}`
    });
  }
}

export function useLiveSignal(symbol: string) {
  const [payload, setPayload] = useState<SignalEnvelope | null>(null);
  const [connected, setConnected] = useState(false);
  const [history, setHistory] = useState<SpotPoint[]>([]);
  const lastNotifiedRef = useRef<string>("");

  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let unmounted = false;

    const seed = async () => {
      const latest = await fetchLatestSignal(symbol);
      if (!latest || unmounted) {
        return;
      }
      setPayload(latest);
      setHistory([{ t: latest.timestamp, spot: latest.snapshot.spot_price, vwap: latest.indicators.vwap }]);
    };

    const connect = () => {
      socket = new WebSocket(`${BASE_WS_URL}?symbol=${symbol}`);

      socket.onopen = () => setConnected(true);
      socket.onclose = () => {
        setConnected(false);
        if (!unmounted) {
          reconnectTimer = setTimeout(connect, 1500);
        }
      };

      socket.onmessage = (event) => {
        const data = JSON.parse(event.data) as SignalEnvelope;
        if (data.snapshot.symbol !== symbol) {
          return;
        }
        setPayload(data);

        setHistory((prev) => {
          const next = [...prev, { t: data.timestamp, spot: data.snapshot.spot_price, vwap: data.indicators.vwap }];
          return next.slice(-120);
        });

        const currentSignal = `${data.signal.instrument}:${data.signal.signal_type}:${data.timestamp}`;
        if (lastNotifiedRef.current !== currentSignal) {
          notifySignal(data);
          lastNotifiedRef.current = currentSignal;
        }
      };
    };

    seed();
    connect();

    return () => {
      unmounted = true;
      socket?.close();
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
    };
  }, [symbol]);

  useEffect(() => {
    if (typeof window !== "undefined" && Notification.permission === "default") {
      Notification.requestPermission().catch(() => undefined);
    }
  }, []);

  const latestSpot = useMemo(() => payload?.snapshot.spot_price ?? 0, [payload]);

  return {
    payload,
    connected,
    history,
    latestSpot
  };
}
