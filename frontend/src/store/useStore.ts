import { useEffect, useRef, useState } from "react";
import type {
  Alert,
  ApprovalRequest,
  AuditEntry,
  BrainMode,
  BrainProvider,
  ChaosFault,
  Coordinate,
  Decision,
  DegradedMode,
  DynamicKPIs,
  EnvironmentDisclosure,
  Event,
  ExceptionItem,
  HelloPayload,
  Order,
  ReslotRecommendation,
  Robot,
  StaticWorld,
  WorldSnapshot,
  WsEnvelope,
} from "../types/generated";
import {
  fetchBrainApprovals,
  fetchBrainDecisions,
  fetchBrainStatus,
  fetchChaosStatus,
  fetchEnvironment,
  fetchExceptions,
  fetchReslotRecommendations,
} from "../services/api";

export type WorkspaceView =
  | "overview"
  | "2d"
  | "3d"
  | "split"
  | "orders"
  | "brain"
  | "chaos"
  | "replay";

export interface KpiHistoryPoint {
  tick: number;
  throughput: number;
  queueDepth: number;
  utilization: number;
  moving: number;
  delivered: number;
}

export interface StoreState {
  connected: boolean;
  hello: HelloPayload | null;
  staticWorld: StaticWorld | null;
  snapshot: WorldSnapshot | null;
  robots: Record<string, Robot>;
  orders: Record<string, Order>;
  alerts: Alert[];
  kpis: DynamicKPIs;
  kpiHistory: KpiHistoryPoint[];
  recentEvents: Event[];
  tick: number;
  simTimeMs: number;
  lastSeq: number;
  isPaused: boolean;
  speedMultiplier: number;
  theme: "dark" | "light";
  activeWorkspaceView: WorkspaceView;
  selectedRobotId: string | null;
  focusedCoord: Coordinate | null;
  selectedOrderId: string | null;
  isEnvironmentModalOpen: boolean;
  isEStopModalOpen: boolean;
  blockModeActive: boolean;
  selectedCellsToBlock: Coordinate[];
  leftPanelOpen: boolean;
  rightPanelOpen: boolean;
  activeRightTab: "alerts" | "events";
  activeOverlays: {
    showFlowArrows: boolean;
    showZones: boolean;
    showLabels: boolean;
    showCongestion: boolean;
  };
  environmentDisclosure: EnvironmentDisclosure | null;
  // Phase 4: 3D Visualization, Cameras & Quality
  viewMode: "2d" | "3d" | "split";
  cameraMode: "orbit" | "isometric" | "follow" | "stations" | "dispatch" | "cinematic";
  lightingPreset: "daylight" | "warm_evening" | "night_ops";
  qualityTier: "ultra" | "high" | "medium" | "low";
  showMiniMap: boolean;
  show3DLabels: boolean;
  show3DPaths: boolean;
  showDiagnostics: boolean;
  diagnostics: {
    fps: number;
    drawCalls: number;
    triangles: number;
    tier: string;
  };
  // Phase 5: AI Operations Brain
  aiMode: BrainMode;
  brainProvider: BrainProvider;
  brainConnectionState: string;
  brainModelName: string;
  brainInferenceInFlight: boolean;
  deadlocksActiveCount: number;
  circuitBreakerTripped: boolean;
  decisions: Decision[];
  pendingApprovals: ApprovalRequest[];
  heldZones: string[];
  totalBrainCostUsd: number;
  isDecisionLogOpen: boolean;
  isApprovalsDrawerOpen: boolean;
  isSupervisorBarOpen: boolean;
  isAISettingsOpen: boolean;
  // Phase 6: Chaos, Resilience, Exceptions & Audit
  isChaosControlOpen: boolean;
  isExceptionsQueueOpen: boolean;
  isAuditLogOpen: boolean;
  isIncidentTimelineOpen: boolean;
  activeFaults: ChaosFault[];
  activeFaultsCount: number;
  degradedModes: DegradedMode[];
  pendingExceptions: ExceptionItem[];
  reslotRecommendations: ReslotRecommendation[];
  // Phase 7: Replay & Historical Run Operations
  isReplayMode: boolean;
  replayRecordingId: string | null;
  replayTotalTicks: number;
  replayBookmarks: Array<{ tick: number; type: string; title: string; description: string }>;
  isReplaying: boolean;
  replaySpeedMultiplier: number;
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
  kpiHistory: [],
  recentEvents: [],
  tick: 0,
  simTimeMs: 0,
  lastSeq: 0,
  isPaused: false,
  speedMultiplier: 1.0,
  theme: (typeof localStorage !== "undefined" && (localStorage.getItem("ROBOFLEET_THEME") as any)) || "light",
  activeWorkspaceView:
    (typeof localStorage !== "undefined" &&
      (["2d", "3d", "split"].includes(localStorage.getItem("ROBOFLEET_VIEW_MODE") || "")
        ? (localStorage.getItem("ROBOFLEET_VIEW_MODE") as "2d" | "3d" | "split")
        : "split")) ||
    "split",
  selectedRobotId: null,
  focusedCoord: null,
  selectedOrderId: null,
  isEnvironmentModalOpen: false,
  isEStopModalOpen: false,
  blockModeActive: false,
  selectedCellsToBlock: [],
  leftPanelOpen: true,
  rightPanelOpen: true,
  activeRightTab: "alerts",
  activeOverlays: {
    showFlowArrows: true,
    showZones: true,
    showLabels: true,
    showCongestion: false,
  },
  environmentDisclosure: null,
  viewMode:
    (typeof localStorage !== "undefined" &&
      (["2d", "3d", "split"].includes(localStorage.getItem("ROBOFLEET_VIEW_MODE") || "")
        ? (localStorage.getItem("ROBOFLEET_VIEW_MODE") as "2d" | "3d" | "split")
        : "split")) ||
    "split",
  cameraMode: "orbit",
  lightingPreset: "daylight",
  qualityTier: "high",
  showMiniMap: true,
  show3DLabels: true,
  show3DPaths: true,
  showDiagnostics: false,
  diagnostics: {
    fps: 60,
    drawCalls: 0,
    triangles: 0,
    tier: "high",
  },
  // Phase 5: AI Operations Brain
  aiMode: "heuristic",
  brainProvider: "heuristic",
  brainConnectionState: "Heuristic Mode — Active",
  brainModelName: "deterministic",
  brainInferenceInFlight: false,
  deadlocksActiveCount: 0,
  circuitBreakerTripped: false,
  decisions: [],
  pendingApprovals: [],
  heldZones: [],
  totalBrainCostUsd: 0,
  isDecisionLogOpen: false,
  isApprovalsDrawerOpen: false,
  isSupervisorBarOpen: false,
  isAISettingsOpen: false,
  // Phase 6: Chaos, Resilience, Exceptions & Audit
  isChaosControlOpen: false,
  isExceptionsQueueOpen: false,
  isAuditLogOpen: false,
  isIncidentTimelineOpen: false,
  activeFaults: [],
  activeFaultsCount: 0,
  degradedModes: [],
  pendingExceptions: [],
  reslotRecommendations: [],
  isReplayMode: false,
  replayRecordingId: null,
  replayTotalTicks: 0,
  replayBookmarks: [],
  isReplaying: false,
  replaySpeedMultiplier: 1.0,
};

