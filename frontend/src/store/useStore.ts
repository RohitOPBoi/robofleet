import { useEffect, useRef, useState } from "react";
import type {
  Alert,
  Coordinate,
  DynamicKPIs,
  EnvironmentDisclosure,
  Event,
  HelloPayload,
  Order,
  Robot,
  StaticWorld,
  WorldSnapshot,
  WsEnvelope,
} from "../types/generated";
import { fetchEnvironment } from "../services/api";

export interface StoreState {
  connected: boolean;
  hello: HelloPayload | null;
  staticWorld: StaticWorld | null;
  snapshot: WorldSnapshot | null;
  robots: Record<string, Robot>;
  orders: Record<string, Order>;
  alerts: Alert[];
  kpis: DynamicKPIs;
  recentEvents: Event[];
  tick: number;
  simTimeMs: number;
  lastSeq: number;
  isPaused: boolean;
  speedMultiplier: number;
  theme: "dark" | "light";
  selectedRobotId: string | null;
  selectedOrderId: string | null;
  isEnvironmentModalOpen: boolean;
  isEStopModalOpen: boolean;
  blockModeActive: boolean;
  selectedCellsToBlock: Coordinate[];
  activeOverlays: {
    showFlowArrows: boolean;
    showZones: boolean;
    showLabels: boolean;
    showCongestion: boolean;
  };
  environmentDisclosure: EnvironmentDisclosure | null;
}

const initialKPIs: DynamicKPIs = {
  throughput_orders_per_hr: 0,
  queue_depth: 0,
  at_risk_orders: 0,
  fleet_utilization: 0,
  active_alerts_count: 0,
  robots_moving: 0,
  robots_idle: 0,
  robots_charging: 0,
  robots_faulted: 0,
  completed_orders_total: 0,
};

let globalState: StoreState = {
  connected: false,
  hello: null,
  staticWorld: null,
  snapshot: null,
  robots: {},
  orders: {},
  alerts: [],
  kpis: initialKPIs,
  recentEvents: [],
  tick: 0,
  simTimeMs: 0,
  lastSeq: 0,
  isPaused: false,
  speedMultiplier: 1.0,
  theme: "dark",
  selectedRobotId: null,
  selectedOrderId: null,
  isEnvironmentModalOpen: false,
  isEStopModalOpen: false,
  blockModeActive: false,
  selectedCellsToBlock: [],
  activeOverlays: {
    showFlowArrows: true,
    showZones: true,
    showLabels: true,
    showCongestion: false,
  },
  environmentDisclosure: null,
};

const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((listener) => listener());
}

export function updateStore(updater: (prev: StoreState) => StoreState) {
  globalState = updater(globalState);
  notify();
}

export function setStore(patch: Partial<StoreState>) {
  globalState = { ...globalState, ...patch };
  notify();
}

export function useStore(): StoreState {
  const [, setTick] = useState(0);

  useEffect(() => {
    const listener = () => setTick((t) => t + 1);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);

  return globalState;
}

// WebSocket Connection Manager singleton hook
export function useWebSocketConnection() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const backoffMsRef = useRef(500);

  useEffect(() => {
    // Initial fetch of environment disclosure
    fetchEnvironment()
      .then((env) => {
        setStore({ environmentDisclosure: env });
      })
      .catch((err) => {
        console.warn("Could not load environment disclosure yet:", err);
      });

    function connect() {
      const loc = window.location;
      const protocol = loc.protocol === "https:" ? "wss:" : "ws:";
      const host = loc.hostname || "localhost";
      const port = loc.port === "5173" ? "8000" : loc.port || "8000";
      const wsUrl = `${protocol}//${host}:${port}/ws`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setStore({ connected: true });
        backoffMsRef.current = 500;

        // Start ping loop
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping", seq: globalState.lastSeq }));
          }
        }, 10000);
      };

      ws.onmessage = (event) => {
        try {
          const envelope: WsEnvelope = JSON.parse(event.data);
          handleEnvelope(ws, envelope);
        } catch (e) {
          console.error("Failed to parse WS envelope:", e);
        }
      };

      ws.onclose = () => {
        setStore({ connected: false });
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);

        // Exponential backoff reconnect
        const nextBackoff = Math.min(backoffMsRef.current * 1.5, 4000);
        backoffMsRef.current = nextBackoff;
        reconnectTimeoutRef.current = setTimeout(connect, nextBackoff);
      };

      ws.onerror = (e) => {
        console.warn("WebSocket connection warning:", e);
        ws.close();
      };
    }

    connect();

    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
    };
  }, []);
}

