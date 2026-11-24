import React, { useEffect, useRef, useState } from "react";
import { TopBar } from "./components/TopBar";
import { CanvasMap } from "./components/CanvasMap";
import { Scene3D } from "./components/Scene3D/Scene3D";
import { OrderBoard } from "./components/OrderBoard";
import { AlertDrawer } from "./components/AlertDrawer";
import { AlertBanner } from "./components/AlertBanner";
import { EventFeed } from "./components/EventFeed";
import { SelectedRobotPanel } from "./components/SelectedRobotPanel";
import { EnvironmentModal } from "./components/EnvironmentModal";
import { ControlModals } from "./components/ControlModals";
import { DecisionLogPanel } from "./components/Brain/DecisionLogPanel";
import { ApprovalsDrawer } from "./components/Brain/ApprovalsDrawer";
import { SupervisorCommandBar } from "./components/Brain/SupervisorCommandBar";
import { ChaosControlModal } from "./components/Chaos/ChaosControlModal";
import { ExceptionsQueueDrawer } from "./components/Chaos/ExceptionsQueueDrawer";
import { AuditLogViewerModal } from "./components/Chaos/AuditLogViewerModal";
import { ReplayTimeline } from "./components/ReplayTimeline";
import { pauseSimulation, resumeSimulation, setSimulationSpeed } from "./services/api";
import { setStore, useStore, useWebSocketConnection } from "./store/useStore";

const VIEW_MODES: Array<"2d" | "3d" | "split"> = ["2d", "3d", "split"];

