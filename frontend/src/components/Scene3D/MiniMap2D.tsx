/**
 * MiniMap2D: Picture-in-Picture 2D HUD radar overlay for Scene3D.
 * Provides high-speed tactical spatial awareness, robot position pips,
 * active alert rings, and one-click robot targeting.
 */

import React, { useEffect, useRef } from "react";
import { Layers, X } from "lucide-react";
import { setStore, useStore } from "../../store/useStore";
import type { Robot } from "../../types/generated";

const getPos = (obj: any): { x: number; y: number } => {
  if (!obj) return { x: 0, y: 0 };
  if (obj.pos) return { x: Number(obj.pos.x) || 0, y: Number(obj.pos.y) || 0 };
  if (obj.coord) return { x: Number(obj.coord.x) || 0, y: Number(obj.coord.y) || 0 };
  return { x: Number(obj.x) || 0, y: Number(obj.y) || 0 };
};

function getInterpolatedCoord(r: Robot): { rx: number; ry: number } {
  let rx = r.coord?.x ?? 0;
  let ry = r.coord?.y ?? 0;
  if (r.motion?.from_coord && r.motion?.to_coord) {
    const prog = Math.max(0, Math.min(1, r.motion.progress ?? 0));
    rx = r.motion.from_coord.x + (r.motion.to_coord.x - r.motion.from_coord.x) * prog;
    ry = r.motion.from_coord.y + (r.motion.to_coord.y - r.motion.from_coord.y) * prog;
  }
  return { rx, ry };
}