function handleEnvelope(ws: WebSocket, envelope: WsEnvelope) {
  const { type, seq, tick, payload } = envelope;

  // Gap detection: if seq jumps unexpectedly, send resync
  if (globalState.lastSeq > 0 && seq > globalState.lastSeq + 1 && type === "delta") {
    console.warn(`Detected sequence gap! Current: ${globalState.lastSeq}, Incoming: ${seq}. Requesting resync...`);
    ws.send(JSON.stringify({ type: "resync" }));
    return;
  }

  switch (type) {
    case "hello": {
      setStore({
        hello: payload as HelloPayload,
        lastSeq: seq,
      });
      break;
    }
    case "static_world": {
      setStore({
        staticWorld: payload as StaticWorld,
        lastSeq: seq,
      });
      break;
    }
    case "snapshot": {
      const snap = payload as any;
      const robotsMap: Record<string, Robot> = {};
      const snapRobots = snap.robots || snap.dynamic?.robots;
      if (snapRobots) {
        if (Array.isArray(snapRobots)) {
          snapRobots.forEach((r: any) => {
            const id = r.robot_id || r.id;
            robotsMap[id] = {
              ...r,
              id: id,
              battery_percent: r.battery_percent ?? r.battery_pct ?? 100,
            };
          });
        } else {
          Object.entries(snapRobots).forEach(([id, r]: [string, any]) => {
            robotsMap[id] = {
              ...r,
              id: id,
              battery_percent: r.battery_percent ?? r.battery_pct ?? 100,
            };
          });
        }
      }

      const ordersMap: Record<string, Order> = {};
      const snapOrders = snap.orders || snap.dynamic?.orders;
      if (snapOrders) {
        if (Array.isArray(snapOrders)) {
          snapOrders.forEach((o: any) => {
            const id = o.order_id || o.id;
            ordersMap[id] = { ...o, id: id };
          });
        } else {
          Object.entries(snapOrders).forEach(([id, o]: [string, any]) => {
            ordersMap[id] = { ...o, id: id };
          });
        }
      }

      setStore({
        snapshot: snap,
        robots: robotsMap,
        orders: ordersMap,
        alerts: snap.alerts || snap.active_alerts || snap.dynamic?.active_alerts || [],
        kpis: snap.kpis || snap.dynamic?.kpis || initialKPIs,
        recentEvents: snap.recent_events || snap.dynamic?.recent_events || [],
        tick: snap.tick ?? tick,
        simTimeMs: snap.sim_time_ms ?? 0,
        lastSeq: seq,
      });
      break;
    }
    case "delta": {
      updateStore((prev) => {
        // Merge robots
        const nextRobots = { ...prev.robots };
        if (payload.robots) {
          Object.entries(payload.robots as Record<string, Partial<Robot>>).forEach(([id, rPatch]) => {
            const current = nextRobots[id];
            nextRobots[id] = current ? ({ ...current, ...rPatch } as Robot) : (rPatch as Robot);
          });
        }

        // Merge orders
        const nextOrders = { ...prev.orders };
        if (payload.orders) {
          Object.entries(payload.orders as Record<string, Partial<Order>>).forEach(([id, oPatch]) => {
            const current = nextOrders[id];
            nextOrders[id] = current ? ({ ...current, ...oPatch } as Order) : (oPatch as Order);
          });
        }

        // Prepend new events, keep up to 100
        const nextEvents = [...(payload.new_events || []), ...prev.recentEvents].slice(0, 100);

        return {
          ...prev,
          robots: nextRobots,
          orders: nextOrders,
          alerts: payload.alerts !== undefined ? payload.alerts : prev.alerts,
          kpis: payload.kpis || prev.kpis,
          recentEvents: nextEvents,
          tick: payload.tick ?? tick,
          simTimeMs: payload.sim_time_ms ?? prev.simTimeMs,
          lastSeq: seq,
        };
      });
      break;
    }
    case "pong":
      // Keepalive confirmed
      break;
    default:
      break;
  }
}
