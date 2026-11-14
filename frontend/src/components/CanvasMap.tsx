import React, { useEffect, useRef, useState, useCallback } from "react";
import { Eye, Layers, Maximize2, ShieldAlert, ZoomIn, ZoomOut } from "lucide-react";
import type { Coordinate, Layout, Robot } from "../types/generated";
import { setStore, useStore } from "../store/useStore";

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

  const layout: Layout | undefined = staticWorld?.layout;

  // Fit to screen callback
  const fitToScreen = useCallback(() => {
    if (!layout || !containerRef.current) return;
    const { clientWidth, clientHeight } = containerRef.current;
    const padding = 60;
    const availableWidth = clientWidth - padding;
    const availableHeight = clientHeight - padding;

    const cellWidth = availableWidth / layout.width;
    const cellHeight = availableHeight / layout.height;
    const newZoom = Math.max(12, Math.min(cellWidth, cellHeight, 64));

    const totalGridWidth = layout.width * newZoom;
    const totalGridHeight = layout.height * newZoom;

    setZoom(newZoom);
    setPan({
      x: (clientWidth - totalGridWidth) / 2,
      y: (clientHeight - totalGridHeight) / 2,
    });
  }, [layout]);

  // Initial fit
  useEffect(() => {
    if (layout) {
      fitToScreen();
    }
  }, [layout, fitToScreen]);

  // Handle Wheel Zoom
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
    const newZoom = Math.min(Math.max(zoom * zoomFactor, 12), 120);

    // Zoom toward mouse position
    const rect = canvasRef.current?.getBoundingClientRect();
    if (rect) {
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      const dx = mouseX - pan.x;
      const dy = mouseY - pan.y;

      setPan({
        x: mouseX - dx * (newZoom / zoom),
        y: mouseY - dy * (newZoom / zoom),
      });
      setZoom(newZoom);
    }
  };

  // Dragging Pan Handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return; // Only left click
    setIsDragging(true);
    dragStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPan({
        x: e.clientX - dragStartRef.current.x,
        y: e.clientY - dragStartRef.current.y,
      });
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
      // Toggle cell in selectedCellsToBlock
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
      const rx = r.motion ? r.motion.from_coord.x + (r.motion.to_coord.x - r.motion.from_coord.x) * r.motion.progress : r.coord.x;
      const ry = r.motion ? r.motion.from_coord.y + (r.motion.to_coord.y - r.motion.from_coord.y) * r.motion.progress : r.coord.y;

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

  // High-performance 60fps render loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !layout) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;

    const render = () => {
      // Resize canvas to client dimensions if needed
      if (canvas.width !== canvas.clientWidth || canvas.height !== canvas.clientHeight) {
        canvas.width = canvas.clientWidth;
        canvas.height = canvas.clientHeight;
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      ctx.save();
      ctx.translate(pan.x, pan.y);

      // 1. Draw Grid Background
      ctx.strokeStyle = "rgba(55, 65, 81, 0.35)";
      ctx.lineWidth = 1;

      // Draw floor cells
      for (let y = 0; y < layout.height; y++) {
        for (let x = 0; x < layout.width; x++) {
          const px = x * zoom;
          const py = y * zoom;

          // Default floor
          ctx.fillStyle = "#0F172A";
          ctx.fillRect(px, py, zoom, zoom);
          ctx.strokeRect(px, py, zoom, zoom);
        }
      }

      // 2. Temperature Zones Overlay
      if (activeOverlays.showZones) {
        for (let y = 0; y < layout.height; y++) {
          for (let x = 0; x < layout.width; x++) {
            const cell = layout.grid?.[y]?.[x];
            if (cell) {
              const px = x * zoom;
              const py = y * zoom;
              if (cell.zone === "CHILLED") {
                ctx.fillStyle = "rgba(59, 130, 246, 0.08)";
                ctx.fillRect(px, py, zoom, zoom);
              } else if (cell.zone === "FROZEN") {
                ctx.fillStyle = "rgba(6, 182, 212, 0.12)";
                ctx.fillRect(px, py, zoom, zoom);
              }
            }
          }
        }
      }

      // 3. Draw Shelves / Racks
      layout.shelves.forEach((shelf) => {
        const px = shelf.coord.x * zoom;
        const py = shelf.coord.y * zoom;
        const pad = Math.max(2, zoom * 0.12);

        // Rack color based on zone
        let rackColor = "#334155";
        let rackBorder = "#475569";
        if (shelf.zone === "CHILLED") {
          rackColor = "#1E3A8A";
          rackBorder = "#3B82F6";
        } else if (shelf.zone === "FROZEN") {
          rackColor = "#164E63";
          rackBorder = "#06B6D4";
        }

        ctx.fillStyle = rackColor;
        ctx.strokeStyle = rackBorder;
        ctx.lineWidth = 1.5;
        ctx.fillRect(px + pad, py + pad, zoom - 2 * pad, zoom - 2 * pad);
        ctx.strokeRect(px + pad, py + pad, zoom - 2 * pad, zoom - 2 * pad);

        // Rack crossbeams
        ctx.beginPath();
        ctx.moveTo(px + pad, py + zoom / 2);
        ctx.lineTo(px + zoom - pad, py + zoom / 2);
        ctx.stroke();
      });

      // 4. Draw Chargers
      layout.chargers.forEach((ch) => {
        const px = ch.coord.x * zoom;
        const py = ch.coord.y * zoom;
        const pad = Math.max(2, zoom * 0.15);

        ctx.fillStyle = "rgba(245, 158, 11, 0.15)";
        ctx.strokeStyle = "#F59E0B";
        ctx.lineWidth = 1.5;
        ctx.fillRect(px + pad, py + pad, zoom - 2 * pad, zoom - 2 * pad);
        ctx.strokeRect(px + pad, py + pad, zoom - 2 * pad, zoom - 2 * pad);

        // Bolt symbol
        ctx.fillStyle = "#F59E0B";
        ctx.font = `${Math.max(10, zoom * 0.45)}px sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText("⚡", px + zoom / 2, py + zoom / 2);
      });

      // 5. Draw Pick Stations
      layout.pick_stations.forEach((ps) => {
        const px = ps.coord.x * zoom;
        const py = ps.coord.y * zoom;
        const pad = Math.max(2, zoom * 0.1);

        ctx.fillStyle = "rgba(16, 185, 129, 0.2)";
        ctx.strokeStyle = "#10B981";
        ctx.lineWidth = 1.5;
        ctx.fillRect(px + pad, py + pad, zoom - 2 * pad, zoom - 2 * pad);
        ctx.strokeRect(px + pad, py + pad, zoom - 2 * pad, zoom - 2 * pad);

        ctx.fillStyle = "#10B981";
        ctx.font = `600 ${Math.max(8, zoom * 0.3)}px monospace`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText("PICK", px + zoom / 2, py + zoom / 2);
      });

      // 6. Draw Blocked Cells (from layout or active selection)
      if (layout.grid) {
        for (let y = 0; y < layout.height; y++) {
          for (let x = 0; x < layout.width; x++) {
            const cell = layout.grid[y]?.[x];
            const isSelectedToBlock = selectedCellsToBlock.some((c) => c.x === x && c.y === y);

            if (cell?.blocked || isSelectedToBlock) {
              const px = x * zoom;
              const py = y * zoom;

              ctx.fillStyle = isSelectedToBlock ? "rgba(239, 68, 68, 0.4)" : "rgba(239, 68, 68, 0.25)";
              ctx.fillRect(px, py, zoom, zoom);

              ctx.strokeStyle = "#EF4444";
              ctx.lineWidth = 1.5;
              ctx.strokeRect(px, py, zoom, zoom);

              // Diagonal cross-hatch
              ctx.beginPath();
              ctx.moveTo(px, py);
              ctx.lineTo(px + zoom, py + zoom);
              ctx.moveTo(px + zoom, py);
              ctx.lineTo(px, py + zoom);
              ctx.stroke();
            }
          }
        }
      }

      // 7. Draw Flow Arrows if enabled
      if (activeOverlays.showFlowArrows && layout.grid) {
        ctx.strokeStyle = "rgba(148, 163, 184, 0.25)";
        ctx.fillStyle = "rgba(148, 163, 184, 0.25)";
        ctx.lineWidth = 1.5;

        for (let y = 0; y < layout.height; y++) {
          for (let x = 0; x < layout.width; x++) {
            const cell = layout.grid[y]?.[x];
            if (cell && cell.cell_type === "WALKWAY" && cell.aisle_dir) {
              const cx = (x + 0.5) * zoom;
              const cy = (y + 0.5) * zoom;
              const arrowSize = zoom * 0.2;

              ctx.save();
              ctx.translate(cx, cy);

              let angle = 0;
              if (cell.aisle_dir === "EAST") angle = 0;
              else if (cell.aisle_dir === "SOUTH") angle = Math.PI / 2;
              else if (cell.aisle_dir === "WEST") angle = Math.PI;
              else if (cell.aisle_dir === "NORTH") angle = -Math.PI / 2;

              ctx.rotate(angle);
              ctx.beginPath();
              ctx.moveTo(-arrowSize, -arrowSize * 0.5);
              ctx.lineTo(arrowSize, 0);
              ctx.lineTo(-arrowSize, arrowSize * 0.5);
              ctx.stroke();
              ctx.restore();
            }
          }
        }
      }

      // 8. Draw AMRs (Robots) with Sub-Tick Progress Interpolation
      const robotList = Object.values(robots);
      robotList.forEach((r: Robot) => {
        // Interpolate position
        let rx = r.coord.x;
        let ry = r.coord.y;
        if (r.motion) {
          const from = r.motion.from_coord;
          const to = r.motion.to_coord;
          const prog = Math.max(0, Math.min(1, r.motion.progress));
          rx = from.x + (to.x - from.x) * prog;
          ry = from.y + (to.y - from.y) * prog;
        }

        const cx = pan.x + (rx + 0.5) * zoom - pan.x;
        const cy = pan.y + (ry + 0.5) * zoom - pan.y;
        const radius = zoom * 0.38;

        const isSelected = selectedRobotId === r.id;

        // Selection ring
        if (isSelected) {
          ctx.beginPath();
          ctx.arc(cx, cy, radius + 4, 0, 2 * Math.PI);
          ctx.strokeStyle = "#38BDF8";
          ctx.lineWidth = 2.5;
          ctx.stroke();
        }

        // AMR State base color
        let amrColor = "#10B981"; // IDLE/MOVING default green
        if (r.state === "CHARGING") amrColor = "#F59E0B";
        else if (r.state === "FAULTED" || r.state === "EMERGENCY_STOPPED") amrColor = "#EF4444";
        else if (r.state.startsWith("PICK") || r.state.startsWith("DROP")) amrColor = "#3B82F6";

        // AMR Body circle
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, 2 * Math.PI);
        ctx.fillStyle = "#1E293B";
        ctx.fill();
        ctx.strokeStyle = amrColor;
        ctx.lineWidth = 2;
        ctx.stroke();

        // Battery Ring Indicator
        const batteryPct = Math.max(0, Math.min(100, r.battery_percent));
        const batteryAngle = (batteryPct / 100) * 2 * Math.PI;
        ctx.beginPath();
        ctx.arc(cx, cy, radius - 3, -Math.PI / 2, -Math.PI / 2 + batteryAngle);
        ctx.strokeStyle = batteryPct > 50 ? "#10B981" : batteryPct > 20 ? "#F59E0B" : "#EF4444";
        ctx.lineWidth = 2;
        ctx.stroke();

        // Heading Arrow Indicator
        const headingRad = (r.heading_deg * Math.PI) / 180;
        const hLen = radius * 0.75;
        const hx = cx + Math.cos(headingRad) * hLen;
        const hy = cy + Math.sin(headingRad) * hLen;

        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(hx, hy);
        ctx.strokeStyle = "#FFFFFF";
        ctx.lineWidth = 2;
        ctx.stroke();

        // Robot ID Label if zoomed in enough or selected
        if (zoom >= 24 || isSelected) {
          ctx.fillStyle = "#F8FAFC";
          ctx.font = `600 ${Math.max(9, zoom * 0.28)}px monospace`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          const shortId = r.id.replace("ROBOT-", "R");
          ctx.fillText(shortId, cx, cy - radius - 5);
        }
      });

      // 9. Draw Active Alerts on Map
      alerts.forEach((alert) => {
        if (alert.coord && !alert.cleared) {
          const ax = (alert.coord.x + 0.5) * zoom;
          const ay = (alert.coord.y + 0.5) * zoom;

          ctx.beginPath();
          ctx.arc(ax, ay, zoom * 0.35, 0, 2 * Math.PI);
          ctx.fillStyle = alert.severity === "CRITICAL" ? "rgba(239, 68, 68, 0.4)" : "rgba(245, 158, 11, 0.4)";
          ctx.fill();

          ctx.strokeStyle = alert.severity === "CRITICAL" ? "#EF4444" : "#F59E0B";
          ctx.lineWidth = 2;
          ctx.stroke();

          ctx.fillStyle = "#FFFFFF";
          ctx.font = `${Math.max(10, zoom * 0.4)}px sans-serif`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText("⚠️", ax, ay);
        }
      });

      ctx.restore();

      animationFrameId = requestAnimationFrame(render);
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
    activeOverlays,
    blockModeActive,
    selectedCellsToBlock,
  ]);

  return (
    <div
      ref={containerRef}
      className="relative flex-1 h-full bg-gray-950 overflow-hidden select-none cursor-grab active:cursor-grabbing"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onWheel={handleWheel}
      onClick={handleClick}
    >
      <canvas ref={canvasRef} className="w-full h-full block" />

      {/* Floating Map Controls */}
      <div className="absolute bottom-4 left-4 flex items-center gap-1.5 bg-gray-900/90 border border-gray-800 backdrop-blur-md rounded-lg p-1 text-xs shadow-lg z-20">
        <button
          onClick={() => setZoom((z) => Math.min(z * 1.25, 120))}
          className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition"
          title="Zoom In"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          onClick={() => setZoom((z) => Math.max(z * 0.8, 12))}
          className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition"
          title="Zoom Out"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <button
          onClick={fitToScreen}
          className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition"
          title="Fit to Screen"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
        <div className="h-4 w-px bg-gray-800" />
        <button
          onClick={() =>
            setStore({
              activeOverlays: {
                ...activeOverlays,
                showFlowArrows: !activeOverlays.showFlowArrows,
              },
            })
          }
          className={`p-1.5 rounded transition ${
            activeOverlays.showFlowArrows ? "bg-blue-600/30 text-blue-400" : "text-gray-400 hover:text-white"
          }`}
          title="Toggle Aisle Flow Arrows"
        >
          <Eye className="w-4 h-4" />
        </button>
        <button
          onClick={() =>
            setStore({
              activeOverlays: {
                ...activeOverlays,
                showZones: !activeOverlays.showZones,
              },
            })
          }
          className={`p-1.5 rounded transition ${
            activeOverlays.showZones ? "bg-blue-600/30 text-blue-400" : "text-gray-400 hover:text-white"
          }`}
          title="Toggle Temperature Zones"
        >
          <Layers className="w-4 h-4" />
        </button>
        <button
          onClick={() =>
            setStore({
              blockModeActive: !blockModeActive,
              selectedCellsToBlock: [],
            })
          }
          className={`flex items-center gap-1 px-2 py-1 rounded transition text-xs font-medium ${
            blockModeActive ? "bg-red-600 text-white" : "text-gray-400 hover:text-white hover:bg-gray-800"
          }`}
          title="Toggle Block Cell Tool (Click cells to block)"
        >
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>Block Tool</span>
        </button>
      </div>

      {/* Block Tool Action Bar */}
      {blockModeActive && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-red-950/90 border border-red-800 backdrop-blur-md rounded-lg px-4 py-2 flex items-center gap-3 text-xs shadow-xl z-20">
          <ShieldAlert className="w-4 h-4 text-red-400" />
          <span className="text-red-200">
            Click cells to select. <strong>{selectedCellsToBlock.length}</strong> cells selected.
          </span>
          <button
            onClick={() => setStore({ isEStopModalOpen: true })}
            disabled={selectedCellsToBlock.length === 0}
            className="px-2.5 py-1 bg-red-600 hover:bg-red-500 disabled:opacity-40 text-white font-medium rounded transition"
          >
            Block Selected
          </button>
          <button
            onClick={() => setStore({ blockModeActive: false, selectedCellsToBlock: [] })}
            className="px-2 py-1 text-gray-400 hover:text-white transition"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
};
