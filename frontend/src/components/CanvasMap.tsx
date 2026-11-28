import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  Eye,
  Layers,
  MapPin,
  Maximize2,
  Package,
  RotateCcw,
  ShieldAlert,
  Zap,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import type { Layout, Robot } from "../types/generated";
import { setStore, useStore } from "../store/useStore";

export interface CanvasMapProps {
  compact?: boolean;
}

// Safe coordinate extractor helper
const getPos = (obj: any): { x: number; y: number } => {
  if (!obj) return { x: 0, y: 0 };
  if (obj.pos) return { x: Number(obj.pos.x) || 0, y: Number(obj.pos.y) || 0 };
  if (obj.coord) return { x: Number(obj.coord.x) || 0, y: Number(obj.coord.y) || 0 };
  return { x: Number(obj.x) || 0, y: Number(obj.y) || 0 };
};

function getInterpolatedRobotCoord(r: Robot): { rx: number; ry: number } {
  let rx = r.coord?.x ?? 0;
  let ry = r.coord?.y ?? 0;
  if (r.motion?.from_coord && r.motion?.to_coord) {
    const from = r.motion.from_coord;
    const to = r.motion.to_coord;
    const prog = Math.max(0, Math.min(1, r.motion.progress ?? 0));
    rx = from.x + (to.x - from.x) * prog;
    ry = from.y + (to.y - from.y) * prog;
  }
  return { rx, ry };
}