export const MiniMap2D: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const { staticWorld, robots, alerts, selectedRobotId, showMiniMap, theme } = useStore();

  const layout = staticWorld?.layout;
  const storeWidth = layout?.width ?? 28;
  const storeHeight = layout?.height ?? 20;

  // Mini-map dimensions
  const mapWidth = 200;
  const mapHeight = Math.round((mapWidth * storeHeight) / storeWidth);
  const scale = mapWidth / storeWidth;

  const renderStateRef = useRef({
    layout,
    robots,
    alerts,
    selectedRobotId,
    storeWidth,
    storeHeight,
    scale,
    mapWidth,
    mapHeight,
    theme,
  });

  renderStateRef.current = {
    layout,
    robots,
    alerts,
    selectedRobotId,
    storeWidth,
    storeHeight,
    scale,
    mapWidth,
    mapHeight,
    theme,
  };

  useEffect(() => {
    if (!showMiniMap) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const mq =
      typeof window !== "undefined" && window.matchMedia
        ? window.matchMedia("(prefers-reduced-motion: reduce)")
        : null;
    let reducedMotion = mq?.matches ?? false;
    const onMqChange = () => {
      reducedMotion = mq?.matches ?? false;
    };
    mq?.addEventListener?.("change", onMqChange);

    let animId: number;

    const render = () => {
      const {
        layout: curLayout,
        robots: curRobots,
        alerts: curAlerts,
        selectedRobotId: curSelectedId,
        storeWidth: curW,
        storeHeight: curH,
        scale: curScale,
        mapWidth: curMapW,
        mapHeight: curMapH,
        theme: curTheme,
      } = renderStateRef.current;

      const dpr = window.devicePixelRatio || 1;
      const targetW = Math.round(curMapW * dpr);
      const targetH = Math.round(curMapH * dpr);
      if (canvas.width !== targetW || canvas.height !== targetH) {
        canvas.width = targetW;
        canvas.height = targetH;
      }

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, curMapW, curMapH);

      const isLight = curTheme === "light";

      // 1. Studio floor background
      ctx.fillStyle = isLight ? "#FAF5F0" : "#140F0D";
      ctx.fillRect(0, 0, curMapW, curMapH);

      // Subtle grid
      ctx.strokeStyle = isLight ? "rgba(72, 46, 32, 0.08)" : "rgba(255, 236, 224, 0.06)";
      ctx.lineWidth = 0.5;
      for (let x = 0; x <= curW; x += 4) {
        ctx.beginPath();
        ctx.moveTo(x * curScale, 0);
        ctx.lineTo(x * curScale, curMapH);
        ctx.stroke();
      }
      for (let y = 0; y <= curH; y += 4) {
        ctx.beginPath();
        ctx.moveTo(0, y * curScale);
        ctx.lineTo(curMapW, y * curScale);
        ctx.stroke();
      }

      // 2. Shelf footprints
      const cells = Array.isArray((curLayout as any)?.cells) ? (curLayout as any).cells : [];
      cells.forEach((cell: any) => {
        if (cell.cell_type === "SHELF") {
          const p = getPos(cell);
          ctx.fillStyle =
            cell.zone === "FROZEN"
              ? "#0891B2"
              : cell.zone === "CHILLED"
              ? "#2563EB"
              : isLight
              ? "#CBB8A9"
              : "#382B24";
          ctx.fillRect(p.x * curScale, p.y * curScale, curScale * 0.9, curScale * 0.9);
        }
      });

      // 3. Stations & Chargers
      const stations = Array.isArray((curLayout as any)?.stations)
        ? (curLayout as any).stations
        : (curLayout as any)?.pick_stations || [];
      ctx.fillStyle = "#2E7D5B";
      stations.forEach((s: any) => {
        const p = getPos(s);
        ctx.fillRect(p.x * curScale, p.y * curScale, curScale * 0.9, curScale * 0.9);
      });

      const chargers = Array.isArray((curLayout as any)?.chargers) ? (curLayout as any).chargers : [];
      ctx.fillStyle = "#B4691E";
      chargers.forEach((c: any) => {
        const p = getPos(c);
        ctx.fillRect(p.x * curScale, p.y * curScale, curScale * 0.9, curScale * 0.9);
      });

      // 4. Alert Beacons (static ring when prefers-reduced-motion is active)
      const now = performance.now() / 1000;
      curAlerts.forEach((alert) => {
        if (alert.cleared || !alert.coord) return;
        const ax = (alert.coord.x + 0.5) * curScale;
        const ay = (alert.coord.y + 0.5) * curScale;
        const isCritical = alert.severity === "CRITICAL";

        const ringRadius = reducedMotion ? 5.5 : 4 + 3 * Math.sin(now * 6);
        ctx.strokeStyle = isCritical ? "rgba(185, 56, 41, 0.85)" : "rgba(180, 105, 30, 0.85)";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(ax, ay, ringRadius, 0, Math.PI * 2);
        ctx.stroke();

        ctx.fillStyle = isCritical ? "#B93829" : "#B4691E";
        ctx.beginPath();
        ctx.arc(ax, ay, 2, 0, Math.PI * 2);
        ctx.fill();
      });

      // 5. Robots
      Object.values(curRobots).forEach((r) => {
        const { rx, ry } = getInterpolatedCoord(r);
        const cx = (rx + 0.5) * curScale;
        const cy = (ry + 0.5) * curScale;
        const isSelected = curSelectedId === r.id;

        let color = isLight ? "#2E7D5B" : "#34D399";
        if (r.state === "CHARGING") color = "#B4691E";
        else if (r.state === "FAULTED" || r.state === "EMERGENCY_STOPPED") color = "#B93829";
        else if (r.current_task_id || (r as any).carrying?.length > 0) color = "#D9533B";

        if (isSelected) {
          // High-contrast outer selection ring + inner accent ring
          ctx.strokeStyle = isLight ? "#241B16" : "#FAF3EE";
          ctx.lineWidth = 2.2;
          ctx.beginPath();
          ctx.arc(cx, cy, 6.4, 0, Math.PI * 2);
          ctx.stroke();

          ctx.strokeStyle = "#D9533B";
          ctx.lineWidth = 1.25;
          ctx.beginPath();
          ctx.arc(cx, cy, 4.8, 0, Math.PI * 2);
          ctx.stroke();
        }

        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(cx, cy, isSelected ? 3.2 : 2.5, 0, Math.PI * 2);
        ctx.fill();
      });

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => {
      cancelAnimationFrame(animId);
      mq?.removeEventListener?.("change", onMqChange);
    };
  }, [showMiniMap]);

  if (!showMiniMap) return null;

  const selectedRobot = selectedRobotId ? robots[selectedRobotId] : null;
  const robotCount = Object.keys(robots).length;

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    const clickX = ((e.clientX - rect.left) / rect.width) * storeWidth;
    const clickY = ((e.clientY - rect.top) / rect.height) * storeHeight;

    // Match rendered center (rx + 0.5, ry + 0.5) using interpolated coordinates
    let nearestId: string | null = null;
    let minDist = 2.0;

    Object.values(robots).forEach((r) => {
      const { rx, ry } = getInterpolatedCoord(r);
      const dist = Math.hypot(rx + 0.5 - clickX, ry + 0.5 - clickY);
      if (dist < minDist) {
        minDist = dist;
        nearestId = r.id;
      }
    });

    if (nearestId) {
      setStore({ selectedRobotId: nearestId });
    }
  };

  return (
    <div
      className="absolute bottom-3 left-3 z-20 studio-card studio-enter stagger-2 rounded-2xl p-2.5 select-none"
      onClick={(e) => e.stopPropagation()}
      onMouseDown={(e) => e.stopPropagation()}
    >
      <div className="flex items-center justify-between gap-2 pb-1.5 mb-2 border-b border-[var(--studio-border)]">
        <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[var(--studio-text-primary)]">
          <Layers className="w-3.5 h-3.5 text-[#B83B24] dark:text-[#E87454]" strokeWidth={1.5} />
          <span>2D Radar</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-[10px] tabular-nums text-[var(--studio-text-muted)]">
            {selectedRobot
              ? `(${selectedRobot.coord?.x ?? 0}, ${selectedRobot.coord?.y ?? 0})`
              : `${robotCount} AMRs`}
          </span>
          <button
            type="button"
            onClick={() => setStore({ showMiniMap: false })}
            className="studio-btn p-1 rounded-lg text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-subtle)] cursor-pointer"
            title="Hide radar"
            aria-label="Hide 2D radar mini-map"
          >
            <X className="w-3.5 h-3.5" strokeWidth={1.5} />
          </button>
        </div>
      </div>

      <canvas
        ref={canvasRef}
        onClick={handleClick}
        className="rounded-[6px] border border-[var(--studio-border-strong)] cursor-crosshair block"
        style={{ width: `${mapWidth}px`, height: `${mapHeight}px` }}
      />
    </div>
  );
};
