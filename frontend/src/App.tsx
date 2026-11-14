import React, { useEffect } from "react";
import { TopBar } from "./components/TopBar";
import { CanvasMap } from "./components/CanvasMap";
import { OrderBoard } from "./components/OrderBoard";
import { AlertDrawer } from "./components/AlertDrawer";
import { EventFeed } from "./components/EventFeed";
import { SelectedRobotPanel } from "./components/SelectedRobotPanel";
import { EnvironmentModal } from "./components/EnvironmentModal";
import { ControlModals } from "./components/ControlModals";
import { defaultPanelRegistry } from "./panels/registry";
import { pauseSimulation, resumeSimulation, setSimulationSpeed } from "./services/api";
import { setStore, useStore, useWebSocketConnection } from "./store/useStore";

// Initialize CA-9 Panel Registry
defaultPanelRegistry.register({
  id: "order-board",
  title: "Order Board",
  position: "left",
  defaultOpen: true,
  order: 1,
  component: OrderBoard,
});

defaultPanelRegistry.register({
  id: "alert-drawer",
  title: "Alert Drawer",
  position: "right",
  defaultOpen: true,
  order: 1,
  component: AlertDrawer,
});

defaultPanelRegistry.register({
  id: "event-feed",
  title: "Event Feed",
  position: "right",
  defaultOpen: true,
  order: 2,
  component: EventFeed,
});

export const App: React.FC = () => {
  // Establish persistent WebSocket connection & reactive state
  useWebSocketConnection();
  const { isPaused } = useStore();

  // Keyboard shortcuts (P2-A13)
  useEffect(() => {
    const handleKeyDown = async (e: KeyboardEvent) => {
      // Ignore if user is typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      if (e.code === "Space") {
        e.preventDefault();
        try {
          if (isPaused) {
            await resumeSimulation();
            setStore({ isPaused: false });
          } else {
            await pauseSimulation();
            setStore({ isPaused: true });
          }
        } catch (err) {
          console.error(err);
        }
      } else if (e.code === "Digit1") {
        await setSimulationSpeed(1.0);
        setStore({ speedMultiplier: 1.0 });
      } else if (e.code === "Digit2") {
        await setSimulationSpeed(2.0);
        setStore({ speedMultiplier: 2.0 });
      } else if (e.code === "Digit5") {
        await setSimulationSpeed(5.0);
        setStore({ speedMultiplier: 5.0 });
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
  }, [isPaused]);

  // Retrieve panels from CA-9 registry
  const leftPanels = defaultPanelRegistry.list("left");
  const rightPanels = defaultPanelRegistry.list("right");

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-gray-950 text-gray-100 font-sans">
      {/* Top Bar with KPIs & Controls */}
      <TopBar />

      {/* Main Operations Canvas Area */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Left Side: Registered Left Panels */}
        {leftPanels.map((p) => {
          const Comp = p.component;
          return <Comp key={p.id} />;
        })}

        {/* Center: 2D Live Operations Canvas */}
        <div className="flex-1 h-full relative overflow-hidden">
          <CanvasMap />
          <SelectedRobotPanel />
        </div>

        {/* Right Side: Registered Right Panels */}
        <div className="w-88 h-full border-l border-gray-800 bg-gray-900/95 flex flex-col z-20">
          {rightPanels.map((p) => {
            const Comp = p.component;
            return <Comp key={p.id} />;
          })}
        </div>
      </div>

      {/* Modals & Dialogs */}
      <EnvironmentModal />
      <ControlModals />
    </div>
  );
};

export default App;