function drawContrastBadge(
  ctx: CanvasRenderingContext2D,
  text: string,
  cx: number,
  cy: number,
  fontSize: number,
  bgColor: string,
  textColor: string,
  borderColor?: string
) {
  ctx.font = `700 ${fontSize}px "JetBrains Mono", monospace`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const metrics = ctx.measureText(text);
  const padX = Math.max(3.5, fontSize * 0.4);
  const padY = Math.max(2, fontSize * 0.24);
  const w = metrics.width + padX * 2;
  const h = fontSize + padY * 2;
  const x = cx - w / 2;
  const y = cy - h / 2;
  const r = Math.min(4, h / 2);

  ctx.beginPath();
  if (typeof ctx.roundRect === "function") {
    ctx.roundRect(x, y, w, h, r);
  } else {
    ctx.rect(x, y, w, h);
  }
  ctx.fillStyle = bgColor;
  ctx.fill();
  if (borderColor) {
    ctx.strokeStyle = borderColor;
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  ctx.fillStyle = textColor;
  ctx.fillText(text, cx, cy + 0.5);
}

export const CanvasMap: React.FC<CanvasMapProps> = ({ compact = false }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);

  const {
    staticWorld,
    robots,
    alerts,
    selectedRobotId,
    activeOverlays,
    blockModeActive,
    selectedCellsToBlock,
    activeFaults,
    theme,
  } = useStore();

  const [zoom, setZoom] = useState<number>(32); // Pixels per grid cell
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [hoveredRobot, setHoveredRobot] = useState<Robot | null>(null);

  const panRef = useRef<{ x: number; y: number }>({ x: 40, y: 40 });
  const zoomRef = useRef<number>(32);
  const isDraggingRef = useRef<boolean>(false);
  const dragStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const hoveredRobotIdRef = useRef<string | null>(null);
  const mousePosRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  const layout: Layout | undefined = staticWorld?.layout;

  // Live render snapshot ref so rAF never tears down on hover/pan/telemetry updates
  const renderStateRef = useRef({
    layout,
    robots,
    alerts,
    selectedRobotId,
    activeOverlays,
    blockModeActive,
    selectedCellsToBlock,
    activeFaults,
    theme,
  });

  renderStateRef.current = {
    layout,
    robots,
    alerts,
    selectedRobotId,
    activeOverlays,
    blockModeActive,
    selectedCellsToBlock,
    activeFaults,
    theme,
  };

  const computeTooltipTransform = useCallback((mx: number, my: number) => {
    const w = containerRef.current?.clientWidth ?? 800;
    const h = containerRef.current?.clientHeight ?? 500;
    const tx = Math.max(10, Math.min(mx + 14, w - 210));
    const ty = Math.max(10, Math.min(my - 54, h - 72));
    return `translate3d(${Math.round(tx)}px, ${Math.round(ty)}px, 0)`;
  }, []);

  // Fit grid to screen callback
  const fitToScreen = useCallback(() => {
    if (!layout || !containerRef.current) return;
    const { clientWidth, clientHeight } = containerRef.current;
    if (clientWidth <= 0 || clientHeight <= 0) return;

    const padding = compact ? 20 : 48;
    const availableWidth = Math.max(100, clientWidth - padding);
    const availableHeight = Math.max(100, clientHeight - padding);

    const cellWidth = availableWidth / (layout.width || 1);
    const cellHeight = availableHeight / (layout.height || 1);
    const newZoom = Math.max(10, Math.min(cellWidth, cellHeight, 64));

    const totalGridWidth = (layout.width || 1) * newZoom;
    const totalGridHeight = (layout.height || 1) * newZoom;

    zoomRef.current = newZoom;
    panRef.current = {
      x: Math.round((clientWidth - totalGridWidth) / 2),
      y: Math.round((clientHeight - totalGridHeight) / 2),
    };
    setZoom(newZoom);
  }, [layout, compact]);

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

    const prevZoom = zoomRef.current;
    const nextZoom = Math.min(Math.max(prevZoom * factor, 10), 120);
    const prevPan = panRef.current;
    const dx = cx - prevPan.x;
    const dy = cy - prevPan.y;

    panRef.current = {
      x: Math.round(cx - dx * (nextZoom / prevZoom)),
      y: Math.round(cy - dy * (nextZoom / prevZoom)),
    };
    zoomRef.current = nextZoom;
    setZoom(nextZoom);
  }, []);

  // Quick Camera Presets
  const focusPreset = (target: "all" | "stations" | "chargers") => {
    if (!layout || !containerRef.current) return;
    const { clientWidth, clientHeight } = containerRef.current;

    if (target === "all") {
      fitToScreen();
    } else if (target === "stations") {
      const newZoom = 44;
      zoomRef.current = newZoom;
      panRef.current = {
        x: Math.round(clientWidth / 2 - 10 * newZoom),
        y: Math.round(clientHeight / 2 - 17 * newZoom),
      };
      setZoom(newZoom);
    } else if (target === "chargers") {
      const newZoom = 44;
      zoomRef.current = newZoom;
      panRef.current = {
        x: Math.round(clientWidth / 2 - 25 * newZoom),
        y: Math.round(clientHeight / 2 - 5 * newZoom),
      };
      setZoom(newZoom);
    }
  };

  // Native non-passive Wheel Zoom (disabled in compact mode so page scroll isn't hijacked)
  useEffect(() => {
    if (compact) return;
    const container = containerRef.current;
    if (!container) return;

    const onWheelNative = (e: WheelEvent) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
      const rect = container.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const prevZoom = zoomRef.current;
      const nextZoom = Math.min(Math.max(prevZoom * zoomFactor, 10), 120);
      const prevPan = panRef.current;
      const dx = mouseX - prevPan.x;
      const dy = mouseY - prevPan.y;

      panRef.current = {
        x: Math.round(mouseX - dx * (nextZoom / prevZoom)),
        y: Math.round(mouseY - dy * (nextZoom / prevZoom)),
      };
      zoomRef.current = nextZoom;
      setZoom(nextZoom);
    };

    container.addEventListener("wheel", onWheelNative, { passive: false });
    return () => container.removeEventListener("wheel", onWheelNative);
  }, [compact]);

  // Dragging Pan Handlers (zero React state churn during pan/hover move)
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    isDraggingRef.current = true;
    setIsDragging(true);
    dragStartRef.current = {
      x: e.clientX - panRef.current.x,
      y: e.clientY - panRef.current.y,
    };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (rect) {
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      mousePosRef.current = { x: mx, y: my };
      if (tooltipRef.current) {
        tooltipRef.current.style.transform = computeTooltipTransform(mx, my);
      }
    }

    if (isDraggingRef.current) {
      panRef.current = {
        x: e.clientX - dragStartRef.current.x,
        y: e.clientY - dragStartRef.current.y,
      };
      return;
    }

    // Hover detection over AMRs
    if (rect && layout) {
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      const curPan = panRef.current;
      const curZoom = zoomRef.current;
      let hovered: Robot | null = null;

      for (const r of Object.values(robots)) {
        const { rx, ry } = getInterpolatedRobotCoord(r);
        const screenRx = curPan.x + (rx + 0.5) * curZoom;
        const screenRy = curPan.y + (ry + 0.5) * curZoom;
        const dist = Math.hypot(mouseX - screenRx, mouseY - screenRy);

        if (dist < curZoom * 0.55) {
          hovered = r;
          break;
        }
      }

      const nextId = hovered?.id ?? null;
      if (nextId !== hoveredRobotIdRef.current) {
        hoveredRobotIdRef.current = nextId;
        setHoveredRobot(hovered);
      }
    }
  };

  const handleMouseUp = () => {
    if (isDraggingRef.current) {
      isDraggingRef.current = false;
      setIsDragging(false);
    }
  };

  const handleMouseLeave = () => {
    handleMouseUp();
    if (hoveredRobotIdRef.current !== null) {
      hoveredRobotIdRef.current = null;
      setHoveredRobot(null);
    }
  };

  // Canvas Click: Cell Blocking or Robot Selection
  const handleClick = (e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect || !layout) return;

    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    const curPan = panRef.current;
    const curZoom = zoomRef.current;

    const cellX = Math.floor((mouseX - curPan.x) / curZoom);
    const cellY = Math.floor((mouseY - curPan.y) / curZoom);

    if (cellX < 0 || cellX >= layout.width || cellY < 0 || cellY >= layout.height) return;

    if (blockModeActive && !compact) {
      const exists = selectedCellsToBlock.some((c) => c.x === cellX && c.y === cellY);
      const nextCells = exists
        ? selectedCellsToBlock.filter((c) => !(c.x === cellX && c.y === cellY))
        : [...selectedCellsToBlock, { x: cellX, y: cellY }];
      setStore({ selectedCellsToBlock: nextCells });
      return;
    }

    // Check if clicked near an AMR
    let clickedRobotId: string | null = null;
    for (const r of Object.values(robots)) {
      const { rx, ry } = getInterpolatedRobotCoord(r);
      const screenRx = curPan.x + (rx + 0.5) * curZoom;
      const screenRy = curPan.y + (ry + 0.5) * curZoom;
      const dist = Math.hypot(mouseX - screenRx, mouseY - screenRy);

      if (dist < curZoom * 0.55) {
        clickedRobotId = r.id;
        break;
      }
    }

    setStore({ selectedRobotId: clickedRobotId });
  };

  // Decoupled HiDPI 60fps render loop reading from refs
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;

    let animationFrameId: number;

    const render = () => {
      try {
        const {
          layout: curLayout,
          robots: curRobots,
          alerts: curAlerts,
          selectedRobotId: curSelectedId,
          activeOverlays: curOverlays,
          selectedCellsToBlock: curBlockedCells,
          activeFaults: curFaults,
          theme: curTheme,
        } = renderStateRef.current;

        const cssW = canvas.clientWidth;
        const cssH = canvas.clientHeight;
        if (cssW <= 0 || cssH <= 0 || !curLayout) {
          animationFrameId = requestAnimationFrame(render);
          return;
        }

        const dpr = window.devicePixelRatio || 1;
        const targetW = Math.round(cssW * dpr);
        const targetH = Math.round(cssH * dpr);
        if (canvas.width !== targetW || canvas.height !== targetH) {
          canvas.width = targetW;
          canvas.height = targetH;
        }

        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        const isLight = curTheme === "light";
        const curPan = panRef.current;
        const curZoom = zoomRef.current;

        // Warm studio porcelain / espresso backdrop
        ctx.fillStyle = isLight ? "#FAF5F0" : "#140F0D";
        ctx.fillRect(0, 0, cssW, cssH);

        ctx.save();
        ctx.translate(curPan.x, curPan.y);

        // 1. Draw Grid Cells Base
        ctx.strokeStyle = isLight ? "rgba(72, 46, 32, 0.10)" : "rgba(255, 236, 224, 0.08)";
        ctx.lineWidth = 1;

        for (let y = 0; y < curLayout.height; y++) {
          for (let x = 0; x < curLayout.width; x++) {
            const px = x * curZoom;
            const py = y * curZoom;

            ctx.fillStyle = isLight ? "#FFFBF8" : "#1C1512";
            ctx.fillRect(px, py, curZoom, curZoom);
            ctx.strokeRect(px, py, curZoom, curZoom);
          }
        }

        // 2. Draw Layout Cells
        const cellsList = Array.isArray((curLayout as any).cells) ? (curLayout as any).cells : [];

        cellsList.forEach((cell: any) => {
          const p = getPos(cell);
          const px = p.x * curZoom;
          const py = p.y * curZoom;
          const pad = Math.max(2, curZoom * 0.12);
          const ctype = cell.cell_type;

          // Thermal Zones
          if (curOverlays.showZones && (cell.zone === "CHILLED" || cell.zone === "FROZEN")) {
            ctx.fillStyle =
              cell.zone === "CHILLED"
                ? isLight
                  ? "rgba(37, 99, 235, 0.08)"
                  : "rgba(59, 130, 246, 0.12)"
                : isLight
                  ? "rgba(8, 145, 178, 0.10)"
                  : "rgba(6, 182, 212, 0.14)";
            ctx.fillRect(px, py, curZoom, curZoom);
          }

          if (ctype === "SHELF") {
            let rackFill = isLight ? "#E8DDD3" : "#2A201B";
            let rackBorder = isLight ? "#B8A596" : "#524036";
            if (cell.zone === "CHILLED") {
              rackFill = isLight ? "#DBEAFE" : "#172554";
              rackBorder = isLight ? "#3B82F6" : "#60A5FA";
            } else if (cell.zone === "FROZEN") {
              rackFill = isLight ? "#CFFAFE" : "#164E63";
              rackBorder = isLight ? "#0891B2" : "#22D3EE";
            }

            ctx.fillStyle = rackFill;
            ctx.strokeStyle = rackBorder;
            ctx.lineWidth = 1.2;
            ctx.fillRect(px + pad, py + pad, curZoom - 2 * pad, curZoom - 2 * pad);
            ctx.strokeRect(px + pad, py + pad, curZoom - 2 * pad, curZoom - 2 * pad);

            // Crossbeam
            ctx.beginPath();
            ctx.moveTo(px + pad, py + curZoom / 2);
            ctx.lineTo(px + curZoom - pad, py + curZoom / 2);
            ctx.stroke();
          } else if (ctype === "WALL") {
            ctx.fillStyle = isLight ? "#CBB8A9" : "#241B16";
            ctx.strokeStyle = isLight ? "#9C8677" : "#4A3A31";
            ctx.lineWidth = 1.5;
            ctx.fillRect(px, py, curZoom, curZoom);
            ctx.strokeRect(px, py, curZoom, curZoom);
          } else if (ctype === "DISPATCH") {
            ctx.fillStyle = isLight ? "rgba(217, 83, 59, 0.14)" : "rgba(232, 116, 84, 0.18)";
            ctx.strokeStyle = isLight ? "#C2412A" : "#E87454";
            ctx.lineWidth = 1.2;
            ctx.fillRect(px + pad, py + pad, curZoom - 2 * pad, curZoom - 2 * pad);
            ctx.strokeRect(px + pad, py + pad, curZoom - 2 * pad, curZoom - 2 * pad);
            if (curZoom >= 22) {
              drawContrastBadge(
                ctx,
                "BAY",
                px + curZoom / 2,
                py + curZoom / 2,
                Math.max(7, curZoom * 0.22),
                isLight ? "rgba(255, 251, 248, 0.92)" : "rgba(20, 15, 13, 0.88)",
                isLight ? "#8C2D19" : "#FFD6C9",
                isLight ? "rgba(194, 65, 42, 0.35)" : "rgba(232, 116, 84, 0.4)"
              );
            }
          } else if (ctype === "SUPERVISOR_DESK") {
            ctx.fillStyle = isLight ? "rgba(180, 105, 30, 0.15)" : "rgba(217, 146, 62, 0.18)";
            ctx.strokeStyle = isLight ? "#B4691E" : "#E5A952";
            ctx.lineWidth = 1.4;
            ctx.fillRect(px + pad, py + pad, curZoom - 2 * pad, curZoom - 2 * pad);
            ctx.strokeRect(px + pad, py + pad, curZoom - 2 * pad, curZoom - 2 * pad);
            if (curZoom >= 22) {
              drawContrastBadge(
                ctx,
                "DESK",
                px + curZoom / 2,
                py + curZoom / 2,
                Math.max(7, curZoom * 0.2),
                isLight ? "rgba(255, 251, 248, 0.92)" : "rgba(20, 15, 13, 0.88)",
                isLight ? "#7A430D" : "#FDE68A",
                isLight ? "rgba(180, 105, 30, 0.35)" : "rgba(229, 169, 82, 0.4)"
              );
            }
          } else if (ctype === "PARKING") {
            ctx.fillStyle = isLight ? "rgba(117, 98, 87, 0.09)" : "rgba(211, 195, 184, 0.08)";
            ctx.strokeStyle = isLight ? "rgba(117, 98, 87, 0.35)" : "rgba(211, 195, 184, 0.28)";
            ctx.lineWidth = 1;
            ctx.fillRect(px + pad, py + pad, curZoom - 2 * pad, curZoom - 2 * pad);
            ctx.strokeRect(px + pad, py + pad, curZoom - 2 * pad, curZoom - 2 * pad);
            if (curZoom >= 20) {
              drawContrastBadge(
                ctx,
                "P",
                px + curZoom / 2,
                py + curZoom / 2,
                Math.max(7, curZoom * 0.22),
                isLight ? "rgba(255, 251, 248, 0.90)" : "rgba(20, 15, 13, 0.84)",
                isLight ? "#4A3A31" : "#E6D8CC"
              );
            }
          }
        });

        // 3. Draw Dedicated Chargers
        const chargersList = Array.isArray((curLayout as any).chargers) ? (curLayout as any).chargers : [];
        chargersList.forEach((ch: any) => {
          const p = getPos(ch);
          const px = p.x * curZoom;
          const py = p.y * curZoom;
          const pad = Math.max(2, curZoom * 0.15);

          ctx.fillStyle = isLight ? "rgba(180, 105, 30, 0.14)" : "rgba(229, 169, 82, 0.16)";
          ctx.strokeStyle = isLight ? "#B4691E" : "#E5A952";
          ctx.lineWidth = 1.4;
          ctx.fillRect(px + pad, py + pad, curZoom - 2 * pad, curZoom - 2 * pad);
          ctx.strokeRect(px + pad, py + pad, curZoom - 2 * pad, curZoom - 2 * pad);

          const mx = px + curZoom / 2;
          const my = py + curZoom / 2;
          const s = Math.max(4, curZoom * 0.22);
          ctx.fillStyle = isLight ? "#B4691E" : "#F5B95E";
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
        const stationsList = Array.isArray((curLayout as any).stations)
          ? (curLayout as any).stations
          : Array.isArray((curLayout as any).pick_stations)
          ? (curLayout as any).pick_stations
          : [];

        stationsList.forEach((st: any) => {
          const p = getPos(st);
          const px = p.x * curZoom;
          const py = p.y * curZoom;
          const pad = Math.max(2, curZoom * 0.1);

          ctx.fillStyle = isLight ? "rgba(46, 125, 91, 0.14)" : "rgba(52, 211, 153, 0.16)";
          ctx.strokeStyle = isLight ? "#2E7D5B" : "#34D399";
          ctx.lineWidth = 1.5;
          ctx.fillRect(px + pad, py + pad, curZoom - 2 * pad, curZoom - 2 * pad);
          ctx.strokeRect(px + pad, py + pad, curZoom - 2 * pad, curZoom - 2 * pad);

          const label = st.station_id ? st.station_id.replace("ST-", "S") : "PICK";
          if (curZoom >= 18) {
            drawContrastBadge(
              ctx,
              label,
              px + curZoom / 2,
              py + curZoom / 2,
              Math.max(7.5, curZoom * 0.24),
              isLight ? "rgba(255, 251, 248, 0.92)" : "rgba(20, 15, 13, 0.88)",
              isLight ? "#176441" : "#6EE7B7",
              isLight ? "rgba(46, 125, 91, 0.35)" : "rgba(52, 211, 153, 0.4)"
            );
          }
        });

        // 5. Draw Blocked Cells
        const allBlockedCells: { x: number; y: number }[] = [...curBlockedCells];
        cellsList.forEach((c: any) => {
          if (c.blocked) {
            const p = getPos(c);
            if (!allBlockedCells.some((b) => b.x === p.x && b.y === p.y)) {
              allBlockedCells.push(p);
            }
          }
        });
        curFaults.forEach((f) => {
          if (f.target_id.startsWith("cell:")) {
            const parts = f.target_id.replace("cell:", "").split(",");
            if (parts.length === 2) {
              const cx = Number(parts[0]);
              const cy = Number(parts[1]);
              if (!allBlockedCells.some((b) => b.x === cx && b.y === cy)) {
                allBlockedCells.push({ x: cx, y: cy });
              }
            }
          }
        });

        allBlockedCells.forEach((c) => {
          const px = c.x * curZoom;
          const py = c.y * curZoom;

          ctx.fillStyle = "rgba(185, 56, 41, 0.32)";
          ctx.fillRect(px, py, curZoom, curZoom);
          ctx.strokeStyle = isLight ? "#B93829" : "#F87171";
          ctx.lineWidth = 1.6;
          ctx.strokeRect(px, py, curZoom, curZoom);

          ctx.beginPath();
          ctx.moveTo(px, py);
          ctx.lineTo(px + curZoom, py + curZoom);
          ctx.moveTo(px + curZoom, py);
          ctx.lineTo(px, py + curZoom);
          ctx.stroke();
        });

        // 6. Draw Directional Flow Arrows
        if (curOverlays.showFlowArrows) {
          ctx.strokeStyle = isLight ? "rgba(88, 71, 61, 0.28)" : "rgba(211, 195, 184, 0.24)";
          ctx.lineWidth = 1.2;

          cellsList.forEach((cell: any) => {
            const flow = cell.flow || cell.aisle_dir;
            if (flow && flow !== "BOTH" && cell.cell_type === "FLOOR") {
              const p = getPos(cell);
              const cx = (p.x + 0.5) * curZoom;
              const cy = (p.y + 0.5) * curZoom;
              const arrowSize = curZoom * 0.18;

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

        // 7. Draw Trajectory Line for Selected AMR (warm terracotta)
        if (curSelectedId && curRobots[curSelectedId]) {
          const sr = curRobots[curSelectedId];
          const { rx, ry } = getInterpolatedRobotCoord(sr);
          const scx = (rx + 0.5) * curZoom;
          const scy = (ry + 0.5) * curZoom;

          if (sr.motion?.to_coord) {
            const tcx = (sr.motion.to_coord.x + 0.5) * curZoom;
            const tcy = (sr.motion.to_coord.y + 0.5) * curZoom;

            ctx.save();
            ctx.setLineDash([4, 4]);
            ctx.strokeStyle = isLight ? "#D9533B" : "#E87454";
            ctx.lineWidth = 1.8;
            ctx.beginPath();
            ctx.moveTo(scx, scy);
            ctx.lineTo(tcx, tcy);
            ctx.stroke();
            ctx.restore();
          }
        }

        // 8. Draw AMRs (Robots) with Sub-Tick Interpolation & Warm Studio Precision
        const curHoveredId = hoveredRobotIdRef.current;
        const robotList = Object.values(curRobots);
        robotList.forEach((r: Robot) => {
          const { rx, ry } = getInterpolatedRobotCoord(r);
          const cx = (rx + 0.5) * curZoom;
          const cy = (ry + 0.5) * curZoom;
          const radius = Math.max(6.5, curZoom * 0.38);

          const isSelected = curSelectedId === r.id;
          const isHovered = curHoveredId === r.id;

          let amrBorder = isLight ? "#2E7D5B" : "#34D399";
          if (r.state === "CHARGING") {
            amrBorder = isLight ? "#B4691E" : "#F59E0B";
          } else if (r.state === "FAULTED" || r.state === "EMERGENCY_STOPPED") {
            amrBorder = isLight ? "#B93829" : "#F87171";
          } else if (String(r.state).includes("PICK") || String(r.state).includes("DROP") || r.current_task_id) {
            amrBorder = isLight ? "#D9533B" : "#E87454";
          }

          // Crisp selection reticle (no neon glow)
          if (isSelected) {
            ctx.beginPath();
            ctx.arc(cx, cy, radius + 5, 0, 2 * Math.PI);
            ctx.strokeStyle = isLight ? "#241B16" : "#FAF3EE";
            ctx.lineWidth = 2.4;
            ctx.stroke();

            ctx.beginPath();
            ctx.arc(cx, cy, radius + 3.2, 0, 2 * Math.PI);
            ctx.strokeStyle = isLight ? "#D9533B" : "#E87454";
            ctx.lineWidth = 1.6;
            ctx.stroke();
          }

          // Hover highlight
          if (isHovered && !isSelected) {
            ctx.beginPath();
            ctx.arc(cx, cy, radius + 3, 0, 2 * Math.PI);
            ctx.strokeStyle = isLight ? "rgba(36, 27, 22, 0.45)" : "rgba(250, 243, 238, 0.55)";
            ctx.lineWidth = 1.5;
            ctx.stroke();
          }

          // AMR Outer Chassis
          ctx.beginPath();
          ctx.arc(cx, cy, radius, 0, 2 * Math.PI);
          ctx.fillStyle = isLight ? "#241B16" : "#2E231D";
          ctx.fill();
          ctx.strokeStyle = amrBorder;
          ctx.lineWidth = 2;
          ctx.stroke();

          // Circular Battery Percentage Gauge Arc
          const batteryPct = Math.max(0, Math.min(100, r.battery_percent ?? 100));
          const batteryAngle = (batteryPct / 100) * 2 * Math.PI;
          ctx.beginPath();
          ctx.arc(cx, cy, Math.max(3, radius - 3.2), -Math.PI / 2, -Math.PI / 2 + batteryAngle);
          ctx.strokeStyle =
            batteryPct > 50
              ? isLight
                ? "#34D399"
                : "#34D399"
              : batteryPct > 20
                ? "#F59E0B"
                : "#F87171";
          ctx.lineWidth = 1.8;
          ctx.stroke();

          // Heading Indicator
          const headingRad = ((r.heading_deg ?? 0) * Math.PI) / 180;
          const hLen = radius * 0.78;
          const hx = cx + Math.cos(headingRad) * hLen;
          const hy = cy + Math.sin(headingRad) * hLen;

          ctx.beginPath();
          ctx.moveTo(cx, cy);
          ctx.lineTo(hx, hy);
          ctx.strokeStyle = "#FAF3EE";
          ctx.lineWidth = 1.8;
          ctx.stroke();

          // Carrying Tote indicator (warm terracotta-amber)
          if (r.current_task_id) {
            const bx = cx + radius * 0.55;
            const by = cy - radius * 0.55;
            ctx.fillStyle = "#E87454";
            ctx.fillRect(bx - 3.5, by - 3.5, 7, 7);
            ctx.strokeStyle = "#FFFBF8";
            ctx.lineWidth = 1;
            ctx.strokeRect(bx - 3.5, by - 3.5, 7, 7);
          }

          // AMR Short ID with readable contrast badge in both .light and .dark
          if (curZoom >= 18 || isSelected) {
            const shortId = r.id.replace("ROBOT-", "R-");
            drawContrastBadge(
              ctx,
              shortId,
              cx,
              cy - radius - 8,
              Math.max(8.5, Math.min(11, curZoom * 0.25)),
              isLight ? "rgba(255, 251, 248, 0.92)" : "rgba(20, 15, 13, 0.88)",
              isLight ? "#241B16" : "#FAF3EE",
              isLight ? "rgba(72, 46, 32, 0.20)" : "rgba(255, 236, 224, 0.18)"
            );
          }
        });

        // 9. Draw Active Alerts on Map (crisp geometric marker, zero shadowBlur)
        curAlerts.forEach((alert) => {
          if (alert.coord && !alert.cleared) {
            const ax = (alert.coord.x + 0.5) * curZoom;
            const ay = (alert.coord.y + 0.5) * curZoom;
            const s = Math.max(5, curZoom * 0.3);
            const isCrit = alert.severity === "CRITICAL";

            ctx.beginPath();
            ctx.arc(ax, ay, s + 4, 0, 2 * Math.PI);
            ctx.fillStyle = isCrit ? "rgba(185, 56, 41, 0.24)" : "rgba(180, 105, 30, 0.24)";
            ctx.fill();
            ctx.strokeStyle = isCrit ? "#B93829" : "#B4691E";
            ctx.lineWidth = 1.2;
            ctx.stroke();

            // Triangle
            ctx.beginPath();
            ctx.moveTo(ax, ay - s);
            ctx.lineTo(ax + s, ay + s);
            ctx.lineTo(ax - s, ay + s);
            ctx.closePath();
            ctx.fillStyle = isCrit ? "#B93829" : "#D97706";
            ctx.fill();

            // Exclamation mark
            ctx.fillStyle = "#FFFBF8";
            ctx.fillRect(ax - 0.75, ay - s * 0.35, 1.5, s * 0.6);
            ctx.fillRect(ax - 0.75, ay + s * 0.55, 1.5, 1.5);
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
  }, []);

  const zoomPercent = Math.round((zoom / 32) * 100);
  const initialTooltipTransform = computeTooltipTransform(
    mousePosRef.current.x,
    mousePosRef.current.y
  );

  return (
    <div
      ref={containerRef}
      className={`relative flex-1 h-full w-full overflow-hidden select-none ${
        isDragging ? "cursor-grabbing" : "cursor-grab"
      }`}
      style={{ backgroundColor: theme === "light" ? "#FAF5F0" : "#140F0D" }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
      onClick={handleClick}
    >
      <canvas ref={canvasRef} className="w-full h-full block" />

      {/* Compact Studio Legend Pill (hidden in compact Overview embed) */}
      {!compact && (
        <div
          className="hidden sm:flex absolute top-3 left-3 z-20 studio-card rounded-full px-3 py-1 items-center gap-3 text-[10.5px] font-medium select-none"
          onMouseDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
        >
          <span className="inline-flex items-center gap-1.5 text-[var(--studio-text-secondary)]">
            <span className="w-2 h-2 rounded-full bg-[#2E7D5B] dark:bg-emerald-400" />
            <span>Ready</span>
          </span>
          <span className="inline-flex items-center gap-1.5 text-[var(--studio-text-secondary)]">
            <span className="w-2 h-2 rounded-full bg-[#D9533B] dark:bg-[#E87454]" />
            <span>Task</span>
          </span>
          <span className="inline-flex items-center gap-1.5 text-[var(--studio-text-secondary)]">
            <span className="w-2 h-2 rounded-full bg-[#B4691E] dark:bg-amber-400" />
            <span>Charge</span>
          </span>
          <span className="inline-flex items-center gap-1.5 text-[var(--studio-text-secondary)]">
            <span className="w-2 h-2 rounded-full bg-[#B93829] dark:bg-red-400" />
            <span>Fault</span>
          </span>
          <span className="inline-flex items-center gap-1.5 text-[var(--studio-text-secondary)]">
            <span className="w-2 h-2 rounded-[3px] border border-[#2E7D5B] dark:border-emerald-400 bg-[#2E7D5B]/25" />
            <span>Pick</span>
          </span>
        </div>
      )}

      {/* Floating AMR Hover Tooltip (Compositor translate3d) */}
      {hoveredRobot && (
        <div
          ref={tooltipRef}
          className="absolute left-0 top-0 pointer-events-none z-30 studio-card px-3 py-2 rounded-xl text-[11px] backdrop-blur-xl will-change-transform"
          style={{
            background: "var(--studio-surface-elevated)",
            borderColor: "var(--studio-border-strong)",
            transform: initialTooltipTransform,
          }}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono font-semibold text-[#B83B24] dark:text-[#E87454] tabular-nums">
              {hoveredRobot.id}
            </span>
            <span
              className="text-[9.5px] px-1.5 py-0.5 rounded-full font-medium border"
              style={{
                background: "var(--studio-surface-subtle)",
                borderColor: "var(--studio-border)",
                color: "var(--studio-text-secondary)",
              }}
            >
              {hoveredRobot.state}
            </span>
          </div>
          <div className="flex items-center gap-2.5 text-[10.5px] mt-1 font-mono tabular-nums text-[var(--studio-text-secondary)]">
            <span className="inline-flex items-center gap-1">
              <Zap className="w-3 h-3 text-[#85470D] dark:text-amber-300" strokeWidth={1.5} />
              {Math.round(hoveredRobot.battery_percent ?? 100)}%
            </span>
            <span className="inline-flex items-center gap-1">
              <MapPin className="w-3 h-3 text-[var(--studio-text-muted)]" strokeWidth={1.5} />
              ({hoveredRobot.coord?.x ?? 0}, {hoveredRobot.coord?.y ?? 0})
            </span>
            {hoveredRobot.current_task_id && (
              <span className="inline-flex items-center gap-1 text-[#B83B24] dark:text-[#E87454] font-medium font-sans">
                <Package className="w-3 h-3" strokeWidth={1.5} />
                <span>Tote</span>
              </span>
            )}
          </div>
        </div>
      )}

      {/* Translucent Studio Floating HUD Controls (hidden in compact Overview embed) */}
      {!compact && (
        <div
          className="absolute bottom-3 left-3 z-20 studio-card studio-enter rounded-2xl p-1.5 flex items-center gap-1.5 text-xs max-w-[calc(100%-1.5rem)]"
          onMouseDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Zoom Controls */}
          <div
            className="flex items-center gap-0.5 rounded-[10px] p-0.5 border"
            style={{
              background: "var(--studio-surface-subtle)",
              borderColor: "var(--studio-border)",
            }}
          >
            <button
              type="button"
              onClick={() => zoomByFactor(1.25)}
              className="studio-btn p-1.5 rounded-lg text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-elevated)] cursor-pointer"
              title="Zoom in (+)"
              aria-label="Zoom in"
            >
              <ZoomIn className="w-3.5 h-3.5" strokeWidth={1.5} />
            </button>
            <span className="px-1.5 font-mono text-[10.5px] font-medium tabular-nums text-[var(--studio-text-secondary)] min-w-[38px] text-center">
              {zoomPercent}%
            </span>
            <button
              type="button"
              onClick={() => zoomByFactor(0.8)}
              className="studio-btn p-1.5 rounded-lg text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-elevated)] cursor-pointer"
              title="Zoom out (-)"
              aria-label="Zoom out"
            >
              <ZoomOut className="w-3.5 h-3.5" strokeWidth={1.5} />
            </button>
            <button
              type="button"
              onClick={fitToScreen}
              className="studio-btn p-1.5 rounded-lg text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-elevated)] cursor-pointer"
              title="Fit warehouse to screen"
              aria-label="Fit warehouse to screen"
            >
              <Maximize2 className="w-3.5 h-3.5" strokeWidth={1.5} />
            </button>
            <button
              type="button"
              onClick={() => {
                zoomRef.current = 32;
                panRef.current = { x: 40, y: 40 };
                setZoom(32);
              }}
              className="studio-btn p-1.5 rounded-lg text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-elevated)] cursor-pointer"
              title="Reset pan & zoom"
              aria-label="Reset pan and zoom"
            >
              <RotateCcw className="w-3.5 h-3.5" strokeWidth={1.5} />
            </button>
          </div>

          <div className="hidden sm:block h-4 w-px bg-[var(--studio-border-strong)]" />

          {/* Camera Preset Quick Pills */}
          <div className="hidden sm:flex items-center gap-1 text-[11px] font-medium">
            <button
              type="button"
              onClick={() => focusPreset("stations")}
              className="studio-btn px-2.5 py-1 rounded-[10px] border border-[var(--studio-border)] bg-[var(--studio-surface-subtle)] text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-elevated)] cursor-pointer"
              title="Center view on picking stations"
              aria-label="Center view on picking stations"
            >
              Stations
            </button>
            <button
              type="button"
              onClick={() => focusPreset("chargers")}
              className="studio-btn px-2.5 py-1 rounded-[10px] border border-[var(--studio-border)] bg-[var(--studio-surface-subtle)] text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-elevated)] cursor-pointer"
              title="Center view on charger bank"
              aria-label="Center view on charger bank"
            >
              Chargers
            </button>
          </div>

          <div className="h-4 w-px bg-[var(--studio-border-strong)]" />

          {/* Overlays */}
          <div className="flex items-center gap-1">
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
              aria-label="Toggle aisle flow arrows"
              aria-pressed={activeOverlays.showFlowArrows}
              className={`studio-btn p-1.5 rounded-[10px] border cursor-pointer ${
                activeOverlays.showFlowArrows
                  ? "bg-[#D9533B] text-[#FFFBF8] border-[#D9533B] shadow-sm"
                  : "border-transparent text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-subtle)]"
              }`}
              title="Toggle aisle flow arrows"
            >
              <Eye className="w-3.5 h-3.5" strokeWidth={1.5} />
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
              aria-label="Toggle temperature zones"
              aria-pressed={activeOverlays.showZones}
              className={`studio-btn p-1.5 rounded-[10px] border cursor-pointer ${
                activeOverlays.showZones
                  ? "bg-[#D9533B] text-[#FFFBF8] border-[#D9533B] shadow-sm"
                  : "border-transparent text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-subtle)]"
              }`}
              title="Toggle temperature zones"
            >
              <Layers className="w-3.5 h-3.5" strokeWidth={1.5} />
            </button>
          </div>

          <div className="h-4 w-px bg-[var(--studio-border-strong)]" />

          {/* Block Tool */}
          <button
            type="button"
            onClick={() =>
              setStore({
                blockModeActive: !blockModeActive,
                selectedCellsToBlock: [],
              })
            }
            aria-label="Toggle block cell tool"
            aria-pressed={blockModeActive}
            className={`studio-btn flex items-center gap-1.5 px-2.5 py-1 rounded-[10px] border text-[11px] font-medium cursor-pointer ${
              blockModeActive
                ? "bg-[#D9533B] text-[#FFFBF8] border-[#D9533B] font-semibold shadow-sm"
                : "border-[var(--studio-border)] bg-[var(--studio-surface-subtle)] text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-elevated)]"
            }`}
            title="Toggle block cell tool (Click grid cells to block)"
          >
            <ShieldAlert className="w-3.5 h-3.5" strokeWidth={1.5} />
            <span>Block</span>
          </button>
        </div>
      )}

      {/* Block Tool Action Bar (Outer centering decoupled from .studio-enter transform) */}
      {!compact && blockModeActive && (
        <div
          className="absolute top-3 left-1/2 -translate-x-1/2 z-20 max-w-[calc(100%-1.5rem)]"
          onMouseDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
        >
          <div
            className="studio-card studio-enter rounded-2xl px-3.5 py-2 flex items-center gap-3 text-xs"
            style={{
              background: "var(--studio-surface-elevated)",
              borderColor: "rgba(185, 56, 41, 0.45)",
            }}
          >
            <ShieldAlert className="w-4 h-4 text-[#B83B24] dark:text-[#E87454] shrink-0" strokeWidth={1.5} />
            <span className="text-[var(--studio-text-primary)] whitespace-nowrap">
              Click cells on grid.{" "}
              <strong className="font-mono tabular-nums text-[#B83B24] dark:text-[#E87454]">
                {selectedCellsToBlock.length}
              </strong>{" "}
              selected.
            </span>
            <button
              type="button"
              onClick={() => setStore({ isEStopModalOpen: true })}
              disabled={selectedCellsToBlock.length === 0}
              aria-label="Block selected cells"
              className="studio-btn px-2.5 py-1 bg-[#B93829] hover:bg-[#9F2E21] disabled:opacity-40 text-[#FFFBF8] font-semibold rounded-lg cursor-pointer whitespace-nowrap"
            >
              Block selected
            </button>
            <button
              type="button"
              onClick={() => setStore({ blockModeActive: false, selectedCellsToBlock: [] })}
              aria-label="Cancel block cell mode"
              className="studio-btn px-2 py-1 rounded-lg text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-subtle)] cursor-pointer"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
