/**
 * MiniMap2D: Picture-in-Picture 2D HUD radar overlay for Scene3D.
 * Provides high-speed tactical spatial awareness, robot position pips,
 * active alert rings, and one-click robot targeting.
 */

import React, { useEffect, useRef } from "react";
import { Layers, X } from "lucide-react";
import { setStore, useStore } from "../../store/useStore";

const getPos = (obj: any): { x: number; y: number } => {
  if (!obj) return { x: 0, y: 0 };
  if (obj.pos) return { x: Number(obj.pos.x) || 0, y: Number(obj.pos.y) || 0 };
  if (obj.coord) return { x: Number(obj.coord.x) || 0, y: Number(obj.coord.y) || 0 };
  return { x: Number(obj.x) || 0, y: Number(obj.y) || 0 };
};

export const MiniMap2D: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const { staticWorld, robots, alerts, selectedRobotId, showMiniMap } = useStore();

  const layout = staticWorld?.layout;
  const storeWidth = layout?.width ?? 28;
  const storeHeight = layout?.height ?? 20;

  // Mini-map dimensions
  const mapWidth = 200;
  const mapHeight = Math.round((mapWidth * storeHeight) / storeWidth);
  const scale = mapWidth / storeWidth;

  useEffect(() => {
    if (!showMiniMap) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;

    const render = () => {
      ctx.clearRect(0, 0, mapWidth, mapHeight);

      // 1. Dark floor background
      ctx.fillStyle = "#070A10";
      ctx.fillRect(0, 0, mapWidth, mapHeight);

      // Subtle grid
      ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
      ctx.lineWidth = 0.5;
      for (let x = 0; x <= storeWidth; x += 4) {
        ctx.beginPath();
        ctx.moveTo(x * scale, 0);
        ctx.lineTo(x * scale, mapHeight);
        ctx.stroke();
      }
      for (let y = 0; y <= storeHeight; y += 4) {
        ctx.beginPath();
        ctx.moveTo(0, y * scale);
        ctx.lineTo(mapWidth, y * scale);
        ctx.stroke();
      }

      // 2. Shelf footprints
      const cells = Array.isArray((layout as any)?.cells) ? (layout as any).cells : [];
      cells.forEach((cell: any) => {
        if (cell.cell_type === "SHELF") {
          const p = getPos(cell);
          ctx.fillStyle = cell.zone === "FROZEN" ? "#0e7490" : cell.zone === "CHILLED" ? "#1e3a8a" : "#1e293b";
          ctx.fillRect(p.x * scale, p.y * scale, scale * 0.9, scale * 0.9);
        }
      });

      // 3. Stations & Chargers
      const stations = Array.isArray((layout as any)?.stations)
        ? (layout as any).stations
        : (layout as any)?.pick_stations || [];
      ctx.fillStyle = "#059669";
      stations.forEach((s: any) => {
        const p = getPos(s);
        ctx.fillRect(p.x * scale, p.y * scale, scale * 0.9, scale * 0.9);
      });

      const chargers = Array.isArray((layout as any)?.chargers) ? (layout as any).chargers : [];
      ctx.fillStyle = "#d97706";
      chargers.forEach((c: any) => {
        const p = getPos(c);
        ctx.fillRect(p.x * scale, p.y * scale, scale * 0.9, scale * 0.9);
      });

      // 4. Alert Beacons
      const now = performance.now() / 1000;
      alerts.forEach((alert) => {
        if (alert.cleared || !alert.coord) return;
        const ax = alert.coord.x * scale + scale / 2;
        const ay = alert.coord.y * scale + scale / 2;
        const isCritical = alert.severity === "CRITICAL";

        // Pulsing ring
        const pulse = 4 + 3 * Math.sin(now * 6);
        ctx.strokeStyle = isCritical ? "rgba(239, 68, 68, 0.8)" : "rgba(245, 158, 11, 0.8)";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(ax, ay, pulse, 0, Math.PI * 2);
        ctx.stroke();

        ctx.fillStyle = isCritical ? "#EF4444" : "#F59E0B";
        ctx.beginPath();
        ctx.arc(ax, ay, 2, 0, Math.PI * 2);
        ctx.fill();
      });

      // 5. Robots
      Object.values(robots).forEach((r) => {
        let rx = r.coord?.x ?? 0;
        let ry = r.coord?.y ?? 0;
        if (r.motion?.from_coord && r.motion?.to_coord) {
          const prog = Math.max(0, Math.min(1, r.motion.progress ?? 0));
          rx = r.motion.from_coord.x + (r.motion.to_coord.x - r.motion.from_coord.x) * prog;
          ry = r.motion.from_coord.y + (r.motion.to_coord.y - r.motion.from_coord.y) * prog;
        }

        const cx = rx * scale + scale / 2;
        const cy = ry * scale + scale / 2;
        const isSelected = selectedRobotId === r.id;

        // Robot dot color
        let color = "#10B981";
        if (r.state === "CHARGING") color = "#F59E0B";
        else if (r.state === "FAULTED" || r.state === "EMERGENCY_STOPPED") color = "#EF4444";
        else if (r.current_task_id || (r as any).carrying?.length > 0) color = "#A855F7";

        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(cx, cy, isSelected ? 3.5 : 2.5, 0, Math.PI * 2);
        ctx.fill();

        if (isSelected) {
          ctx.strokeStyle = "#00F0FF";
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.arc(cx, cy, 6, 0, Math.PI * 2);
          ctx.stroke();
        }
      });

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [showMiniMap, layout, robots, alerts, selectedRobotId, storeWidth, storeHeight, scale, mapWidth, mapHeight]);

  if (!showMiniMap) return null;

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = (e.clientX - rect.left) / scale;
    const clickY = (e.clientY - rect.top) / scale;

    // Find nearest robot within 2 grid units
    let nearestId: string | null = null;
    let minDist = 2.0;

    Object.values(robots).forEach((r) => {
      const rx = r.coord?.x ?? 0;
      const ry = r.coord?.y ?? 0;
      const dist = Math.hypot(rx - clickX, ry - clickY);
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
      className="absolute bottom-4 left-4 z-20 bg-gray-950/90 border border-white/10 rounded-xl p-2 shadow-2xl backdrop-blur-xl select-none"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="flex items-center justify-between pb-1.5 mb-1.5 border-b border-white/10 text-[10px] font-mono text-gray-400">
        <div className="flex items-center gap-1 text-cyan-400 font-bold">
          <Layers className="w-3 h-3" />
          <span>2D RADAR</span>
        </div>
        <button
          type="button"
          onClick={() => setStore({ showMiniMap: false })}
          className="p-0.5 rounded text-gray-400 hover:text-white hover:bg-white/10 transition cursor-pointer"
          title="Hide radar"
          aria-label="Hide radar"
        >
          <X className="w-3 h-3" />
        </button>
      </div>

      <canvas
        ref={canvasRef}
        width={mapWidth}
        height={mapHeight}
        onClick={handleClick}
        className="rounded border border-white/5 cursor-crosshair block"
        style={{ width: `${mapWidth}px`, height: `${mapHeight}px` }}
      />
    </div>
  );
};
