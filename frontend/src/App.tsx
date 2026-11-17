import React, { useEffect } from "react";
import { TopBar } from "./components/TopBar";
import { CanvasMap } from "./components/CanvasMap";
import { OrderBoard } from "./components/OrderBoard";
import { AlertDrawer } from "./components/AlertDrawer";
import { EventFeed } from "./components/EventFeed";
import { SelectedRobotPanel } from "./components/SelectedRobotPanel";
import { EnvironmentModal } from "./components/EnvironmentModal";
import { ControlModals } from "./components/ControlModals";
import { pauseSimulation, resumeSimulation, setSimulationSpeed } from "./services/api";
import { setStore, useStore, useWebSocketConnection } from "./store/useStore";

export const App: React.FC = () => {
  // Establish persistent WebSocket connection & reactive state
  useWebSocketConnection();
  const { isPaused, leftPanelOpen, rightPanelOpen, activeRightTab, alerts } = useStore();

  const activeAlertCount = alerts.filter((a) => !a.cleared).length;

  // Global Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = async (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
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
      } else if (e.code === "BracketLeft") {
        setStore({ leftPanelOpen: !leftPanelOpen });
      } else if (e.code === "BracketRight") {
        setStore({ rightPanelOpen: !rightPanelOpen });
      } else if (e.key === "Escape") {
        setStore({
          isEnvironmentModalOpen: false,
          isEStopModalOpen: false,
          selectedRobotId: null,
          selectedOrderId: null,
          blockModeActive: false,
        });
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isPaused, leftPanelOpen, rightPanelOpen]);

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-gray-950 text-gray-100 font-sans select-none">
      {/* Top Bar with KPIs & Controls */}
      <TopBar />

      {/* Main Operations Canvas Area */}
      <div className="flex flex-1 overflow-hidden relative min-h-0">
        {/* Left Side: Order Board (Collapsible) */}
        {leftPanelOpen && (
          <aside className="w-72 max-w-[288px] flex-shrink-0 h-full border-r border-gray-800 bg-gray-900/95 flex flex-col z-20 overflow-hidden">
            <OrderBoard />
          </aside>
        )}

        {/* Center: 2D Live Operations Canvas */}
        <main className="flex-1 min-w-0 h-full relative overflow-hidden bg-gray-950">
          <CanvasMap />
          <SelectedRobotPanel />
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
    </div>
  );
};

export default App;