const listeners = new Set<() => void>();

function notify() {
  if (typeof window !== "undefined") {
    (window as any).__ROBOFLEET_STORE__ = { getState: () => globalState };
  }
  listeners.forEach((listener) => listener());
}

export function updateStore(updater: (prev: StoreState) => StoreState) {
  globalState = updater(globalState);
  if (typeof localStorage !== "undefined" && globalState.viewMode) {
    localStorage.setItem("ROBOFLEET_VIEW_MODE", globalState.viewMode);
  }
  notify();
}

export function setStore(patch: Partial<StoreState>) {
  globalState = { ...globalState, ...patch };
  if (patch.viewMode && typeof localStorage !== "undefined") {
    localStorage.setItem("ROBOFLEET_VIEW_MODE", patch.viewMode);
  }
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

export function normalizeRobot(raw: any): Robot {
  const id = String(raw.robot_id || raw.id || "ROBOT-000");
  const cell = raw.cell || raw.coord || { x: 0, y: 0 };
  const cx = Number(cell.x) || 0;
  const cy = Number(cell.y) || 0;

  let headingDeg = 0;
  if (typeof raw.heading_deg === "number") {
    headingDeg = raw.heading_deg;
  } else if (typeof raw.heading === "string") {
    const h = raw.heading.toUpperCase();
    if (h === "N") headingDeg = 270;
    else if (h === "E") headingDeg = 0;
    else if (h === "S") headingDeg = 90;
    else if (h === "W") headingDeg = 180;
  }

  const battery = Number(raw.battery_percent ?? raw.battery_pct ?? 100);

  let motion = raw.motion;
  if (!motion) {
    motion = {
      from_coord: { x: cx, y: cy },
      to_coord: { x: cx, y: cy },
      progress: 1.0,
      heading_deg: headingDeg,
    };
  } else {
    const rawFc = motion.from_coord || motion.from_cell || { x: cx, y: cy };
    const rawTc = motion.to_coord || motion.to_cell || { x: cx, y: cy };
    const rawProg =
      typeof motion.progress === "number"
        ? motion.progress
        : typeof motion.progress_permille === "number"
          ? motion.progress_permille / 1000
          : 1.0;
    motion = {
      from_coord: { x: Number(rawFc.x) || 0, y: Number(rawFc.y) || 0 },
      to_coord: { x: Number(rawTc.x) || 0, y: Number(rawTc.y) || 0 },
      progress: Math.max(0, Math.min(1, rawProg)),
      heading_deg: Number(motion.heading_deg) || headingDeg,
    };
  }

  return {
    id,
    coord: { x: cx, y: cy },
    heading_deg: headingDeg,
    state: raw.state || "IDLE",
    battery_percent: battery,
    current_task_id: raw.current_task_id || null,
    fault_code: raw.fault || raw.fault_code || null,
    motion,
    telemetry: raw.telemetry || {
      odometer_m: Number(raw.odometer_m) || 0,
      battery_percent: battery,
      internal_temp_c: Number(raw.internal_temp_c) || 32.0,
      current_speed_m_s:
        Number(raw.current_speed_m_s) ||
        (String(raw.state).startsWith("MOVING") ? 1.2 : 0),
    },
  };
}

export function normalizeOrder(raw: any): Order {
  const id = String(raw.order_id || raw.id || "ORD-000");
  return {
    id,
    received_tick: Number(raw.created_tick ?? raw.received_tick ?? 0),
    deadline_tick: Number(raw.deadline_tick ?? 1000),
    sla_tier: String(raw.sla_tier || "standard"),
    status: raw.status || "QUEUED",
    lines: Array.isArray(raw.lines) ? raw.lines : [],
    priority: Number(raw.priority) || 1,
    assigned_robot_id: raw.assigned_robot_id || null,
    assigned_robot_ids: Array.isArray(raw.assigned_robot_ids) ? raw.assigned_robot_ids : [],
    tote_id: raw.tote_id || null,
    ready_tick: raw.ready_tick ?? null,
    handover_tick: raw.handover_tick ?? null,
    delay_attribution: raw.delay_attribution || null,
    at_risk: Boolean(raw.at_risk),
  };
}

export function normalizeAlert(raw: any): Alert {
  const id = String(raw.alert_id || raw.id || `ALERT-${Math.random()}`);
  const entityId =
    raw.entity_id ||
    (Array.isArray(raw.entity_ids) && raw.entity_ids.length > 0 ? raw.entity_ids[0] : null);
  const rawCoord = raw.coord || raw.cell || null;
  const coord = rawCoord ? { x: Number(rawCoord.x) || 0, y: Number(rawCoord.y) || 0 } : null;
  const tickVal = Number(raw.tick !== undefined ? raw.tick : raw.raised_tick) || 0;
  const isCleared = Boolean(raw.cleared || (raw.resolved_tick !== null && raw.resolved_tick !== undefined));

  return {
    id,
    tick: tickVal,
    severity: raw.severity || "WARN",
    category: String(raw.category || "OPERATIONAL"),
    message: String(raw.message || "Alert notice"),
    entity_id: entityId,
    coord,
    requires_human: Boolean(raw.requires_human),
    cleared: isCleared,
    cleared_tick: raw.cleared_tick || raw.resolved_tick || null,
  };
}

// WebSocket Connection Manager singleton hook
export function useWebSocketConnection() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const backoffMsRef = useRef(300);

  useEffect(() => {
    fetchEnvironment()
      .then((env) => setStore({ environmentDisclosure: env }))
      .catch((err) => console.warn("Environment disclosure initial fetch:", err));

    fetchBrainStatus()
      .then((st) =>
        setStore({
          aiMode: (st.mode || "heuristic") as BrainMode,
          brainProvider: (st.provider || "heuristic") as BrainProvider,
          brainConnectionState: st.connection_state || "Heuristic Mode — Active",
          brainModelName: st.model_name || "",
          brainInferenceInFlight: Boolean(st.inference_in_flight),
          deadlocksActiveCount: Number(st.deadlocks_active_count) || 0,
          circuitBreakerTripped: Boolean(st.circuit_breaker_tripped || st.circuit_tripped),
          heldZones: st.held_zones || [],
          totalBrainCostUsd: Number(st.total_cost_usd) || 0,
        })
      )
      .catch((err) => console.warn("Brain status initial fetch:", err));

    fetchBrainDecisions(50)
      .then((decs) => setStore({ decisions: decs }))
      .catch((err) => console.warn("Brain decisions initial fetch:", err));

    fetchBrainApprovals()
      .then((apps) => setStore({ pendingApprovals: apps }))
      .catch((err) => console.warn("Brain approvals initial fetch:", err));

    fetchChaosStatus()
      .then((cs) =>
        setStore({
          activeFaults: cs.active_faults || [],
          activeFaultsCount: (cs.active_faults || []).length,
          degradedModes: cs.degraded_modes || [],
        })
      )
      .catch((err) => console.warn("Chaos status initial fetch:", err));

    fetchExceptions()
      .then((exs) =>
        setStore({
          pendingExceptions: exs.pending_exceptions || [],
        })
      )
      .catch((err) => console.warn("Exceptions initial fetch:", err));

    fetchReslotRecommendations()
      .then((recs) =>
        setStore({
          reslotRecommendations: recs || [],
        })
      )
      .catch((err) => console.warn("Reslot recommendations initial fetch:", err));

    function connect() {
      const loc = window.location;
      const protocol = loc.protocol === "https:" ? "wss:" : "ws:";
      const host = loc.hostname || "localhost";
      const port = loc.port === "5173" ? "8000" : loc.port || "8000";
      const token = localStorage.getItem("ROBOFLEET_TOKEN") || "secret-robofleet-token";
      const wsUrl = `${protocol}//${host}:${port}/ws?token=${encodeURIComponent(token)}`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setStore({ connected: true });
        backoffMsRef.current = 300;

        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
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

        const nextBackoff = Math.min(backoffMsRef.current * 1.5, 2000);
        backoffMsRef.current = nextBackoff;
        reconnectTimeoutRef.current = setTimeout(connect, nextBackoff);
      };

      ws.onerror = (e) => {
        console.warn("WebSocket warning:", e);
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

  if (globalState.lastSeq > 0 && seq > globalState.lastSeq + 1 && type === "delta") {
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
      const rawRobots = snap.robots || snap.dynamic?.robots || [];
      const robotsMap: Record<string, Robot> = {};
      const listRobots = Array.isArray(rawRobots) ? rawRobots : Object.values(rawRobots);
      listRobots.forEach((r) => {
        const nr = normalizeRobot(r);
        robotsMap[nr.id] = nr;
      });

      const rawOrders = snap.orders || snap.dynamic?.orders || [];
      const ordersMap: Record<string, Order> = {};
      const listOrders = Array.isArray(rawOrders) ? rawOrders : Object.values(rawOrders);
      listOrders.forEach((o) => {
        const no = normalizeOrder(o);
        ordersMap[no.id] = no;
      });

      const rawAlerts = snap.alerts || snap.active_alerts || snap.dynamic?.alerts || snap.dynamic?.active_alerts || [];
      const listAlerts = Array.isArray(rawAlerts) ? rawAlerts.map(normalizeAlert) : [];

      const snapTick = Number(snap.tick ?? snap.dynamic?.tick ?? tick ?? 0);
      const snapKpis = snap.kpis || snap.dynamic?.kpis || initialKPIs;
      let nextKpiHistory = globalState.kpiHistory;
      if (snapTick === 0 || snapTick < globalState.tick) {
        nextKpiHistory = [];
      } else if (
        nextKpiHistory.length === 0 ||
        snapTick > nextKpiHistory[nextKpiHistory.length - 1].tick
      ) {
        nextKpiHistory = [
          ...nextKpiHistory,
          {
            tick: snapTick,
            throughput: Number(snapKpis.throughput_orders_per_hr) || 0,
            queueDepth: Number(snapKpis.queue_depth) || 0,
            utilization: Number(snapKpis.fleet_utilization) || 0,
            moving: Number(snapKpis.robots_moving) || 0,
            delivered: Number(snapKpis.completed_orders_total) || 0,
          },
        ].slice(-120);
      }

      setStore({
        snapshot: snap,
        staticWorld: snap.layout
          ? {
            meta: snap.meta,
            layout: snap.layout,
            skus: snap.skus || snap.catalogue || {},
            bins: snap.bins || {},
          }
          : globalState.staticWorld,
        robots: robotsMap,
        orders: ordersMap,
        alerts: listAlerts,
        kpis: snapKpis,
        kpiHistory: nextKpiHistory,
        recentEvents: snap.recent_events || snap.dynamic?.recent_events || snap.events || [],
        tick: snapTick,
        simTimeMs: snap.sim_time_ms ?? snap.dynamic?.sim_time_ms ?? 0,
        lastSeq: seq,
      });
      break;
    }
    case "delta": {
      updateStore((prev) => {
        const nextRobots = { ...prev.robots };
        if (payload.robots) {
          const list = Array.isArray(payload.robots) ? payload.robots : Object.values(payload.robots);
          list.forEach((r: any) => {
            const nr = normalizeRobot(r);
            nextRobots[nr.id] = nr;
          });
        }

        const nextOrders = { ...prev.orders };
        if (payload.orders) {
          const list = Array.isArray(payload.orders) ? payload.orders : Object.values(payload.orders);
          list.forEach((o: any) => {
            const no = normalizeOrder(o);
            nextOrders[no.id] = no;
          });
        }

        const nextAlerts =
          payload.alerts !== undefined
            ? (Array.isArray(payload.alerts) ? payload.alerts.map(normalizeAlert) : prev.alerts)
            : prev.alerts;

        const newEventsList = payload.new_events || payload.events || [];
        const nextEvents = [...newEventsList, ...prev.recentEvents].slice(0, 100);

        let nextDecisions = prev.decisions;
        if (payload.recent_decision) {
          const rec = payload.recent_decision;
          if (!prev.decisions.some((d) => d.decision_id === rec.decision_id)) {
            nextDecisions = [rec, ...prev.decisions].slice(0, 100);
          }
        }
        if (Array.isArray(payload.decision_updates) && payload.decision_updates.length > 0) {
          const updatesMap = new Map<string, Decision>(
            payload.decision_updates.map((u: Decision) => [u.decision_id, u])
          );
          nextDecisions = nextDecisions.map((d) => updatesMap.get(d.decision_id) ?? d);
        }

        const brainStatus = payload.brain_status;
        const nextAiMode = brainStatus ? (brainStatus.ai_mode as BrainMode) : prev.aiMode;
        const nextProvider = brainStatus
          ? (brainStatus.provider_status as BrainProvider)
          : prev.brainProvider;
        const nextConnState = brainStatus?.connection_state ?? prev.brainConnectionState;
        const nextModelName = brainStatus?.model_name ?? prev.brainModelName;
        const nextInFlight =
          brainStatus?.inference_in_flight !== undefined
            ? Boolean(brainStatus.inference_in_flight)
            : prev.brainInferenceInFlight;
        const nextDeadlocksCount =
          brainStatus?.deadlocks_active_count !== undefined
            ? Number(brainStatus.deadlocks_active_count)
            : prev.deadlocksActiveCount;
        const nextHeldZones = Array.isArray(brainStatus?.held_zones)
          ? brainStatus.held_zones
          : prev.heldZones;
        const nextCircuit =
          brainStatus?.circuit_tripped !== undefined
            ? Boolean(brainStatus.circuit_tripped)
            : prev.circuitBreakerTripped;
        const nextApprovals =
          payload.pending_approvals !== undefined
            ? payload.pending_approvals
            : prev.pendingApprovals;
        const nextCost = brainStatus
          ? Number(brainStatus.total_cost_usd) || 0
          : prev.totalBrainCostUsd;

        const nextDegraded =
          payload.degraded_modes !== undefined ? payload.degraded_modes : prev.degradedModes;
        const nextActiveFaultsCount =
          payload.active_faults_count !== undefined
            ? payload.active_faults_count
            : prev.activeFaultsCount;
        const nextExceptions =
          payload.pending_exceptions !== undefined
            ? payload.pending_exceptions
            : prev.pendingExceptions;
        const nextReslot =
          payload.reslot_recommendations !== undefined
            ? payload.reslot_recommendations
            : prev.reslotRecommendations;

        const nextTick = Number(payload.tick ?? tick ?? prev.tick);
        const nextKpis = payload.kpis || prev.kpis;
        let nextKpiHistory = prev.kpiHistory;
        if (nextTick < prev.tick || (nextTick === 0 && prev.tick > 0)) {
          nextKpiHistory = [];
        } else if (nextTick > prev.tick) {
          const lastRecordedTick =
            prev.kpiHistory.length > 0
              ? prev.kpiHistory[prev.kpiHistory.length - 1].tick
              : -1;
          if (nextTick > lastRecordedTick) {
            nextKpiHistory = [
              ...prev.kpiHistory,
              {
                tick: nextTick,
                throughput: Number(nextKpis.throughput_orders_per_hr) || 0,
                queueDepth: Number(nextKpis.queue_depth) || 0,
                utilization: Number(nextKpis.fleet_utilization) || 0,
                moving: Number(nextKpis.robots_moving) || 0,
                delivered: Number(nextKpis.completed_orders_total) || 0,
              },
            ].slice(-120);
          }
        }

        return {
          ...prev,
          robots: nextRobots,
          orders: nextOrders,
          alerts: nextAlerts,
          kpis: nextKpis,
          kpiHistory: nextKpiHistory,
          recentEvents: nextEvents,
          decisions: nextDecisions,
          aiMode: nextAiMode,
          brainProvider: nextProvider,
          brainConnectionState: nextConnState,
          brainModelName: nextModelName,
          brainInferenceInFlight: nextInFlight,
          deadlocksActiveCount: nextDeadlocksCount,
          circuitBreakerTripped: nextCircuit,
          heldZones: nextHeldZones,
          pendingApprovals: nextApprovals,
          totalBrainCostUsd: nextCost,
          degradedModes: nextDegraded,
          activeFaultsCount: nextActiveFaultsCount,
          pendingExceptions: nextExceptions,
          reslotRecommendations: nextReslot,
          tick: nextTick,
          simTimeMs:
            payload.sim_time_ms !== undefined
              ? Number(payload.sim_time_ms)
              : payload.tick !== undefined
                ? Number(payload.tick) * 100
                : tick !== undefined
                  ? Number(tick) * 100
                  : prev.simTimeMs,
          lastSeq: seq,
        };
      });
      break;
    }
    case "pong":
      break;
    default:
      break;
  }
}
