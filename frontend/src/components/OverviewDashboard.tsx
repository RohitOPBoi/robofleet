import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Box,
  ChevronRight,
  Cpu,
  Download,
  Flame,
  Layers,
  Maximize2,
  Minus,
  Plus,
  ShieldAlert,
  Terminal,
  UserCheck,
} from "lucide-react";
import { scaleFleet, triggerRush } from "../services/api";
import { setStore, useStore } from "../store/useStore";
import type { BrainMode } from "../types/generated";
import { CanvasMap } from "./CanvasMap";

export interface KpiHistorySample {
  tick: number;
  throughput: number;
  queueDepth: number;
}

interface SplinePoint {
  x: number;
  y: number;
  qy: number;
  tick: number;
  throughput: number;
  queueDepth: number;
}

interface DonutSegment {
  key: string;
  label: string;
  count: number;
  pct: number;
  color: string;
}

const EASE_STUDIO = "cubic-bezier(0.23, 1, 0.32, 1)";

const AI_MODE_LABELS: Record<BrainMode, string> = {
  baseline: "Baseline",
  heuristic: "Heuristic",
  ai: "Cloud AI",
  local_llm: "Local LLM",
  replay: "Replay",
};

function formatSimClock(simTimeMs: number): string {
  const totalSeconds = Math.max(0, Math.floor((simTimeMs || 0) / 1000));
  const hours = Math.floor(totalSeconds / 3600) % 24;
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function formatSentenceCase(raw: string | null | undefined, fallback = ""): string {
  if (!raw) return fallback;
  const cleaned = raw.replace(/[_-]+/g, " ").trim().toLowerCase();
  if (!cleaned) return fallback;
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

function distributeLargestRemainder(counts: number[]): number[] {
  const total = counts.reduce((sum, c) => sum + c, 0);
  if (total <= 0) return counts.map(() => 0);

  const exact = counts.map((c, idx) => {
    const pct = (c / total) * 100;
    const floor = Math.floor(pct);
    return {
      idx,
      count: c,
      floor,
      remainder: pct - floor,
    };
  });

  let remaining = 100 - exact.reduce((sum, item) => sum + item.floor, 0);
  const byRemainder = [...exact].sort((a, b) => {
    if (b.remainder !== a.remainder) return b.remainder - a.remainder;
    return b.count - a.count;
  });

  const result = exact.map((item) => item.floor);
  let i = 0;
  while (remaining > 0 && byRemainder.length > 0) {
    result[byRemainder[i % byRemainder.length].idx] += 1;
    remaining -= 1;
    i += 1;
  }
  return result;
}

function buildCatmullRomPaths(
  points: Array<{ x: number; y: number }>,
  baselineY: number,
  minY: number
): { linePath: string; areaPath: string } {
  if (points.length === 0) return { linePath: "", areaPath: "" };
  if (points.length === 1) {
    const p = points[0];
    return {
      linePath: `M ${p.x.toFixed(2)} ${p.y.toFixed(2)}`,
      areaPath: `M ${p.x.toFixed(2)} ${baselineY.toFixed(2)} L ${p.x.toFixed(2)} ${p.y.toFixed(2)} L ${p.x.toFixed(2)} ${baselineY.toFixed(2)} Z`,
    };
  }

  const clampY = (val: number) => Math.max(minY, Math.min(baselineY, val));
  let line = `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;

  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(0, i - 1)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(points.length - 1, i + 2)];

    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = clampY(p1.y + (p2.y - p0.y) / 6);
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = clampY(p2.y - (p3.y - p1.y) / 6);

    line += ` C ${cp1x.toFixed(2)} ${cp1y.toFixed(2)}, ${cp2x.toFixed(2)} ${cp2y.toFixed(2)}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
  }

  const first = points[0];
  const last = points[points.length - 1];
  const area = `${line} L ${last.x.toFixed(2)} ${baselineY.toFixed(2)} L ${first.x.toFixed(2)} ${baselineY.toFixed(2)} Z`;
  return { linePath: line, areaPath: area };
}

function patchStore(patch: Record<string, unknown>) {
  (setStore as (p: Record<string, unknown>) => void)(patch);
}

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState<boolean>(() => {
    if (typeof window === "undefined" || !window.matchMedia) return false;
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  });

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(mq.matches);
    update();
    mq.addEventListener?.("change", update);
    return () => mq.removeEventListener?.("change", update);
  }, []);

  return reduced;
}