export const App: React.FC = () => {
  // Establish persistent WebSocket connection & reactive state
  useWebSocketConnection();
  const store = useStore();
  const {
    isPaused,
    leftPanelOpen,
    rightPanelOpen,
    activeRightTab,
    alerts,
    viewMode,
    isSupervisorBarOpen,
  } = store;

  const activeAlertCount = alerts.filter((a) => !a.cleared).length;

  // Draggable Split Divider State
  const [splitRatio, setSplitRatio] = useState<number>(0.5);
  const [isDraggingSplit, setIsDraggingSplit] = useState<boolean>(false);
  const mainRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!isDraggingSplit) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!mainRef.current) return;
      const rect = mainRef.current.getBoundingClientRect();
      const relativeX = e.clientX - rect.left;
      const newRatio = Math.max(0.2, Math.min(0.8, relativeX / rect.width));
      setSplitRatio(newRatio);
    };

    const handleMouseUp = () => {
      setIsDraggingSplit(false);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDraggingSplit]);

  // Global Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = async (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setStore({ isSupervisorBarOpen: !isSupervisorBarOpen });
        return;
      }

      if (e.code === "Space") {
        e.preventDefault();
        const nextPaused = !isPaused;
        setStore({ isPaused: nextPaused });
        try {
          if (nextPaused) {
            await pauseSimulation();
          } else {
            await resumeSimulation();
          }
        } catch (err) {
          console.error(err);
        }
      } else if (e.code === "Digit1") {
        setStore({ speedMultiplier: 1.0 });
        await setSimulationSpeed(1.0);
      } else if (e.code === "Digit2") {
        setStore({ speedMultiplier: 2.0 });
        await setSimulationSpeed(2.0);
      } else if (e.code === "Digit5") {
        setStore({ speedMultiplier: 5.0 });
        await setSimulationSpeed(5.0);
      } else if (e.code === "KeyV") {
        e.preventDefault();
        const nextMode = VIEW_MODES[(VIEW_MODES.indexOf(viewMode) + 1) % VIEW_MODES.length];
        setStore({ viewMode: nextMode });
      } else if (e.code === "BracketLeft") {
        setStore({ leftPanelOpen: !leftPanelOpen });
      } else if (e.code === "BracketRight") {
        setStore({ rightPanelOpen: !rightPanelOpen });
      } else if (e.key === "Escape") {
        setStore({
          isEnvironmentModalOpen: false,
          isEStopModalOpen: false,
          isDecisionLogOpen: false,
          isApprovalsDrawerOpen: false,
          isSupervisorBarOpen: false,
          isChaosControlOpen: false,
          isExceptionsQueueOpen: false,
          isAuditLogOpen: false,
          selectedRobotId: null,
          selectedOrderId: null,
          blockModeActive: false,
        });
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isPaused, leftPanelOpen, rightPanelOpen, viewMode]);

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-gray-950 text-gray-100 font-sans select-none">
      {/* Top Bar with KPIs & Controls */}
      <TopBar />

      {/* Floating High-Priority Alert Banner */}
      <AlertBanner />

      {/* Main Operations Canvas Area */}
      <div className="flex flex-1 overflow-hidden relative min-h-0">
        {/* Left Side: Order Board (Collapsible) */}
        {leftPanelOpen && (
          <aside className="w-72 max-w-[288px] flex-shrink-0 h-full border-r border-gray-800 bg-gray-900/95 flex flex-col z-20 overflow-hidden">
            <OrderBoard />
          </aside>
        )}

        {/* Center: Live 2D / 3D / Split Digital Twin Canvas */}
        <main
          ref={mainRef}
          className="flex-1 min-w-0 h-full relative overflow-hidden bg-gray-950 flex"
        >
          {viewMode === "2d" && (
            <div className="w-full h-full relative">
              <CanvasMap />
            </div>
          )}

          {viewMode === "3d" && (
            <div className="w-full h-full relative">
              <Scene3D />
            </div>
          )}

          {viewMode === "split" && (
            <div className="flex w-full h-full relative overflow-hidden">
              <div
                style={{ width: `${splitRatio * 100}%` }}
                className="h-full relative overflow-hidden"
              >
                <CanvasMap />
              </div>

              {/* Draggable Divider */}
              <div
                onMouseDown={() => setIsDraggingSplit(true)}
                className={`w-1.5 h-full cursor-col-resize z-20 flex items-center justify-center transition-colors select-none ${
                  isDraggingSplit
                    ? "bg-cyan-500 shadow-md shadow-cyan-500/50"
                    : "bg-gray-800 hover:bg-cyan-600/70"
                }`}
                title="Drag to resize 2D/3D split view"
              >
                <div className="w-0.5 h-8 bg-gray-500/80 rounded-full" />
              </div>

              <div
                style={{ width: `${(1 - splitRatio) * 100}%` }}
                className="h-full relative overflow-hidden"
              >
                <Scene3D />
              </div>
            </div>
          )}

          {/* Persistent Selected AMR Detail Panel */}
          <SelectedRobotPanel />

          {/* Phase 7 Replay & Timeline Scrubber Dock */}
          <ReplayTimeline />
        </main>

        {/* Right Side: Tabbed Alerts & Event Feed (Collapsible) */}
        {rightPanelOpen && (
          <aside className="w-72 max-w-[288px] flex-shrink-0 h-full border-l border-gray-800 bg-gray-900/95 flex flex-col z-20 overflow-hidden">
            {/* Right Panel Tab Switcher */}
            <div className="px-3 pt-2.5 pb-2 border-b border-gray-800 bg-gray-950/70 flex items-center gap-1.5 shrink-0">
              <button
                type="button"
                onClick={() => setStore({ activeRightTab: "alerts" })}
                className={`flex-1 py-1.5 px-2 rounded-md font-medium text-xs flex items-center justify-center gap-1.5 transition cursor-pointer ${
                  activeRightTab === "alerts"
                    ? "bg-gray-800 text-white shadow-sm"
                    : "text-gray-400 hover:text-gray-200 hover:bg-gray-900"
                }`}
              >
                <span>Alerts</span>
                <span
                  className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${
                    activeAlertCount > 0
                      ? "bg-amber-950 text-amber-300 border border-amber-800/80 font-bold"
                      : "bg-gray-700 text-gray-400"
                  }`}
                >
                  {activeAlertCount}
                </span>
              </button>

              <button
                type="button"
                onClick={() => setStore({ activeRightTab: "events" })}
                className={`flex-1 py-1.5 px-2 rounded-md font-medium text-xs flex items-center justify-center gap-1.5 transition cursor-pointer ${
                  activeRightTab === "events"
                    ? "bg-gray-800 text-white shadow-sm"
                    : "text-gray-400 hover:text-gray-200 hover:bg-gray-900"
                }`}
              >
                <span>Event feed</span>
              </button>
            </div>

            {/* Tab Body */}
            <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
              {activeRightTab === "alerts" ? <AlertDrawer /> : <EventFeed />}
            </div>
          </aside>
        )}
      </div>

      {/* Modals & Dialogs */}
      <EnvironmentModal />
      <ControlModals />

      {/* AI Operations Brain Overlays (Phase 5) */}
      <DecisionLogPanel />
      <ApprovalsDrawer />
      <SupervisorCommandBar />

      {/* Chaos & Resilience Studio Overlays (Phase 6) */}
      <ChaosControlModal />
      <ExceptionsQueueDrawer />
      <AuditLogViewerModal />
    </div>
  );
};

export default App;
