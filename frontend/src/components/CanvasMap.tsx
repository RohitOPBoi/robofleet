import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  Eye,
  Layers,
  Maximize2,
  RotateCcw,
  ShieldAlert,
  ZoomIn,
  ZoomOut,
  Crosshair,
  Zap,
} from "lucide-react";
import type { Layout, Robot } from "../types/generated";
import { setStore, useStore } from "../store/useStore";

// Safe coordinate extractor helper
const getPos = (obj: any): { x: number; y: number } => {
  if (!obj) return { x: 0, y: 0 };
  if (obj.pos) return { x: Number(obj.pos.x) || 0, y: Number(obj.pos.y) || 0 };
  if (obj.coord) return { x: Number(obj.coord.x) || 0, y: Number(obj.coord.y) || 0 };
  return { x: Number(obj.x) || 0, y: Number(obj.y) || 0 };
};

export const CanvasMap: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const {
    staticWorld,
    robots,
    alerts,
    selectedRobotId,
    activeOverlays,
    blockModeActive,
    selectedCellsToBlock,
  } = useStore();

  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 40, y: 40 });
  const [zoom, setZoom] = useState<number>(32); // Pixels per grid cell
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const dragStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const [hoveredRobot, setHoveredRobot] = useState<Robot | null>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  const layout: Layout | undefined = staticWorld?.layout;

  // Fit grid to screen callback
  const fitToScreen = useCallback(() => {
    if (!layout || !containerRef.current) return;
    const { clientWidth, clientHeight } = containerRef.current;
    if (clientWidth <= 0 || clientHeight <= 0) return;

    const padding = 48;
    const availableWidth = Math.max(100, clientWidth - padding);
    const availableHeight = Math.max(100, clientHeight - padding);

    const cellWidth = availableWidth / (layout.width || 1);
    const cellHeight = availableHeight / (layout.height || 1);
    const newZoom = Math.max(12, Math.min(cellWidth, cellHeight, 64));

    const totalGridWidth = (layout.width || 1) * newZoom;
    const totalGridHeight = (layout.height || 1) * newZoom;

    setZoom(newZoom);
    setPan({
      x: Math.round((clientWidth - totalGridWidth) / 2),
      y: Math.round((clientHeight - totalGridHeight) / 2),
    });
  }, [layout]);

  // Initial fit & ResizeObserver for dynamic screen changes
  useEffect(() => {
    if (!containerRef.current) return;

    const ro = new ResizeObserver(() => {
      fitToScreen();
    });
    ro.observe(containerRef.current);

    return () => ro.disconnect();
  }, [fitToScreen]);

  // Center Zoom Helper (zooms into the exact center of viewport)
  const zoomByFactor = useCallback((factor: number) => {
    if (!containerRef.current) return;
    const { clientWidth, clientHeight } = containerRef.current;
    const cx = clientWidth / 2;
    const cy = clientHeight / 2;

    setZoom((prevZoom) => {
      const nextZoom = Math.min(Math.max(prevZoom * factor, 12), 120);
      setPan((prevPan) => {
        const dx = cx - prevPan.x;
        const dy = cy - prevPan.y;
        return {
          x: Math.round(cx - dx * (nextZoom / prevZoom)),
          y: Math.round(cy - dy * (nextZoom / prevZoom)),
        };
      });
      return nextZoom;
    });
  }, []);

  // Quick Camera Presets
  const focusPreset = (target: "all" | "stations" | "chargers") => {
    if (!layout || !containerRef.current) return;
    const { clientWidth, clientHeight } = containerRef.current;

    if (target === "all") {
      fitToScreen();
    } else if (target === "stations") {
      const newZoom = 44;
      setZoom(newZoom);
      setPan({
        x: Math.round(clientWidth / 2 - 10 * newZoom),
        y: Math.round(clientHeight / 2 - 17 * newZoom),
      });
    } else if (target === "chargers") {
      const newZoom = 44;
      setZoom(newZoom);
      setPan({
        x: Math.round(clientWidth / 2 - 25 * newZoom),
        y: Math.round(clientHeight / 2 - 5 * newZoom),
      });
    }
  };

  // Native non-passive Wheel Zoom to guarantee smooth zoom towards cursor
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const onWheelNative = (e: WheelEvent) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
      const rect = container.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      setZoom((prevZoom) => {
        const nextZoom = Math.min(Math.max(prevZoom * zoomFactor, 12), 120);
        setPan((prevPan) => {
          const dx = mouseX - prevPan.x;
          const dy = mouseY - prevPan.y;
          return {
            x: Math.round(mouseX - dx * (nextZoom / prevZoom)),
            y: Math.round(mouseY - dy * (nextZoom / prevZoom)),
          };
        });
        return nextZoom;
      });
    };

    container.addEventListener("wheel", onWheelNative, { passive: false });
    return () => container.removeEventListener("wheel", onWheelNative);
  }, []);

  // Dragging Pan Handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    setIsDragging(true);
    dragStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (rect) {
      setMousePos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    }

    if (isDragging) {
      setPan({
        x: e.clientX - dragStartRef.current.x,
        y: e.clientY - dragStartRef.current.y,
      });
      return;
    }

    // Hover detection over AMRs
    if (rect && layout) {
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      let hovered: Robot | null = null;

      for (const r of Object.values(robots)) {
        let rx = r.coord?.x ?? 0;
        let ry = r.coord?.y ?? 0;
        if (r.motion?.from_coord && r.motion?.to_coord) {
          const from = r.motion.from_coord;
          const to = r.motion.to_coord;
          const prog = Math.max(0, Math.min(1, r.motion.progress ?? 0));
          rx = from.x + (to.x - from.x) * prog;
          ry = from.y + (to.y - from.y) * prog;
        }

        const screenRx = pan.x + (rx + 0.5) * zoom;
        const screenRy = pan.y + (ry + 0.5) * zoom;
        const dist = Math.hypot(mouseX - screenRx, mouseY - screenRy);

        if (dist < zoom * 0.55) {
          hovered = r;
          break;
        }
      }
      setHoveredRobot(hovered);
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  // Canvas Click: Cell Blocking or Robot Selection
  const handleClick = (e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect || !layout) return;

    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const cellX = Math.floor((mouseX - pan.x) / zoom);
    const cellY = Math.floor((mouseY - pan.y) / zoom);

    if (cellX < 0 || cellX >= layout.width || cellY < 0 || cellY >= layout.height) return;

    if (blockModeActive) {
      const exists = selectedCellsToBlock.some((c) => c.x === cellX && c.y === cellY);
      const nextCells = exists
        ? selectedCellsToBlock.filter((c) => !(c.x === cellX && c.y === cellY))
        : [...selectedCellsToBlock, { x: cellX, y: cellY }];
      setStore({ selectedCellsToBlock: nextCells });
      return;
    }

    // Check if clicked near an AMR
    let clickedRobotId: string | null = null;
    const robotList = Object.values(robots);
    for (const r of robotList) {
      let rx = r.coord?.x ?? 0;
      let ry = r.coord?.y ?? 0;
      if (r.motion?.from_coord && r.motion?.to_coord) {
        const from = r.motion.from_coord;
        const to = r.motion.to_coord;
        const prog = Math.max(0, Math.min(1, r.motion.progress ?? 0));
        rx = from.x + (to.x - from.x) * prog;
        ry = from.y + (to.y - from.y) * prog;
      }

      const screenRx = pan.x + (rx + 0.5) * zoom;
      const screenRy = pan.y + (ry + 0.5) * zoom;
      const dist = Math.hypot(mouseX - screenRx, mouseY - screenRy);

      if (dist < zoom * 0.55) {
        clickedRobotId = r.id;
        break;
      }
    }

    setStore({ selectedRobotId: clickedRobotId });
  };

  // High-performance 60fps render loop with sub-tick interpolation & robust cell drawing
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !layout) return;

    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;

    let animationFrameId: number;

    const render = () => {
      try {
        if (canvas.width !== canvas.clientWidth || canvas.height !== canvas.clientHeight) {
          canvas.width = canvas.clientWidth;
          canvas.height = canvas.clientHeight;
        }

        // Cyber-dark industrial matte background
        ctx.fillStyle = "#070A10";
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.save();
        ctx.translate(pan.x, pan.y);

        // 1. Draw Grid Cells Base
        ctx.strokeStyle = "rgba(30, 41, 59, 0.45)";
        ctx.lineWidth = 1;

        for (let y = 0; y < layout.height; y++) {
          for (let x = 0; x < layout.width; x++) {
            const px = x * zoom;
            const py = y * zoom;

            ctx.fillStyle = "#0C111D";
            ctx.fillRect(px, py, zoom, zoom);
            ctx.strokeRect(px, py, zoom, zoom);
          }
        }

        // 2. Draw Layout Cells (Shelves, Chargers, Stations, Walls, Floors, Dispatch, Supervisor)
        const cellsList = Array.isArray((layout as any).cells) ? (layout as any).cells : [];

        cellsList.forEach((cell: any) => {
          const p = getPos(cell);
          const px = p.x * zoom;
          const py = p.y * zoom;
          const pad = Math.max(2, zoom * 0.12);
          const ctype = cell.cell_type;

          // Thermal Zones
          if (activeOverlays.showZones && (cell.zone === "CHILLED" || cell.zone === "FROZEN")) {
            ctx.fillStyle =
              cell.zone === "CHILLED"
                ? "rgba(59, 130, 246, 0.08)"
                : "rgba(6, 182, 212, 0.12)";
            ctx.fillRect(px, py, zoom, zoom);
          }

          if (ctype === "SHELF") {
            // High-tech storage racks
            let rackFill = "#161E2E";
            let rackBorder = "#334155";
            if (cell.zone === "CHILLED") {
              rackFill = "#172554";
              rackBorder = "#3B82F6";
            } else if (cell.zone === "FROZEN") {
              rackFill = "#083344";
              rackBorder = "#06B6D4";
            }

            ctx.fillStyle = rackFill;
            ctx.strokeStyle = rackBorder;
            ctx.lineWidth = 1.2;
            ctx.fillRect(px + pad, py + pad, zoom - 2 * pad, zoom - 2 * pad);
            ctx.strokeRect(px + pad, py + pad, zoom - 2 * pad, zoom - 2 * pad);

            // Crossbeam
            ctx.beginPath();
            ctx.moveTo(px + pad, py + zoom / 2);
            ctx.lineTo(px + zoom - pad, py + zoom / 2);
            ctx.stroke();
          } else if (ctype === "WALL") {
            // Perimeter barrier
            ctx.fillStyle = "#111827";
            ctx.strokeStyle = "#1F2937";
            ctx.lineWidth = 1.5;
            ctx.fillRect(px, py, zoom, zoom);
            ctx.strokeRect(px, py, zoom, zoom);
          } else if (ctype === "DISPATCH") {
            // Dispatch Bay
            ctx.fillStyle = "rgba(139, 92, 246, 0.15)";
            ctx.strokeStyle = "#8B5CF6";
            ctx.lineWidth = 1.2;
            ctx.fillRect(px + pad, py + pad, zoom - 2 * pad, zoom - 2 * pad);
            ctx.strokeRect(px + pad, py + pad, zoom - 2 * pad, zoom - 2 * pad);
            if (zoom >= 24) {
              ctx.fillStyle = "#C4B5FD";
              ctx.font = `600 ${Math.max(7, zoom * 0.22)}px monospace`;
              ctx.textAlign = "center";
              ctx.textBaseline = "middle";
              ctx.fillText("BAY", px + zoom / 2, py + zoom / 2);
            }
          } else if (ctype === "SUPERVISOR_DESK") {
            // Supervisor Desk
            ctx.fillStyle = "rgba(245, 158, 11, 0.2)";
            ctx.strokeStyle = "#F59E0B";
            ctx.lineWidth = 1.5;
            ctx.fillRect(px + pad, py + pad, zoom - 2 * pad, zoom - 2 * pad);
            ctx.strokeRect(px + pad, py + pad, zoom - 2 * pad, zoom - 2 * pad);
            if (zoom >= 24) {
              ctx.fillStyle = "#FDE68A";
              ctx.font = `700 ${Math.max(7, zoom * 0.22)}px monospace`;
              ctx.textAlign = "center";
              ctx.textBaseline = "middle";
              ctx.fillText("DESK", px + zoom / 2, py + zoom / 2);
            }
          } else if (ctype === "PARKING") {
            // Parking Spots
            ctx.fillStyle = "rgba(59, 130, 246, 0.08)";
            ctx.strokeStyle = "rgba(59, 130, 246, 0.3)";
            ctx.lineWidth = 1;
            ctx.fillRect(px + pad, py + pad, zoom - 2 * pad, zoom - 2 * pad);
            ctx.strokeRect(px + pad, py + pad, zoom - 2 * pad, zoom - 2 * pad);
            if (zoom >= 22) {
              ctx.fillStyle = "rgba(147, 197, 253, 0.5)";
              ctx.font = `600 ${Math.max(7, zoom * 0.22)}px monospace`;
              ctx.textAlign = "center";
              ctx.textBaseline = "middle";
              ctx.fillText("P", px + zoom / 2, py + zoom / 2);
            }
          }
        });

        // 3. Draw Dedicated Chargers
        const chargersList = Array.isArray((layout as any).chargers) ? (layout as any).chargers : [];
        chargersList.forEach((ch: any) => {
          const p = getPos(ch);
          const px = p.x * zoom;
          const py = p.y * zoom;
          const pad = Math.max(2, zoom * 0.15);

          ctx.fillStyle = "rgba(245, 158, 11, 0.14)";
          ctx.strokeStyle = "#F59E0B";
          ctx.lineWidth = 1.4;
          ctx.fillRect(px + pad, py + pad, zoom - 2 * pad, zoom - 2 * pad);
          ctx.strokeRect(px + pad, py + pad, zoom - 2 * pad, zoom - 2 * pad);

          // Lightning icon
          const mx = px + zoom / 2;
          const my = py + zoom / 2;
          const s = Math.max(4, zoom * 0.22);
          ctx.fillStyle = "#F59E0B";
          ctx.beginPath();
          ctx.moveTo(mx + s * 0.1, my - s);
          ctx.lineTo(mx - s * 0.6, my + s * 0.1);
          ctx.lineTo(mx - s * 0.05, my + s * 0.1);
          ctx.lineTo(mx - s * 0.2, my + s);
          ctx.lineTo(mx + s * 0.6, my - s * 0.1);
          ctx.lineTo(mx + s * 0.05, my - s * 0.1);
          ctx.closePath();
          ctx.fill();
        });

        // 4. Draw Picking Stations
        const stationsList = Array.isArray((layout as any).stations)
          ? (layout as any).stations
          : Array.isArray((layout as any).pick_stations)
          ? (layout as any).pick_stations
          : [];

        stationsList.forEach((st: any) => {
          const p = getPos(st);
          const px = p.x * zoom;
          const py = p.y * zoom;
          const pad = Math.max(2, zoom * 0.1);

          ctx.fillStyle = "rgba(16, 185, 129, 0.16)";
          ctx.strokeStyle = "#10B981";
          ctx.lineWidth = 1.5;
          ctx.fillRect(px + pad, py + pad, zoom - 2 * pad, zoom - 2 * pad);
          ctx.strokeRect(px + pad, py + pad, zoom - 2 * pad, zoom - 2 * pad);

          ctx.fillStyle = "#10B981";
          ctx.font = `700 ${Math.max(8, zoom * 0.26)}px monospace`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          const label = st.station_id ? st.station_id.replace("ST-", "S") : "PICK";
          ctx.fillText(label, px + zoom / 2, py + zoom / 2);
        });

        // 5. Draw Blocked Cells (from layout or active selection)
        selectedCellsToBlock.forEach((c) => {
          const px = c.x * zoom;
          const py = c.y * zoom;

          ctx.fillStyle = "rgba(239, 68, 68, 0.35)";
          ctx.fillRect(px, py, zoom, zoom);
          ctx.strokeStyle = "#EF4444";
          ctx.lineWidth = 1.4;
          ctx.strokeRect(px, py, zoom, zoom);

          // Cross
          ctx.beginPath();
          ctx.moveTo(px, py);
          ctx.lineTo(px + zoom, py + zoom);
          ctx.moveTo(px + zoom, py);
          ctx.lineTo(px, py + zoom);
          ctx.stroke();
        });

        // 6. Draw Directional Flow Arrows if enabled
        if (activeOverlays.showFlowArrows) {
          ctx.strokeStyle = "rgba(100, 116, 139, 0.3)";
          ctx.fillStyle = "rgba(100, 116, 139, 0.3)";
          ctx.lineWidth = 1.2;

          cellsList.forEach((cell: any) => {
            const flow = cell.flow || cell.aisle_dir;
            if (flow && flow !== "BOTH" && cell.cell_type === "FLOOR") {
              const p = getPos(cell);
              const cx = (p.x + 0.5) * zoom;
              const cy = (p.y + 0.5) * zoom;
              const arrowSize = zoom * 0.18;

              ctx.save();
              ctx.translate(cx, cy);

              let angle = 0;
              if (flow === "E" || flow === "EAST") angle = 0;
              else if (flow === "S" || flow === "SOUTH") angle = Math.PI / 2;
              else if (flow === "W" || flow === "WEST") angle = Math.PI;
              else if (flow === "N" || flow === "NORTH") angle = -Math.PI / 2;

              ctx.rotate(angle);
              ctx.beginPath();
              ctx.moveTo(-arrowSize, -arrowSize * 0.5);
              ctx.lineTo(arrowSize, 0);
              ctx.lineTo(-arrowSize, arrowSize * 0.5);
              ctx.stroke();
              ctx.restore();
            }
          });
        }

        // 7. Draw Trajectory Line for Selected AMR
        if (selectedRobotId && robots[selectedRobotId]) {
          const sr = robots[selectedRobotId];
          let rx = sr.coord?.x ?? 0;
          let ry = sr.coord?.y ?? 0;
          if (sr.motion?.from_coord && sr.motion?.to_coord) {
            const from = sr.motion.from_coord;
            const to = sr.motion.to_coord;
            const prog = Math.max(0, Math.min(1, sr.motion.progress ?? 0));
            rx = from.x + (to.x - from.x) * prog;
            ry = from.y + (to.y - from.y) * prog;
          }

          const scx = (rx + 0.5) * zoom;
          const scy = (ry + 0.5) * zoom;

          if (sr.motion?.to_coord) {
            const tcx = (sr.motion.to_coord.x + 0.5) * zoom;
            const tcy = (sr.motion.to_coord.y + 0.5) * zoom;

            ctx.save();
            ctx.setLineDash([4, 4]);
            ctx.strokeStyle = "#00F0FF";
            ctx.lineWidth = 1.8;
            ctx.beginPath();
            ctx.moveTo(scx, scy);
            ctx.lineTo(tcx, tcy);
            ctx.stroke();
            ctx.restore();
          }
        }

        // 8. Draw AMRs (Robots) with Sub-Tick Progress Interpolation & GenZ Glow
        const robotList = Object.values(robots);
        robotList.forEach((r: Robot) => {
          let rx = r.coord?.x ?? 0;
          let ry = r.coord?.y ?? 0;
          if (r.motion?.from_coord && r.motion?.to_coord) {
            const from = r.motion.from_coord;
            const to = r.motion.to_coord;
            const prog = Math.max(0, Math.min(1, r.motion.progress ?? 0));
            rx = from.x + (to.x - from.x) * prog;
            ry = from.y + (to.y - from.y) * prog;
          }

          const cx = (rx + 0.5) * zoom;
          const cy = (ry + 0.5) * zoom;
          const radius = Math.max(7, zoom * 0.38);

          const isSelected = selectedRobotId === r.id;
          const isHovered = hoveredRobot?.id === r.id;

          // AMR State Status Accent Color
          let amrBorder = "#10B981"; // Moving / Idle
          let glowColor = "rgba(16, 185, 129, 0.4)";
          if (r.state === "CHARGING") {
            amrBorder = "#F59E0B";
            glowColor = "rgba(245, 158, 11, 0.4)";
          } else if (r.state === "FAULTED" || r.state === "EMERGENCY_STOPPED") {
            amrBorder = "#EF4444";
            glowColor = "rgba(239, 68, 68, 0.5)";
          } else if (String(r.state).includes("PICK") || String(r.state).includes("DROP") || r.current_task_id) {
            amrBorder = "#06B6D4";
            glowColor = "rgba(6, 182, 212, 0.4)";
          }

          // Pulsing Target Reticle if selected
          if (isSelected) {
            ctx.save();
            ctx.beginPath();
            ctx.arc(cx, cy, radius + 5, 0, 2 * Math.PI);
            ctx.strokeStyle = "#00F0FF";
            ctx.lineWidth = 2.2;
            ctx.shadowColor = "#00F0FF";
            ctx.shadowBlur = 10;
            ctx.stroke();
            ctx.restore();
          }

          // Hover highlight
          if (isHovered && !isSelected) {
            ctx.beginPath();
            ctx.arc(cx, cy, radius + 3, 0, 2 * Math.PI);
            ctx.strokeStyle = "rgba(255, 255, 255, 0.5)";
            ctx.lineWidth = 1.5;
            ctx.stroke();
          }

          // AMR Outer Chassis with cyber glow
          ctx.save();
          ctx.beginPath();
          ctx.arc(cx, cy, radius, 0, 2 * Math.PI);
          ctx.fillStyle = "#0F172A";
          ctx.shadowColor = glowColor;
          ctx.shadowBlur = 6;
          ctx.fill();
          ctx.strokeStyle = amrBorder;
          ctx.lineWidth = 2;
          ctx.stroke();
          ctx.restore();

          // Circular Battery Percentage Gauge Arc
          const batteryPct = Math.max(0, Math.min(100, r.battery_percent ?? 100));
          const batteryAngle = (batteryPct / 100) * 2 * Math.PI;
          ctx.beginPath();
          ctx.arc(cx, cy, Math.max(3, radius - 3.2), -Math.PI / 2, -Math.PI / 2 + batteryAngle);
          ctx.strokeStyle = batteryPct > 50 ? "#10B981" : batteryPct > 20 ? "#F59E0B" : "#EF4444";
          ctx.lineWidth = 2;
          ctx.stroke();

          // Heading Laser Indicator
          const headingRad = ((r.heading_deg ?? 0) * Math.PI) / 180;
          const hLen = radius * 0.8;
          const hx = cx + Math.cos(headingRad) * hLen;
          const hy = cy + Math.sin(headingRad) * hLen;

          ctx.beginPath();
          ctx.moveTo(cx, cy);
          ctx.lineTo(hx, hy);
          ctx.strokeStyle = "#FFFFFF";
          ctx.lineWidth = 2;
          ctx.stroke();

          // Carrying Tote indicator (Vibrant electric purple box)
          if (r.current_task_id) {
            const bx = cx + radius * 0.55;
            const by = cy - radius * 0.55;
            ctx.save();
            ctx.fillStyle = "#A855F7";
            ctx.shadowColor = "#A855F7";
            ctx.shadowBlur = 4;
            ctx.fillRect(bx - 4, by - 4, 8, 8);
            ctx.strokeStyle = "#FFFFFF";
            ctx.lineWidth = 1;
            ctx.strokeRect(bx - 4, by - 4, 8, 8);
            ctx.restore();
          }

          // AMR Short ID Badge
          if (zoom >= 20 || isSelected) {
            ctx.fillStyle = "#F8FAFC";
            ctx.font = `700 ${Math.max(9, zoom * 0.28)}px monospace`;
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            const shortId = r.id.replace("ROBOT-", "R-");
            ctx.fillText(shortId, cx, cy - radius - 5);
          }
        });

        // 9. Draw Active Alerts on Map
        alerts.forEach((alert) => {
          if (alert.coord && !alert.cleared) {
            const ax = (alert.coord.x + 0.5) * zoom;
            const ay = (alert.coord.y + 0.5) * zoom;
            const s = Math.max(5, zoom * 0.3);

            ctx.save();
            ctx.beginPath();
            ctx.arc(ax, ay, s + 4, 0, 2 * Math.PI);
            ctx.fillStyle =
              alert.severity === "CRITICAL" ? "rgba(239, 68, 68, 0.3)" : "rgba(245, 158, 11, 0.3)";
            ctx.shadowColor = alert.severity === "CRITICAL" ? "#EF4444" : "#F59E0B";
            ctx.shadowBlur = 8;
            ctx.fill();

            // Triangle
            ctx.beginPath();
            ctx.moveTo(ax, ay - s);
            ctx.lineTo(ax + s, ay + s);
            ctx.lineTo(ax - s, ay + s);
            ctx.closePath();
            ctx.fillStyle = alert.severity === "CRITICAL" ? "#EF4444" : "#F59E0B";
            ctx.fill();

            // Exclamation mark
            ctx.fillStyle = "#FFFFFF";
            ctx.fillRect(ax - 0.75, ay - s * 0.35, 1.5, s * 0.6);
            ctx.fillRect(ax - 0.75, ay + s * 0.55, 1.5, 1.5);
            ctx.restore();
          }
        });

        ctx.restore();
      } catch (err) {
        console.error("Canvas render error caught:", err);
      } finally {
        animationFrameId = requestAnimationFrame(render);
      }
    };

    animationFrameId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animationFrameId);
  }, [
    layout,
    robots,
    alerts,
    pan,
    zoom,
    selectedRobotId,
    hoveredRobot,
    activeOverlays,
    blockModeActive,
    selectedCellsToBlock,
  ]);

  return (
    <div
      ref={containerRef}
      className="relative flex-1 h-full w-full bg-gray-950 overflow-hidden select-none cursor-grab active:cursor-grabbing"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onClick={handleClick}
    >
      <canvas ref={canvasRef} className="w-full h-full block" />

      {/* Floating AMR Hover Tooltip */}
      {hoveredRobot && (
        <div
          className="absolute pointer-events-none z-30 px-2.5 py-1.5 rounded-lg bg-gray-950/95 border border-cyan-500/50 shadow-2xl backdrop-blur-md text-[11px] font-mono text-gray-200"
          style={{
            left: Math.min(mousePos.x + 16, (containerRef.current?.clientWidth ?? 800) - 160),
            top: Math.max(mousePos.y - 48, 16),
          }}
        >
          <div className="flex items-center gap-1.5 font-bold text-cyan-400">
            <span>{hoveredRobot.id}</span>
            <span className="text-[9px] px-1 rounded bg-gray-800 text-gray-300 font-normal">
              {hoveredRobot.state}
            </span>
          </div>
          <div className="flex items-center gap-2 text-gray-400 text-[10px] mt-0.5">
            <span>⚡ {Math.round(hoveredRobot.battery_percent ?? 100)}%</span>
            <span>📍 ({hoveredRobot.coord?.x ?? 0}, {hoveredRobot.coord?.y ?? 0})</span>
            {hoveredRobot.current_task_id && <span className="text-purple-400">📦 Tote Loaded</span>}
          </div>
        </div>
      )}

      {/* Modern GenZ Floating HUD Controls */}
      <div
        className="absolute bottom-4 left-4 flex items-center gap-1.5 bg-gray-900/90 border border-white/10 backdrop-blur-xl rounded-xl p-1.5 text-xs shadow-2xl z-20"
        onMouseDown={(e) => e.stopPropagation()}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Zoom Controls */}
        <div className="flex items-center gap-0.5 bg-gray-950/60 rounded-lg p-0.5 border border-white/5">
          <button
            type="button"
            onClick={() => zoomByFactor(1.25)}
            className="p-1.5 text-gray-300 hover:text-white hover:bg-white/10 rounded-md transition active:scale-95 cursor-pointer"
            title="Zoom in (+)"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => zoomByFactor(0.8)}
            className="p-1.5 text-gray-300 hover:text-white hover:bg-white/10 rounded-md transition active:scale-95 cursor-pointer"
            title="Zoom out (-)"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={fitToScreen}
            className="p-1.5 text-gray-300 hover:text-white hover:bg-white/10 rounded-md transition active:scale-95 cursor-pointer"
            title="Fit warehouse to screen"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => {
              setZoom(32);
              setPan({ x: 40, y: 40 });
            }}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded-md transition active:scale-95 cursor-pointer"
            title="Reset pan & zoom"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="h-4 w-px bg-white/10" />

        {/* Camera Preset Quick Pills */}
        <div className="hidden sm:flex items-center gap-1 font-mono text-[10px]">
          <button
            type="button"
            onClick={() => focusPreset("stations")}
            className="px-2 py-1 rounded bg-gray-950/60 hover:bg-emerald-950/60 text-gray-400 hover:text-emerald-300 border border-white/5 hover:border-emerald-700/50 transition cursor-pointer"
            title="Center view on picking stations"
          >
            Stations
          </button>
          <button
            type="button"
            onClick={() => focusPreset("chargers")}
            className="px-2 py-1 rounded bg-gray-950/60 hover:bg-amber-950/60 text-gray-400 hover:text-amber-300 border border-white/5 hover:border-amber-700/50 transition cursor-pointer"
            title="Center view on charger bank"
          >
            Chargers
          </button>
        </div>

        <div className="h-4 w-px bg-white/10" />

        {/* Overlays */}
        <button
          type="button"
          onClick={() =>
            setStore({
              activeOverlays: {
                ...activeOverlays,
                showFlowArrows: !activeOverlays.showFlowArrows,
              },
            })
          }
          className={`p-1.5 rounded-lg transition active:scale-95 cursor-pointer ${
            activeOverlays.showFlowArrows
              ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
              : "text-gray-400 hover:text-white hover:bg-white/5"
          }`}
          title="Toggle aisle flow arrows"
        >
          <Eye className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={() =>
            setStore({
              activeOverlays: {
                ...activeOverlays,
                showZones: !activeOverlays.showZones,
              },
            })
          }
          className={`p-1.5 rounded-lg transition active:scale-95 cursor-pointer ${
            activeOverlays.showZones
              ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
              : "text-gray-400 hover:text-white hover:bg-white/5"
          }`}
          title="Toggle temperature zones"
        >
          <Layers className="w-4 h-4" />
        </button>

        <div className="h-4 w-px bg-white/10" />

        {/* Block Tool */}
        <button
          type="button"
          onClick={() =>
            setStore({
              blockModeActive: !blockModeActive,
              selectedCellsToBlock: [],
            })
          }
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg transition font-medium text-xs active:scale-95 cursor-pointer ${
            blockModeActive
              ? "bg-red-600 text-white shadow-lg shadow-red-600/30 font-bold"
              : "text-gray-300 hover:text-white hover:bg-white/5 border border-white/5"
          }`}
          title="Toggle block cell tool (Click grid cells to block)"
        >
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>Block</span>
        </button>
      </div>

      {/* Block Tool Action Bar */}
      {blockModeActive && (
        <div
          className="absolute top-4 left-1/2 -translate-x-1/2 bg-red-950/95 border border-red-800/80 backdrop-blur-xl rounded-xl px-4 py-2 flex items-center gap-3 text-xs shadow-2xl z-20 animate-in fade-in slide-in-from-top-2"
          onMouseDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
        >
          <ShieldAlert className="w-4 h-4 text-red-400" />
          <span className="text-red-200">
            Click cells on grid. <strong>{selectedCellsToBlock.length}</strong> selected.
          </span>
          <button
            type="button"
            onClick={() => setStore({ isEStopModalOpen: true })}
            disabled={selectedCellsToBlock.length === 0}
            className="px-2.5 py-1 bg-red-600 hover:bg-red-500 disabled:opacity-40 text-white font-semibold rounded-lg transition cursor-pointer"
          >
            Block selected
          </button>
          <button
            type="button"
            onClick={() => setStore({ blockModeActive: false, selectedCellsToBlock: [] })}
            className="px-2 py-1 text-gray-400 hover:text-white transition cursor-pointer"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
};