export const OverviewDashboard: React.FC = () => {
  const store = useStore();
  const {
    connected,
    robots,
    orders,
    alerts,
    kpis,
    tick,
    simTimeMs,
    aiMode,
    decisions,
    pendingApprovals,
    activeFaults,
    activeFaultsCount,
  } = store;

  const prefersReducedMotion = usePrefersReducedMotion();
  const [rushPending, setRushPending] = useState(false);
  const [scalePending, setScalePending] = useState(false);
  const [exportPending, setExportPending] = useState(false);
  const [chartWindow, setChartWindow] = useState<30 | 60 | 120>(60);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const [hoveredDonutKey, setHoveredDonutKey] = useState<string | null>(null);
  const [localHistory, setLocalHistory] = useState<KpiHistorySample[]>([]);
  const lastRecordedTickRef = useRef<number>(-1);
  const chartSvgRef = useRef<SVGSVGElement | null>(null);
  const chartCardRef = useRef<HTMLDivElement | null>(null);

  // Record genuine live KPI samples if store.kpiHistory isn't provided externally
  const storeKpiHistory = (store as unknown as { kpiHistory?: Array<Record<string, unknown>> }).kpiHistory;
  useEffect(() => {
    if (Array.isArray(storeKpiHistory) && storeKpiHistory.length > 0) return;
    if (tick === lastRecordedTickRef.current) return;
    lastRecordedTickRef.current = tick;

    const sample: KpiHistorySample = {
      tick,
      throughput: Number(kpis.throughput_orders_per_hr ?? 0),
      queueDepth: Number(kpis.queue_depth ?? 0),
    };

    setLocalHistory((prev) => {
      if (prev.length > 0 && prev[prev.length - 1].tick > tick) {
        return [sample];
      }
      const next = [...prev, sample];
      return next.length > 120 ? next.slice(next.length - 120) : next;
    });
  }, [tick, kpis.throughput_orders_per_hr, kpis.queue_depth, storeKpiHistory]);

  const kpiSeries: KpiHistorySample[] = useMemo(() => {
    const rawList = Array.isArray(storeKpiHistory) && storeKpiHistory.length > 0 ? storeKpiHistory : localHistory;
    return rawList.map((pt) => ({
      tick: Number((pt as Record<string, unknown>).tick ?? 0),
      throughput: Number((pt as Record<string, unknown>).throughput ?? (pt as Record<string, unknown>).throughput_orders_per_hr ?? 0),
      queueDepth: Number((pt as Record<string, unknown>).queueDepth ?? (pt as Record<string, unknown>).queue_depth ?? 0),
    }));
  }, [storeKpiHistory, localHistory]);

  // Live Fleet & Order Metrics
  const telemetry = useMemo(() => {
    const robotList = Object.values(robots);
    const orderList = Object.values(orders);
    const robotsTotal = robotList.length;

    let movingCount = 0;
    let pickingCount = 0;
    let idleCount = 0;
    let chargingCount = 0;
    let waitingCount = 0;
    let blockedCount = 0;
    let batterySum = 0;

    for (const r of robotList) {
      const st = String(r.state || "IDLE").toUpperCase();
      batterySum += Number(r.battery_percent ?? 100);

      if (st === "FAULTED" || st === "EMERGENCY_STOPPED" || st === "UNAVAILABLE" || st === "MAINTENANCE" || Boolean(r.fault_code)) {
        blockedCount += 1;
      } else if (st.startsWith("MOVING")) {
        movingCount += 1;
      } else if (st === "PICKING" || st === "DROPPING") {
        pickingCount += 1;
      } else if (st === "CHARGING") {
        chargingCount += 1;
      } else if (st === "WAITING") {
        waitingCount += 1;
      } else {
        idleCount += 1;
      }
    }

    if (robotsTotal === 0) {
      movingCount = Number(kpis.robots_moving ?? 0);
      idleCount = Number(kpis.robots_idle ?? 0);
      chargingCount = Number(kpis.robots_charging ?? 0);
      blockedCount = Number(kpis.robots_faulted ?? 0);
      pickingCount = Number((kpis as unknown as Record<string, unknown>).robots_picking ?? 0);
      waitingCount = Number((kpis as unknown as Record<string, unknown>).robots_waiting ?? 0);
    }

    const activeAlerts = alerts.filter((a) => !a.cleared);
    const alertsCount = Math.max(activeAlerts.length, Number(kpis.active_alerts_count ?? 0));
    const avgBatteryPct = robotsTotal > 0 ? Math.round(batterySum / robotsTotal) : 100;

    const kpiUtil = Number(kpis.fleet_utilization ?? 0);
    const utilPct =
      kpiUtil > 0 || robotsTotal === 0
        ? Math.min(100, Math.max(0, Math.round(kpiUtil)))
        : Math.min(100, Math.max(0, Math.round(((movingCount + pickingCount) / robotsTotal) * 100)));

    const handedOverCount = orderList.filter((o) => o.status === "HANDED_OVER").length;
    const rawCompleted = Number(
      (kpis as unknown as Record<string, unknown>).completed_orders_total ??
        (kpis as unknown as Record<string, unknown>).orders_completed ??
        0
    );
    const ordersDelivered = Math.max(rawCompleted, handedOverCount);

    const kpiOnTime = (kpis as unknown as Record<string, unknown>).on_time_percentage;
    let slaScore = 100;
    if (typeof kpiOnTime === "number" && !Number.isNaN(kpiOnTime)) {
      slaScore = Math.max(0, Math.min(100, kpiOnTime));
    } else {
      const evaluated = orderList.filter((o) => o.handover_tick != null);
      if (evaluated.length > 0) {
        const onTime = evaluated.filter((o) => (o.handover_tick ?? 0) <= o.deadline_tick).length;
        slaScore = (onTime / evaluated.length) * 100;
      } else if (orderList.length > 0) {
        const atRisk = Number(kpis.at_risk_orders ?? 0);
        slaScore = Math.max(0, ((orderList.length - atRisk) / orderList.length) * 100);
      }
    }

    return {
      robotsTotal,
      movingCount,
      pickingCount,
      idleCount,
      chargingCount,
      waitingCount,
      blockedCount,
      activeAlerts,
      alertsCount,
      avgBatteryPct,
      utilPct,
      ordersDelivered,
      slaScore,
    };
  }, [robots, orders, alerts, kpis]);

  const simTimeFormatted = formatSimClock(simTimeMs);
  const aiModeLabel = AI_MODE_LABELS[aiMode] ?? "Heuristic";
  const latestDecision = decisions[0] ?? null;
  const latestAlert = telemetry.activeAlerts[0] ?? alerts[0] ?? null;
  const latestFault = activeFaults.find((f) => f.active) ?? activeFaults[0] ?? null;
  const faultsCount = Math.max(activeFaultsCount, activeFaults.filter((f) => f.active).length);

  // Truthful Safety & SLA subtitle derived from live telemetry
  const safetySubtitle = useMemo(() => {
    const parts: string[] = [];
    if (telemetry.blockedCount > 0) {
      parts.push(`${telemetry.blockedCount} blocked`);
    }
    if (faultsCount > 0) {
      parts.push(`${faultsCount} fault${faultsCount === 1 ? "" : "s"}`);
    }
    if (telemetry.alertsCount > 0) {
      parts.push(`${telemetry.alertsCount} alert${telemetry.alertsCount === 1 ? "" : "s"}`);
    }
    return parts.length > 0 ? parts.join(" · ") : "No active faults or alerts";
  }, [telemetry.blockedCount, faultsCount, telemetry.alertsCount]);

  // Hero Ring geometry (132px diameter)
  const ringRadius = 52;
  const ringCircumference = 2 * Math.PI * ringRadius;
  const ringOffset = ringCircumference * (1 - telemetry.utilPct / 100);

  // 7-slot fleet state bar
  const stateSlots = [
    { key: "Mov", label: "Mov", fullLabel: "Moving", count: telemetry.movingCount },
    { key: "Pick", label: "Pick", fullLabel: "Picking", count: telemetry.pickingCount },
    { key: "Idle", label: "Idle", fullLabel: "Idle", count: telemetry.idleCount },
    { key: "Chg", label: "Chg", fullLabel: "Charging", count: telemetry.chargingCount },
    { key: "Wait", label: "Wait", fullLabel: "Waiting", count: telemetry.waitingCount },
    { key: "Blk", label: "Blk", fullLabel: "Blocked", count: telemetry.blockedCount },
    { key: "Alrt", label: "Alrt", fullLabel: "Alerts", count: telemetry.alertsCount },
  ];

  const dominantSlotKey = useMemo(() => {
    if (telemetry.alertsCount > 0) return "Alrt";
    if (telemetry.blockedCount > 0) return "Blk";
    let best = stateSlots[0];
    for (const slot of stateSlots) {
      if (slot.count > best.count) best = slot;
    }
    return best.count > 0 ? best.key : "Mov";
  }, [
    telemetry.alertsCount,
    telemetry.blockedCount,
    telemetry.movingCount,
    telemetry.pickingCount,
    telemetry.idleCount,
    telemetry.chargingCount,
    telemetry.waitingCount,
  ]);

  const handleStateChipClick = (slotKey: string) => {
    if (slotKey === "Alrt") {
      setStore({ rightPanelOpen: true, activeRightTab: "alerts" });
      return;
    }
    if (slotKey === "Blk") {
      if (faultsCount > 0) {
        setStore({ isChaosControlOpen: true });
        return;
      }
    }

    const robotList = Object.values(robots);
    const matchingRobot = robotList.find((r) => {
      const st = String(r.state || "IDLE").toUpperCase();
      if (slotKey === "Blk") {
        return st === "FAULTED" || st === "EMERGENCY_STOPPED" || st === "UNAVAILABLE" || st === "MAINTENANCE" || Boolean(r.fault_code);
      }
      if (slotKey === "Mov") return st.startsWith("MOVING");
      if (slotKey === "Pick") return st === "PICKING" || st === "DROPPING";
      if (slotKey === "Chg") return st === "CHARGING";
      if (slotKey === "Wait") return st === "WAITING";
      return st === "IDLE";
    });

    patchStore({
      activeWorkspaceView: "2d",
      viewMode: "2d",
      ...(matchingRobot ? { selectedRobotId: matchingRobot.id } : {}),
    });
  };

  // Throughput delta pill from live kpiSeries
  const throughputNow = Number(kpis.throughput_orders_per_hr ?? 0);
  const throughputDelta = useMemo(() => {
    if (kpiSeries.length < 2) return { label: "Live", pct: null as number | null };
    const baseline = kpiSeries[Math.max(0, kpiSeries.length - 10)].throughput;
    if (baseline <= 0) {
      if (throughputNow > 0) return { label: "+100.0%", pct: 100 };
      return { label: "0.0%", pct: 0 };
    }
    const pct = ((throughputNow - baseline) / baseline) * 100;
    const sign = pct > 0 ? "+" : "";
    return { label: `${sign}${pct.toFixed(1)}%`, pct };
  }, [kpiSeries, throughputNow]);

  // Spline Chart computation (Throughput + Queue Depth)
  const visibleSeries = useMemo(() => {
    if (kpiSeries.length <= chartWindow) return kpiSeries;
    return kpiSeries.slice(kpiSeries.length - chartWindow);
  }, [kpiSeries, chartWindow]);

  const chartSvgW = 420;
  const chartSvgH = 180;
  const padL = 34;
  const padR = 28;
  const padT = 16;
  const padB = 26;
  const plotW = chartSvgW - padL - padR;
  const plotH = chartSvgH - padT - padB;
  const baselineY = padT + plotH;

  const { splinePoints, maxThroughput, maxQueue, linePath, areaPath, queueLinePath } = useMemo(() => {
    const rawMaxT = visibleSeries.reduce((m, p) => Math.max(m, p.throughput), 0);
    const ceilT = Math.max(20, Math.ceil((rawMaxT * 1.18) / 10) * 10);

    const rawMaxQ = visibleSeries.reduce((m, p) => Math.max(m, p.queueDepth), 0);
    const ceilQ = Math.max(5, Math.ceil((rawMaxQ * 1.2) / 5) * 5);

    const pts: SplinePoint[] = visibleSeries.map((pt, i) => {
      const x =
        visibleSeries.length <= 1
          ? padL + plotW / 2
          : padL + (i / (visibleSeries.length - 1)) * plotW;
      const y = baselineY - (Math.max(0, pt.throughput) / ceilT) * plotH;
      const qy = baselineY - (Math.max(0, pt.queueDepth) / ceilQ) * plotH;
      return {
        x,
        y,
        qy,
        tick: pt.tick,
        throughput: pt.throughput,
        queueDepth: pt.queueDepth,
      };
    });

    const { linePath: lp, areaPath: ap } = buildCatmullRomPaths(pts, baselineY, padT);
    const { linePath: qlp } = buildCatmullRomPaths(
      pts.map((p) => ({ x: p.x, y: p.qy })),
      baselineY,
      padT
    );
    return {
      splinePoints: pts,
      maxThroughput: ceilT,
      maxQueue: ceilQ,
      linePath: lp,
      areaPath: ap,
      queueLinePath: qlp,
    };
  }, [visibleSeries, plotW, plotH, baselineY]);

  const activeHoverIdx =
    hoverIdx !== null && hoverIdx >= 0 && hoverIdx < splinePoints.length ? hoverIdx : null;
  const hoveredPoint = activeHoverIdx !== null ? splinePoints[activeHoverIdx] : null;

  const handleChartMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (splinePoints.length === 0 || !chartSvgRef.current) return;
    const rect = chartSvgRef.current.getBoundingClientRect();
    if (rect.width <= 0) return;
    const svgX = ((e.clientX - rect.left) / rect.width) * chartSvgW;

    let nearest = 0;
    let minDist = Infinity;
    for (let i = 0; i < splinePoints.length; i++) {
      const d = Math.abs(splinePoints[i].x - svgX);
      if (d < minDist) {
        minDist = d;
        nearest = i;
      }
    }
    setHoverIdx(nearest);
  };

  // Clamped tooltip position relative to hovered point
  const tooltipPos = useMemo(() => {
    if (!hoveredPoint) return null;
    const xPct = (hoveredPoint.x / chartSvgW) * 100;
    const yPct = (hoveredPoint.y / chartSvgH) * 100;
    const leftPct = Math.min(68, Math.max(6, xPct - 14));
    const topPct =
      hoveredPoint.y < padT + 50
        ? Math.min(68, yPct + 8)
        : Math.max(2, yPct - 28);
    return { leftPct, topPct };
  }, [hoveredPoint]);

  // Donut breakdown segments (Blocked/Faulted split out, largest-remainder % rounding)
  const donutSegments: DonutSegment[] = useMemo(() => {
    const idleWaitTotal = telemetry.idleCount + telemetry.waitingCount;
    const counts = [
      telemetry.movingCount,
      telemetry.pickingCount,
      telemetry.chargingCount,
      idleWaitTotal,
      telemetry.blockedCount,
    ];
    const pcts = distributeLargestRemainder(counts);

    return [
      {
        key: "moving",
        label: "Moving",
        count: counts[0],
        pct: pcts[0],
        color: "#D9533B",
      },
      {
        key: "picking",
        label: "Picking",
        count: counts[1],
        pct: pcts[1],
        color: "#D97706",
      },
      {
        key: "charging",
        label: "Charging",
        count: counts[2],
        pct: pcts[2],
        color: "#2E7D5B",
      },
      {
        key: "idle",
        label: "Idle / Wait",
        count: counts[3],
        pct: pcts[3],
        color: "#9A8B80",
      },
      {
        key: "blocked",
        label: "Blocked / Faulted",
        count: counts[4],
        pct: pcts[4],
        color: "#B93829",
      },
    ];
  }, [
    telemetry.movingCount,
    telemetry.pickingCount,
    telemetry.chargingCount,
    telemetry.idleCount,
    telemetry.waitingCount,
    telemetry.blockedCount,
  ]);

  const donutRadius = 46;
  const donutCircumference = 2 * Math.PI * donutRadius;
  const activeSegmentCount = useMemo(
    () => donutSegments.filter((seg) => seg.count > 0).length,
    [donutSegments]
  );

  const donutArcs = useMemo(() => {
    const sum = donutSegments.reduce((s, seg) => s + seg.count, 0);
    if (sum <= 0) return [];

    let cumulative = 0;
    return donutSegments.map((seg) => {
      const fraction = seg.count / sum;
      const arcLength = fraction * donutCircumference;
      const offset = -cumulative * donutCircumference;
      cumulative += fraction;
      return {
        ...seg,
        arcLength,
        offset,
      };
    });
  }, [donutSegments, donutCircumference]);

  const hoveredDonutSeg = hoveredDonutKey
    ? donutSegments.find((s) => s.key === hoveredDonutKey) ?? null
    : null;

  // Actions
  const handleRushBurst = async () => {
    if (rushPending) return;
    setRushPending(true);
    try {
      await triggerRush(2.5, 300);
    } catch (err) {
      console.error("Failed to trigger rush burst:", err);
    } finally {
      setTimeout(() => setRushPending(false), 1200);
    }
  };

  const handleScaleUp = async () => {
    if (scalePending) return;
    setScalePending(true);
    try {
      const nextTarget = Math.min(100, Math.max(1, telemetry.robotsTotal + 2));
      await scaleFleet(nextTarget);
    } catch (err) {
      console.error("Failed to scale fleet:", err);
    } finally {
      setTimeout(() => setScalePending(false), 800);
    }
  };

  const handleExportAuditCsv = async () => {
    if (exportPending) return;
    setExportPending(true);
    try {
      const res = await fetch("/api/audit/export.csv");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `robofleet-audit-t${tick}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      setStore({ isAuditLogOpen: true });
    } finally {
      setTimeout(() => setExportPending(false), 700);
    }
  };

  const handleFocusChart = () => {
    setChartWindow((prev) => (prev === 30 ? 60 : prev === 60 ? 120 : 30));
    chartCardRef.current?.scrollIntoView({
      behavior: prefersReducedMotion ? "auto" : "smooth",
      block: "nearest",
    });
  };

  const heroHeadline =
    telemetry.alertsCount === 0 && telemetry.blockedCount === 0
      ? "Fleet dispatch is running smoothly"
      : telemetry.alertsCount > 0
        ? `${telemetry.alertsCount} active alert${telemetry.alertsCount === 1 ? "" : "s"} under triage`
        : `${telemetry.blockedCount} blocked AMR${telemetry.blockedCount === 1 ? "" : "s"} resolving`;

  const quickActions = [
    {
      id: "approvals",
      title: "Review approvals",
      subtitle:
        pendingApprovals.length > 0
          ? `${pendingApprovals.length} awaiting sign-off`
          : "Queue clear",
      badge: pendingApprovals.length > 0 ? String(pendingApprovals.length) : null,
      icon: UserCheck,
      onClick: () => setStore({ isApprovalsDrawerOpen: true }),
    },
    {
      id: "rush",
      title: rushPending ? "Rush wave active" : "Trigger rush burst",
      subtitle: "Inject 2.5x priority order surge",
      badge: rushPending ? "Live" : null,
      icon: Flame,
      onClick: handleRushBurst,
    },
    {
      id: "supervisor",
      title: "Supervisor command",
      subtitle: "Query fleet & dispatch overrides",
      badge: null,
      icon: Terminal,
      onClick: () => setStore({ isSupervisorBarOpen: true }),
    },
    {
      id: "audit",
      title: exportPending ? "Exporting CSV..." : "Export audit CSV",
      subtitle: "Download signed operations ledger",
      badge: null,
      icon: Download,
      onClick: handleExportAuditCsv,
    },
    {
      id: "ai-models",
      title: "AI & Local models",
      subtitle: `Active mode: ${aiModeLabel}`,
      badge: aiModeLabel,
      icon: Cpu,
      onClick: () => setStore({ isAISettingsOpen: true }),
    },
    {
      id: "chaos",
      title: "Chaos & faults",
      subtitle:
        faultsCount > 0
          ? `${faultsCount} active fault${faultsCount === 1 ? "" : "s"}`
          : "All resilience checks nominal",
      badge: faultsCount > 0 ? String(faultsCount) : null,
      icon: ShieldAlert,
      onClick: () => setStore({ isChaosControlOpen: true }),
    },
  ];

  const decisionTitle = latestDecision
    ? `Brain decision · ${formatSentenceCase(latestDecision.trigger, aiModeLabel)}`
    : `Brain decision · ${aiModeLabel}`;

  const floorCardTitle =
    latestAlert && !latestAlert.cleared
      ? `${formatSentenceCase(latestAlert.severity, "Alert")} · ${formatSentenceCase(latestAlert.category, "Operational")}`
      : latestFault && latestFault.active
        ? `Fault · ${formatSentenceCase(latestFault.fault_type, "Fault")}`
        : "Nominal station load";

  return (
    <div className="w-full max-w-[1480px] mx-auto px-4 sm:px-6 py-5 space-y-5 text-[var(--studio-text-primary)]">
      {/* 1. Top Split Row */}
      <section className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        {/* Single Hero Focal Card */}
        <div className="xl:col-span-8 studio-card-terracotta p-6 rounded-2xl relative overflow-hidden text-[#FFFBF8] studio-enter stagger-1 flex flex-col justify-between min-h-[256px]">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
            <div className="flex-1 min-w-0">
              {/* Quiet Status Pill */}
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#FFFBF8]/15 border border-[#FFFBF8]/20 text-xs font-medium text-[#FFFBF8]/95 tabular-nums">
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    connected ? "bg-emerald-300" : "bg-amber-200"
                  }`}
                />
                <span>
                  Live · Tick {tick} · {telemetry.robotsTotal} AMRs active
                </span>
              </div>

              {/* Crisp Headline & Summary */}
              <h2 className="text-[26px] sm:text-[30px] leading-[1.15] tracking-[-0.025em] font-semibold text-[#FFFBF8] mt-4">
                {heroHeadline}
              </h2>
              <p className="text-sm text-[#FFFBF8]/85 mt-2 max-w-xl leading-relaxed tabular-nums">
                {telemetry.ordersDelivered} delivered today with{" "}
                {kpis.queue_depth ?? 0} queued for pick and handover across the
                floor.
              </p>

              {/* Inline Telemetry Trio */}
              <div className="flex flex-wrap items-center gap-5 sm:gap-7 mt-5 tabular-nums">
                <div>
                  <div className="text-[22px] sm:text-[24px] font-semibold leading-none text-[#FFFBF8]">
                    {telemetry.movingCount}
                  </div>
                  <div className="text-[11px] text-[#FFFBF8]/75 mt-1">
                    Robots moving
                  </div>
                </div>
                <div className="h-7 w-px bg-[#FFFBF8]/20 hidden sm:block" />
                <div>
                  <div className="text-[22px] sm:text-[24px] font-semibold leading-none text-[#FFFBF8]">
                    {telemetry.ordersDelivered}
                  </div>
                  <div className="text-[11px] text-[#FFFBF8]/75 mt-1">
                    Orders delivered
                  </div>
                </div>
                <div className="h-7 w-px bg-[#FFFBF8]/20 hidden sm:block" />
                <div>
                  <div className="text-[22px] sm:text-[24px] font-semibold leading-none text-[#FFFBF8]">
                    {telemetry.avgBatteryPct}%
                  </div>
                  <div className="text-[11px] text-[#FFFBF8]/75 mt-1">
                    Avg battery %
                  </div>
                </div>
              </div>

              {/* Bottom-left Action Pills */}
              <div className="flex flex-wrap items-center gap-2.5 mt-6">
                <button
                  type="button"
                  onClick={() =>
                    patchStore({ activeWorkspaceView: "3d", viewMode: "3d" })
                  }
                  className="studio-btn inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-[#FFFBF8] text-[#241B16] hover:bg-[#FAF3EE] text-xs font-semibold shadow-sm cursor-pointer"
                  aria-label="Open 3D Twin"
                >
                  <Box className="w-3.5 h-3.5" strokeWidth={1.5} />
                  <span>Open 3D Twin</span>
                </button>
                <button
                  type="button"
                  onClick={handleRushBurst}
                  disabled={rushPending}
                  className="studio-btn inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-[#FFFBF8]/15 hover:bg-[#FFFBF8]/25 border border-[#FFFBF8]/25 text-[#FFFBF8] text-xs font-medium backdrop-blur-sm disabled:opacity-65 cursor-pointer"
                  aria-label={rushPending ? "Rush dispatched" : "Express Rush"}
                >
                  <Plus className="w-3.5 h-3.5" strokeWidth={1.5} />
                  <span>{rushPending ? "Rush Dispatched" : "Express Rush"}</span>
                </button>
              </div>
            </div>

            {/* Smooth Animated SVG Circular Progress Ring */}
            <div className="shrink-0 flex items-center justify-center self-start md:self-center">
              <div className="relative w-[132px] h-[132px] flex items-center justify-center">
                <svg
                  width={132}
                  height={132}
                  viewBox="0 0 132 132"
                  aria-label={`Fleet utilization ${telemetry.utilPct}%`}
                >
                  <circle
                    cx={66}
                    cy={66}
                    r={ringRadius}
                    fill="none"
                    stroke="rgba(255, 251, 248, 0.24)"
                    strokeWidth={10}
                  />
                  <circle
                    cx={66}
                    cy={66}
                    r={ringRadius}
                    fill="none"
                    stroke="#FFFBF8"
                    strokeWidth={10}
                    strokeLinecap="round"
                    strokeDasharray={ringCircumference}
                    strokeDashoffset={ringOffset}
                    transform="rotate(-90 66 66)"
                    style={{
                      transition: prefersReducedMotion
                        ? "none"
                        : `stroke-dashoffset 260ms ${EASE_STUDIO}`,
                    }}
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none">
                  <span className="text-[26px] font-semibold tracking-tight leading-none text-[#FFFBF8] tabular-nums">
                    {telemetry.utilPct}%
                  </span>
                  <span className="text-[11px] text-[#FFFBF8]/80 mt-1">
                    utilization
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Shift & Live Agenda Card */}
        <div className="xl:col-span-4 studio-card p-5 rounded-2xl flex flex-col justify-between studio-enter stagger-2">
          {/* Header Row */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3.5">
              <div className="text-[36px] leading-none font-semibold tracking-[-0.03em] text-[var(--studio-text-primary)] tabular-nums">
                {String(tick).padStart(3, "0")}
              </div>
              <div className="min-w-0">
                <div className="text-xs font-medium text-[var(--studio-text-primary)] tabular-nums">
                  Sim time {simTimeFormatted}
                </div>
                <div className="text-[11px] text-[var(--studio-text-muted)] mt-0.5">
                  {connected ? "Telemetry stream synced" : "Connecting stream"}
                </div>
              </div>
            </div>
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-[#E05A42]/12 text-[#B83B24] dark:text-[#E87454] border border-[#E05A42]/25 text-[11px] font-medium shrink-0">
              <Cpu className="w-3 h-3" strokeWidth={1.5} />
              <span>{aiModeLabel}</span>
            </span>
          </div>

          {/* Compact 7-slot Horizontal State Bar */}
          <div className="grid grid-cols-7 gap-1 my-4">
            {stateSlots.map((slot) => {
              const isDominant = slot.key === dominantSlotKey;
              const isActive = slot.count > 0;
              const isFaultSlot = slot.key === "Blk" || slot.key === "Alrt";

              let chipClass =
                "bg-[var(--studio-surface-subtle)]/55 text-[var(--studio-text-muted)] border border-transparent hover:bg-[var(--studio-surface-subtle)]";
              let labelClass = "text-[var(--studio-text-muted)]";

              if (isFaultSlot) {
                if (isDominant && isActive) {
                  chipClass =
                    "bg-[#B93829] text-[#FFFBF8] border border-[#B93829] shadow-sm hover:bg-[#9F2E21]";
                  labelClass = "text-[#FFFBF8]/85";
                } else if (isActive) {
                  chipClass =
                    "bg-[#E05A42]/14 text-[#B83B24] dark:text-[#E87454] border border-[#E05A42]/30 hover:bg-[#E05A42]/20";
                  labelClass = "text-[#B83B24]/85 dark:text-[#E87454]/85";
                }
              } else if (isDominant && isActive) {
                chipClass =
                  "bg-[var(--studio-surface-elevated)] text-[var(--studio-text-primary)] border border-[var(--studio-border-strong)] shadow-sm";
                labelClass = "text-[var(--studio-text-secondary)]";
              } else if (isActive) {
                chipClass =
                  "bg-[var(--studio-surface-subtle)] text-[var(--studio-text-primary)] border border-[var(--studio-border)] hover:bg-[var(--studio-surface-elevated)]";
                labelClass = "text-[var(--studio-text-secondary)]";
              }

              return (
                <button
                  key={slot.key}
                  type="button"
                  onClick={() => handleStateChipClick(slot.key)}
                  aria-label={`${slot.fullLabel}: ${slot.count}`}
                  className={`studio-btn flex flex-col items-center justify-center py-2 px-1 rounded-xl text-center cursor-pointer ${chipClass}`}
                >
                  <span className={`text-[10px] font-medium ${labelClass}`}>
                    {slot.label}
                  </span>
                  <span className="text-xs font-semibold tabular-nums mt-0.5">
                    {slot.count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Two Inset Schedule/Event Sub-cards */}
          <div className="space-y-2.5">
            <button
              type="button"
              onClick={() => setStore({ isDecisionLogOpen: true })}
              className="studio-btn w-full text-left rounded-xl p-3 bg-[var(--studio-surface-subtle)] hover:bg-[var(--studio-surface-elevated)] border border-[var(--studio-border)] cursor-pointer flex items-start gap-3"
              aria-label="Open brain decision log"
            >
              <span className="text-[11px] font-medium text-[var(--studio-text-muted)] tabular-nums shrink-0 pt-0.5 w-11">
                {latestDecision ? `T+${latestDecision.tick}` : "Brain"}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-xs font-semibold text-[var(--studio-text-primary)] truncate">
                  {decisionTitle}
                </div>
                <div className="text-[11px] text-[var(--studio-text-secondary)] line-clamp-2 mt-0.5">
                  {latestDecision?.rationale ||
                    latestDecision?.situation_summary ||
                    "Dispatch rules & path reservations nominal"}
                </div>
              </div>
              <ChevronRight
                className="w-3.5 h-3.5 text-[var(--studio-text-muted)] shrink-0 mt-0.5"
                strokeWidth={1.5}
              />
            </button>

            <button
              type="button"
              onClick={() => {
                if (faultsCount > 0 || activeFaults.length > 0) {
                  setStore({ isChaosControlOpen: true });
                } else if (telemetry.alertsCount > 0) {
                  setStore({ rightPanelOpen: true, activeRightTab: "alerts" });
                } else {
                  setStore({ isChaosControlOpen: true });
                }
              }}
              className="studio-btn w-full text-left rounded-xl p-3 bg-[var(--studio-surface-subtle)] hover:bg-[var(--studio-surface-elevated)] border border-[var(--studio-border)] cursor-pointer flex items-start gap-3"
              aria-label="Inspect floor alerts and faults"
            >
              <span className="text-[11px] font-medium text-[var(--studio-text-muted)] tabular-nums shrink-0 pt-0.5 w-11">
                {latestAlert
                  ? `T+${latestAlert.tick}`
                  : latestFault
                    ? `T+${latestFault.injected_tick}`
                    : "Floor"}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-xs font-semibold text-[var(--studio-text-primary)] truncate">
                  {floorCardTitle}
                </div>
                <div className="text-[11px] text-[var(--studio-text-secondary)] line-clamp-2 mt-0.5">
                  {latestAlert && !latestAlert.cleared
                    ? latestAlert.message
                    : latestFault && latestFault.active
                      ? `Target: ${latestFault.target_id}`
                      : "All aisles, stations & chargers healthy"}
                </div>
              </div>
              <ChevronRight
                className="w-3.5 h-3.5 text-[var(--studio-text-muted)] shrink-0 mt-0.5"
                strokeWidth={1.5}
              />
            </button>
          </div>
        </div>
      </section>

      {/* 2. Middle 4-Card KPI Row (All 4 clean .studio-card interactive buttons, no decorative icon tiles) */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-4 studio-enter stagger-3">
        {/* Card 1: Active Robots -> 2D Floor */}
        <button
          type="button"
          onClick={() => patchStore({ activeWorkspaceView: "2d", viewMode: "2d" })}
          className="studio-card studio-btn p-5 rounded-2xl flex flex-col justify-between text-left hover:bg-[var(--studio-surface-elevated)] hover:border-[var(--studio-border-strong)] cursor-pointer"
          aria-label="Open 2D fleet map"
        >
          <div className="flex items-center justify-between gap-2 w-full">
            <span className="text-xs font-medium text-[var(--studio-text-secondary)]">
              Active robots
            </span>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/12 text-[#176441] dark:text-emerald-300 border border-emerald-600/20 dark:border-emerald-400/25 tabular-nums">
              {telemetry.utilPct}% busy
            </span>
          </div>
          <div className="mt-4">
            <div className="text-[28px] leading-none font-semibold tracking-tight text-[var(--studio-text-primary)] tabular-nums">
              {telemetry.movingCount} / {telemetry.robotsTotal}
            </div>
            <div className="text-[11px] text-[var(--studio-text-muted)] mt-2 tabular-nums">
              {telemetry.chargingCount} charging · {telemetry.idleCount} idle
            </div>
          </div>
        </button>

        {/* Card 2: Open Orders -> Orders View */}
        <button
          type="button"
          onClick={() => patchStore({ activeWorkspaceView: "orders" })}
          className="studio-card studio-btn p-5 rounded-2xl flex flex-col justify-between text-left hover:bg-[var(--studio-surface-elevated)] hover:border-[var(--studio-border-strong)] cursor-pointer"
          aria-label="Open orders queue"
        >
          <div className="flex items-center justify-between gap-2 w-full">
            <span className="text-xs font-medium text-[var(--studio-text-secondary)]">
              Open orders
            </span>
            <span
              className={`px-2.5 py-0.5 rounded-full text-[11px] font-medium tabular-nums border ${
                (kpis.at_risk_orders ?? 0) > 0
                  ? "bg-amber-500/12 text-[#85470D] dark:text-amber-300 border-amber-600/20 dark:border-amber-400/25"
                  : "bg-[var(--studio-surface-subtle)] text-[var(--studio-text-secondary)] border-[var(--studio-border)]"
              }`}
            >
              {kpis.at_risk_orders ?? 0} at risk
            </span>
          </div>
          <div className="mt-4">
            <div className="text-[28px] leading-none font-semibold tracking-tight text-[var(--studio-text-primary)] tabular-nums">
              {kpis.queue_depth ?? 0}
            </div>
            <div className="text-[11px] text-[var(--studio-text-muted)] mt-2 tabular-nums">
              {telemetry.ordersDelivered} completed
            </div>
          </div>
        </button>

        {/* Card 3: Throughput -> Focuses Throughput & Queue chart */}
        <button
          type="button"
          onClick={handleFocusChart}
          className="studio-card studio-btn p-5 rounded-2xl flex flex-col justify-between text-left hover:bg-[var(--studio-surface-elevated)] hover:border-[var(--studio-border-strong)] cursor-pointer"
          aria-label="Focus Throughput and Queue chart and cycle window"
        >
          <div className="flex items-center justify-between gap-2 w-full">
            <span className="text-xs font-medium text-[var(--studio-text-secondary)]">
              Throughput
            </span>
            <span
              className={`inline-flex items-center gap-0.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium border tabular-nums ${
                throughputDelta.pct === null || Math.abs(throughputDelta.pct) <= 0.05
                  ? "bg-[var(--studio-surface-subtle)] text-[var(--studio-text-secondary)] border-[var(--studio-border)]"
                  : throughputDelta.pct > 0
                    ? "bg-emerald-500/12 text-[#176441] dark:text-emerald-300 border-emerald-600/20 dark:border-emerald-400/25"
                    : "bg-[#E05A42]/12 text-[#B83B24] dark:text-[#E87454] border-[#E05A42]/25"
              }`}
            >
              {throughputDelta.pct === null || Math.abs(throughputDelta.pct) <= 0.05 ? (
                <Minus className="w-3 h-3" strokeWidth={1.5} />
              ) : throughputDelta.pct > 0 ? (
                <ArrowUpRight className="w-3 h-3" strokeWidth={1.5} />
              ) : (
                <ArrowDownRight className="w-3 h-3" strokeWidth={1.5} />
              )}
              <span>{throughputDelta.label}</span>
            </span>
          </div>
          <div className="mt-4">
            <div className="flex items-baseline gap-1.5">
              <span className="text-[28px] leading-none font-semibold tracking-tight text-[#B83B24] dark:text-[#E87454] tabular-nums">
                {Math.round(throughputNow)}
              </span>
              <span className="text-xs font-medium text-[var(--studio-text-muted)]">
                ord/hr
              </span>
            </div>
            <div className="text-[11px] text-[var(--studio-text-muted)] mt-2 tabular-nums">
              {telemetry.pickingCount} picking at stations
            </div>
          </div>
        </button>

        {/* Card 4: Safety & SLA -> Alerts or Chaos Control */}
        <button
          type="button"
          onClick={() => {
            if (telemetry.alertsCount > 0) {
              setStore({ rightPanelOpen: true, activeRightTab: "alerts" });
            } else {
              setStore({ isChaosControlOpen: true });
            }
          }}
          className="studio-card studio-btn p-5 rounded-2xl flex flex-col justify-between text-left hover:bg-[var(--studio-surface-elevated)] hover:border-[var(--studio-border-strong)] cursor-pointer"
          aria-label="Open safety alerts and fault controls"
        >
          <div className="flex items-center justify-between gap-2 w-full">
            <span className="text-xs font-medium text-[var(--studio-text-secondary)]">
              Safety &amp; SLA
            </span>
            <span
              className={`px-2.5 py-0.5 rounded-full text-[11px] font-medium tabular-nums border ${
                telemetry.alertsCount > 0
                  ? "bg-[#E05A42]/12 text-[#B83B24] dark:text-[#E87454] border-[#E05A42]/25"
                  : "bg-emerald-500/12 text-[#176441] dark:text-emerald-300 border-emerald-600/20 dark:border-emerald-400/25"
              }`}
            >
              {telemetry.alertsCount} alerts
            </span>
          </div>
          <div className="mt-4">
            <div className="text-[28px] leading-none font-semibold tracking-tight text-[var(--studio-text-primary)] tabular-nums">
              {telemetry.slaScore.toFixed(1)}%
            </div>
            <div className="text-[11px] text-[var(--studio-text-muted)] mt-2 tabular-nums">
              {safetySubtitle}
            </div>
          </div>
        </button>
      </section>

      {/* 3. Quick Actions 3x2 Interactive Grid */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 studio-enter stagger-4">
        {quickActions.map((action) => {
          const Icon = action.icon;
          return (
            <button
              key={action.id}
              type="button"
              onClick={action.onClick}
              className="studio-card studio-btn p-3.5 rounded-xl text-left flex items-center justify-between gap-3 hover:bg-[var(--studio-surface-elevated)] hover:border-[var(--studio-border-strong)] cursor-pointer group"
            >
              <div className="flex items-center gap-3 min-w-0">
                <span className="w-9 h-9 rounded-lg bg-[#E05A42]/12 border border-[#E05A42]/20 text-[#B83B24] dark:text-[#E87454] flex items-center justify-center shrink-0 transition-colors duration-150 group-hover:bg-[#D9533B] group-hover:text-[#FFFBF8] group-hover:border-[#D9533B]">
                  <Icon className="w-4 h-4" strokeWidth={1.5} />
                </span>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-[var(--studio-text-primary)] truncate">
                      {action.title}
                    </span>
                    {action.badge && (
                      <span className="px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-[var(--studio-surface-subtle)] border border-[var(--studio-border)] text-[var(--studio-text-secondary)] tabular-nums shrink-0">
                        {action.badge}
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-[var(--studio-text-muted)] truncate mt-0.5">
                    {action.subtitle}
                  </div>
                </div>
              </div>
              <ChevronRight
                className="w-4 h-4 text-[var(--studio-text-muted)] shrink-0 transition-transform duration-150 group-hover:translate-x-0.5"
                strokeWidth={1.5}
              />
            </button>
          );
        })}
      </section>

      {/* 4. Bottom Data & Live Floor Twin Section */}
      <section className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        {/* Live Embedded 2D Digital Twin Stage */}
        <div className="xl:col-span-5 studio-card p-4 rounded-2xl flex flex-col studio-enter stagger-5">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3 px-1">
            <div className="flex items-center gap-2 min-w-0">
              <Layers className="w-4 h-4 text-[#B83B24] dark:text-[#E87454] shrink-0" strokeWidth={1.5} />
              <h3 className="text-sm font-semibold text-[var(--studio-text-primary)] truncate">
                Live warehouse floor
              </h3>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <button
                type="button"
                onClick={handleScaleUp}
                disabled={scalePending}
                className="studio-btn inline-flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-[var(--studio-text-primary)] text-[var(--studio-canvas)] hover:opacity-90 text-[11px] font-medium disabled:opacity-60 cursor-pointer"
                title="Add 2 AMRs to active fleet"
                aria-label="Add 2 AMRs to active fleet"
              >
                <Plus className="w-3 h-3" strokeWidth={1.5} />
                <span>+2 AMRs</span>
              </button>
              <div className="flex items-center gap-0.5 bg-[var(--studio-surface-subtle)] border border-[var(--studio-border)] p-0.5 rounded-xl">
                <button
                  type="button"
                  onClick={() =>
                    patchStore({ activeWorkspaceView: "2d", viewMode: "2d" })
                  }
                  className="studio-btn inline-flex items-center gap-1 px-2 py-1 rounded-[9px] text-[11px] font-medium text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-elevated)] cursor-pointer"
                  aria-label="Expand 2D floor view"
                >
                  <Maximize2 className="w-3 h-3" strokeWidth={1.5} />
                  <span>2D</span>
                </button>
                <button
                  type="button"
                  onClick={() =>
                    patchStore({ activeWorkspaceView: "3d", viewMode: "3d" })
                  }
                  className="studio-btn px-2 py-1 rounded-[9px] text-[11px] font-medium text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-elevated)] cursor-pointer"
                  aria-label="Open 3D view"
                >
                  3D
                </button>
                <button
                  type="button"
                  onClick={() =>
                    patchStore({ activeWorkspaceView: "split", viewMode: "split" })
                  }
                  className="studio-btn px-2 py-1 rounded-[9px] text-[11px] font-medium text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-elevated)] cursor-pointer"
                  aria-label="Open split 2D and 3D view"
                >
                  Split
                </button>
              </div>
            </div>
          </div>

          <div className="h-[290px] w-full rounded-xl overflow-hidden relative border border-[var(--studio-border)] bg-[var(--studio-canvas)]">
            <CanvasMap compact />
          </div>
        </div>

        {/* Throughput & Queue Spline Chart */}
        <div
          ref={chartCardRef}
          className="xl:col-span-4 studio-card p-5 rounded-2xl flex flex-col justify-between studio-enter stagger-5"
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <h3 className="text-sm font-semibold text-[var(--studio-text-primary)]">
                Throughput &amp; Queue
              </h3>
              <p className="text-xs text-[var(--studio-text-muted)] mt-0.5 tabular-nums">
                {Math.round(throughputNow)} ord/hr · {kpis.queue_depth ?? 0} queued
              </p>
              <div className="flex items-center gap-3 mt-2 text-[11px] text-[var(--studio-text-secondary)]">
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-3 h-0.5 rounded-full bg-[#D9533B] inline-block" />
                  <span>Throughput</span>
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-3 border-t-[1.5px] border-dashed border-[var(--studio-text-muted)] inline-block" />
                  <span>Queue depth</span>
                </span>
              </div>
            </div>

            <div className="flex items-center bg-[var(--studio-surface-subtle)] border border-[var(--studio-border)] p-0.5 rounded-xl text-[11px] font-medium tabular-nums shrink-0">
              {([30, 60, 120] as const).map((w) => (
                <button
                  key={w}
                  type="button"
                  onClick={() => setChartWindow(w)}
                  aria-pressed={chartWindow === w}
                  aria-label={`Show ${w} tick chart window`}
                  className={`studio-btn px-2 py-1 rounded-[9px] cursor-pointer ${
                    chartWindow === w
                      ? "bg-[var(--studio-surface-elevated)] text-[var(--studio-text-primary)] shadow-sm"
                      : "text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)]"
                  }`}
                >
                  {w}t
                </button>
              ))}
            </div>
          </div>

          <div className="relative mt-3 flex-1 flex flex-col justify-center">
            <svg
              ref={chartSvgRef}
              viewBox={`0 0 ${chartSvgW} ${chartSvgH}`}
              className="w-full h-[196px] overflow-visible select-none"
              onMouseMove={handleChartMouseMove}
              onMouseLeave={() => setHoverIdx(null)}
            >
              <defs>
                <linearGradient id="studioSplinePeach" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#D9533B" stopOpacity="0.24" />
                  <stop offset="65%" stopColor="#E87454" stopOpacity="0.07" />
                  <stop offset="100%" stopColor="#E87454" stopOpacity="0" />
                </linearGradient>
              </defs>

              {/* Subtle muted horizontal gridlines & dual-scale labels */}
              {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
                const gy = baselineY - frac * plotH;
                const labelVal = Math.round(frac * maxThroughput);
                const queueVal = Math.round(frac * maxQueue);
                return (
                  <g key={frac}>
                    <line
                      x1={padL}
                      y1={gy}
                      x2={chartSvgW - padR}
                      y2={gy}
                      stroke="var(--studio-border)"
                      strokeDasharray={frac === 0 ? undefined : "3 3"}
                    />
                    <text
                      x={padL - 6}
                      y={gy + 3}
                      textAnchor="end"
                      fill="var(--studio-text-muted)"
                      className="text-[10px] tabular-nums"
                    >
                      {labelVal}
                    </text>
                    {(frac === 0 || frac === 0.5 || frac === 1) && (
                      <text
                        x={chartSvgW - padR + 6}
                        y={gy + 3}
                        textAnchor="start"
                        fill="var(--studio-text-muted)"
                        className="text-[9.5px] tabular-nums"
                      >
                        {queueVal}
                      </text>
                    )}
                  </g>
                );
              })}

              {splinePoints.length >= 2 ? (
                <>
                  <path d={areaPath} fill="url(#studioSplinePeach)" />
                  <path
                    d={queueLinePath}
                    fill="none"
                    stroke="var(--studio-text-muted)"
                    strokeWidth={1.75}
                    strokeDasharray="4 3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    opacity={0.85}
                  />
                  <path
                    d={linePath}
                    fill="none"
                    stroke="#D9533B"
                    strokeWidth={2.5}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </>
              ) : (
                <>
                  <line
                    x1={padL}
                    y1={baselineY - plotH * 0.12}
                    x2={chartSvgW - padR}
                    y2={baselineY - plotH * 0.12}
                    stroke="var(--studio-border-strong)"
                    strokeWidth={1.5}
                    strokeDasharray="4 4"
                  />
                  {splinePoints.length === 1 && (
                    <>
                      <circle
                        cx={splinePoints[0].x}
                        cy={splinePoints[0].qy}
                        r={3.5}
                        fill="var(--studio-text-muted)"
                      />
                      <circle
                        cx={splinePoints[0].x}
                        cy={splinePoints[0].y}
                        r={4}
                        fill="#D9533B"
                      />
                    </>
                  )}
                  <text
                    x={padL + plotW / 2}
                    y={padT + plotH / 2 - 4}
                    textAnchor="middle"
                    fill="var(--studio-text-muted)"
                    className="text-[11px]"
                  >
                    Warming up live telemetry window…
                  </text>
                </>
              )}

              {/* Hover scrub guide + dual-series nodes */}
              {hoveredPoint && (
                <g className="pointer-events-none">
                  <line
                    x1={hoveredPoint.x}
                    y1={padT}
                    x2={hoveredPoint.x}
                    y2={baselineY}
                    stroke="var(--studio-border-strong)"
                    strokeWidth={1}
                  />
                  <circle
                    cx={hoveredPoint.x}
                    cy={hoveredPoint.qy}
                    r={3.5}
                    fill="var(--studio-surface-elevated)"
                    stroke="var(--studio-text-muted)"
                    strokeWidth={2}
                  />
                  <circle
                    cx={hoveredPoint.x}
                    cy={hoveredPoint.y}
                    r={4.5}
                    fill="var(--studio-surface-elevated)"
                    stroke="#D9533B"
                    strokeWidth={2.5}
                  />
                </g>
              )}

              {/* Bottom X-axis tick captions */}
              {splinePoints.length >= 1 && (
                <>
                  <text
                    x={padL}
                    y={chartSvgH - 4}
                    textAnchor="start"
                    fill="var(--studio-text-muted)"
                    className="text-[10px] tabular-nums"
                  >
                    T+{splinePoints[0].tick}
                  </text>
                  {splinePoints.length >= 3 && (
                    <text
                      x={padL + plotW / 2}
                      y={chartSvgH - 4}
                      textAnchor="middle"
                      fill="var(--studio-text-muted)"
                      className="text-[10px] tabular-nums"
                    >
                      T+{splinePoints[Math.floor(splinePoints.length / 2)].tick}
                    </text>
                  )}
                  <text
                    x={chartSvgW - padR}
                    y={chartSvgH - 4}
                    textAnchor="end"
                    fill="var(--studio-text-muted)"
                    className="text-[10px] tabular-nums"
                  >
                    T+{splinePoints[splinePoints.length - 1].tick}
                  </text>
                </>
              )}
            </svg>

            {/* Clamped Dark-Aware Tooltip */}
            {hoveredPoint && tooltipPos && (
              <div
                className="absolute z-20 pointer-events-none bg-[var(--studio-surface-elevated)] text-[var(--studio-text-primary)] border border-[var(--studio-border-strong)] rounded-xl px-2.5 py-1.5 shadow-lg text-[11px] tabular-nums backdrop-blur-md"
                style={{
                  left: `${tooltipPos.leftPct}%`,
                  top: `${tooltipPos.topPct}%`,
                }}
              >
                <div className="font-semibold text-[var(--studio-text-primary)]">
                  Tick {hoveredPoint.tick}
                </div>
                <div className="text-[var(--studio-text-secondary)]">
                  {Math.round(hoveredPoint.throughput)} ord/hr · Q{" "}
                  {hoveredPoint.queueDepth}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Fleet State Breakdown Donut */}
        <div className="xl:col-span-3 studio-card p-5 rounded-2xl flex flex-col justify-between studio-enter stagger-6">
          <div className="flex items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-semibold text-[var(--studio-text-primary)]">
                Fleet by state
              </h3>
              <p className="text-xs text-[var(--studio-text-muted)] mt-0.5">
                Live allocation share
              </p>
            </div>
            {telemetry.alertsCount > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#E05A42]/12 text-[#B83B24] dark:text-[#E87454] border border-[#E05A42]/25 text-[11px] font-medium tabular-nums">
                <AlertTriangle className="w-3 h-3" strokeWidth={1.5} />
                <span>{telemetry.alertsCount}</span>
              </span>
            )}
          </div>

          {/* Multi-segment SVG Donut */}
          <div className="relative flex items-center justify-center my-4">
            <svg width={132} height={132} viewBox="0 0 132 132" aria-label="Fleet allocation by state">
              <circle
                cx={66}
                cy={66}
                r={donutRadius}
                fill="none"
                stroke="var(--studio-border-strong)"
                strokeWidth={14}
              />
              {donutArcs.map((seg) => {
                if (seg.count <= 0) return null;
                const isDimmed =
                  hoveredDonutKey !== null && hoveredDonutKey !== seg.key;
                const isHighlighted = hoveredDonutKey === seg.key;
                const dashLen =
                  activeSegmentCount === 1
                    ? donutCircumference
                    : Math.max(0, seg.arcLength - Math.min(2, seg.arcLength * 0.25));

                return (
                  <circle
                    key={seg.key}
                    cx={66}
                    cy={66}
                    r={donutRadius}
                    fill="none"
                    stroke={seg.color}
                    strokeWidth={isHighlighted ? 17 : 14}
                    strokeDasharray={`${dashLen} ${donutCircumference}`}
                    strokeDashoffset={seg.offset}
                    strokeLinecap="butt"
                    transform="rotate(-90 66 66)"
                    opacity={isDimmed ? 0.3 : 1}
                    role="button"
                    tabIndex={0}
                    aria-label={`${seg.label}: ${seg.count} AMRs (${seg.pct}%)`}
                    className="cursor-pointer focus:outline-none"
                    style={{
                      transition: prefersReducedMotion
                        ? "none"
                        : `stroke-dashoffset 260ms ${EASE_STUDIO}, stroke-width 180ms ${EASE_STUDIO}, opacity 180ms ease`,
                    }}
                    onMouseEnter={() => setHoveredDonutKey(seg.key)}
                    onMouseLeave={() => setHoveredDonutKey(null)}
                    onFocus={() => setHoveredDonutKey(seg.key)}
                    onBlur={() => setHoveredDonutKey(null)}
                    onClick={() =>
                      setHoveredDonutKey((prev) => (prev === seg.key ? null : seg.key))
                    }
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setHoveredDonutKey((prev) =>
                          prev === seg.key ? null : seg.key
                        );
                      }
                    }}
                  />
                );
              })}
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none">
              <span className="text-[24px] font-semibold tracking-tight leading-none text-[var(--studio-text-primary)] tabular-nums">
                {hoveredDonutSeg ? hoveredDonutSeg.count : telemetry.robotsTotal}
              </span>
              <span className="text-[11px] text-[var(--studio-text-muted)] mt-1 max-w-[84px] truncate">
                {hoveredDonutSeg ? hoveredDonutSeg.label : "AMRs total"}
              </span>
            </div>
          </div>

          {/* 5-segment Interactive Legend Grid */}
          <div className="grid grid-cols-2 gap-1.5">
            {donutSegments.map((seg, idx) => {
              const isHighlighted = hoveredDonutKey === seg.key;
              const isFullSpan = idx === donutSegments.length - 1;
              return (
                <button
                  key={seg.key}
                  type="button"
                  aria-pressed={isHighlighted}
                  onMouseEnter={() => setHoveredDonutKey(seg.key)}
                  onMouseLeave={() => setHoveredDonutKey(null)}
                  onFocus={() => setHoveredDonutKey(seg.key)}
                  onBlur={() => setHoveredDonutKey(null)}
                  onClick={() =>
                    setHoveredDonutKey((prev) => (prev === seg.key ? null : seg.key))
                  }
                  className={`studio-btn text-left rounded-xl px-2.5 py-2 border cursor-pointer ${
                    isFullSpan ? "col-span-2" : ""
                  } ${
                    isHighlighted
                      ? "bg-[var(--studio-surface-elevated)] border-[var(--studio-border-strong)] shadow-sm"
                      : "bg-[var(--studio-surface-subtle)] border-transparent hover:bg-[var(--studio-surface-elevated)] hover:border-[var(--studio-border)]"
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    <span
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ backgroundColor: seg.color }}
                    />
                    <span className="text-[11px] font-medium text-[var(--studio-text-secondary)] truncate">
                      {seg.label}
                    </span>
                  </div>
                  <div className="text-xs font-semibold text-[var(--studio-text-primary)] tabular-nums mt-0.5 pl-3.5">
                    {seg.count}{" "}
                    <span className="font-normal text-[var(--studio-text-muted)]">
                      ({seg.pct}%)
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </section>
    </div>
  );
};

export default OverviewDashboard;
