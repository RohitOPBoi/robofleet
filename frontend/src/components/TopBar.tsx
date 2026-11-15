import React, { useState } from "react";
import {
  AlertTriangle,
  BatteryCharging,
  Clock,
  Flame,
  Info,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Pause,
  Play,
  RotateCw,
  Sun,
  Truck,
  Zap,
} from "lucide-react";
import {
  pauseSimulation,
  resumeSimulation,
  setSimulationSpeed,
  stepSimulation,
  triggerRush,
} from "../services/api";
import { setStore, useStore } from "../store/useStore";

export const TopBar: React.FC = () => {
  const store = useStore();
  const {
    connected,
    kpis,
    simTimeMs,
    isPaused,
    speedMultiplier,
    theme,
    leftPanelOpen,
    rightPanelOpen,
  } = store;
  const [rushPending, setRushPending] = useState(false);

  // Format sim time in HH:mm:ss
  const totalSeconds = Math.floor(simTimeMs / 1000);
  const hours = Math.floor(totalSeconds / 3600) % 24;
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const formattedTime = `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;

  const togglePause = async () => {
    const nextPaused = !isPaused;
    setStore({ isPaused: nextPaused });
    try {
      if (nextPaused) {
        await pauseSimulation();
      } else {
        await resumeSimulation();
      }
    } catch (e) {
      console.error("Simulation pause/resume error:", e);
    }
  };

  const handleSpeed = async (multiplier: number) => {
    setStore({ speedMultiplier: multiplier });
    try {
      await setSimulationSpeed(multiplier);
    } catch (e) {
      console.error("Simulation speed error:", e);
    }
  };

  const handleStep = async () => {
    try {
      await stepSimulation();
    } catch (e) {
      console.error("Simulation step error:", e);
    }
  };

  const handleRush = async () => {
    setRushPending(true);
    try {
      await triggerRush(2.5, 300);
    } catch (e) {
      console.error("Rush burst error:", e);
    } finally {
      setTimeout(() => setRushPending(false), 1500);
    }
  };

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setStore({ theme: nextTheme });
    if (nextTheme === "light") {
      document.documentElement.classList.remove("dark");
      document.documentElement.classList.add("light");
    } else {
      document.documentElement.classList.remove("light");
      document.documentElement.classList.add("dark");
    }
  };

  return (
    <header className="h-14 border-b border-gray-800 bg-gray-900/95 backdrop-blur-md px-3.5 flex items-center justify-between text-xs z-30 select-none overflow-hidden shrink-0">
      {/* Left: Brand, Panel Toggle & Sim Controls */}
      <div className="flex items-center gap-2.5 sm:gap-3 shrink-0">
        {/* Toggle Left Sidebar */}
        <button
          type="button"
          onClick={() => setStore({ leftPanelOpen: !leftPanelOpen })}
          className="p-1.5 rounded text-gray-400 hover:text-white hover:bg-gray-800 transition cursor-pointer"
          title={leftPanelOpen ? "Collapse orders sidebar ([)" : "Expand orders sidebar ([)"}
        >
          {leftPanelOpen ? <PanelLeftClose className="w-4 h-4" /> : <PanelLeftOpen className="w-4 h-4" />}
        </button>

        {/* Brand */}
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-blue-600 flex items-center justify-center font-bold text-white text-xs shadow-sm">
            RF
          </div>
          <span className="font-semibold tracking-tight text-white text-sm hidden sm:inline">RoboFleet</span>
          <span className="hidden md:inline text-[11px] px-2 py-0.5 rounded-full bg-blue-950/70 text-blue-400 border border-blue-800/50 font-mono">
            {store.staticWorld?.layout.name || "Dark Store 01"}
          </span>
        </div>

        {/* Sim Clock */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-gray-950/80 border border-gray-800 font-mono text-gray-200">
          <Clock className="w-3.5 h-3.5 text-blue-400 shrink-0" />
          <span className="font-semibold">{formattedTime}</span>
          <span className="text-[10px] text-gray-500 hidden sm:inline">T+{store.tick}</span>
        </div>

        {/* Sim Controls: Play/Pause, Step, Speed */}
        <div className="flex items-center gap-1 bg-gray-950/70 border border-gray-800 rounded-md p-0.5">
          <button
            type="button"
            onClick={togglePause}
            title={isPaused ? "Resume simulation (Space)" : "Pause simulation (Space)"}
            className={`p-1.5 rounded transition cursor-pointer ${isPaused
                ? "bg-amber-500/20 text-amber-400 hover:bg-amber-500/30"
                : "text-gray-300 hover:bg-gray-800 hover:text-white"
              }`}
          >
            {isPaused ? <Play className="w-3.5 h-3.5 fill-current" /> : <Pause className="w-3.5 h-3.5 fill-current" />}
          </button>
          <button
            type="button"
            onClick={handleStep}
            title="Single step simulation"
            className="p-1.5 rounded text-gray-400 hover:bg-gray-800 hover:text-white transition cursor-pointer"
          >
            <RotateCw className="w-3.5 h-3.5" />
          </button>
          <div className="h-4 w-px bg-gray-800 mx-0.5" />
          {[0.5, 1, 2, 5, 10, 20].map((speed) => (
            <button
              key={speed}
              type="button"
              onClick={() => handleSpeed(speed)}
              className={`px-1.5 py-0.5 text-[11px] font-mono rounded transition cursor-pointer ${speedMultiplier === speed
                  ? "bg-blue-600 text-white font-semibold shadow-sm"
                  : "text-gray-400 hover:text-gray-200 hover:bg-gray-800"
                }`}
            >
              {speed}x
            </button>
          ))}
        </div>

        {/* Rush Button */}
        <button
          type="button"
          onClick={handleRush}
          disabled={rushPending}
          className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded font-medium text-xs transition border cursor-pointer ${rushPending
              ? "bg-orange-500/30 border-orange-500 text-orange-300 animate-pulse"
              : "bg-orange-950/30 border-orange-800/80 text-orange-400 hover:bg-orange-900/40"
            }`}
          title="Inject 2.5x demand burst for 5 minutes"
        >
          <Flame className="w-3.5 h-3.5" />
          <span>Rush burst</span>
        </button>
      </div>

      {/* Middle: Live KPI Strip (Adaptive / Responsive) */}
      <div className="hidden xl:flex items-center gap-3.5 bg-gray-950/80 border border-gray-800 px-3 py-1 rounded-lg font-mono text-xs shrink-0">
        <div className="flex items-center gap-1.5" title="Orders waiting in queue">
          <Truck className="w-3.5 h-3.5 text-blue-400" />
          <span className="text-gray-400">Queue:</span>
          <span className="font-semibold text-white">{kpis.queue_depth ?? 0}</span>
        </div>
        <div className="h-3 w-px bg-gray-800" />
        <div className="flex items-center gap-1.5" title="Throughput per hour">
          <Zap className="w-3.5 h-3.5 text-amber-400" />
          <span className="text-gray-400">Rate:</span>
          <span className="font-semibold text-white">{kpis.throughput_orders_per_hr ?? 0}/hr</span>
        </div>
        <div className="h-3 w-px bg-gray-800" />
        <div
          className={`flex items-center gap-1.5 ${kpis.at_risk_orders > 0 ? "text-red-400 font-semibold" : "text-gray-400"
            }`}
          title="Orders nearing SLA deadline"
        >
          <Clock className="w-3.5 h-3.5" />
          <span>At risk:</span>
          <span>{kpis.at_risk_orders ?? 0}</span>
        </div>
        <div className="h-3 w-px bg-gray-800" />
        <div className="flex items-center gap-1.5" title="Moving / Idle / Charging AMRs">
          <BatteryCharging className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-gray-400">AMRs:</span>
          <span className="text-emerald-400">{kpis.robots_moving ?? 0}m</span>
          <span className="text-gray-500">/</span>
          <span className="text-gray-300">{kpis.robots_idle ?? 0}i</span>
          <span className="text-gray-500">/</span>
          <span className="text-amber-400">{kpis.robots_charging ?? 0}c</span>
        </div>
        <div className="h-3 w-px bg-gray-800" />
        <div
          className={`flex items-center gap-1.5 ${(kpis.active_alerts_count ?? 0) > 0 ? "text-amber-400" : "text-gray-400"
            }`}
          title="Active safety alerts"
        >
          <AlertTriangle className="w-3.5 h-3.5" />
          <span>Alerts:</span>
          <span className="font-semibold">{kpis.active_alerts_count ?? 0}</span>
        </div>
      </div>

      {/* Right: Environment Badge, E-Stop, Theme & Sidebar Toggle */}
      <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
        {/* Environment Disclosure Badge */}
        <button
          type="button"
          onClick={() => setStore({ isEnvironmentModalOpen: true })}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-950/60 border border-emerald-800/80 text-emerald-400 hover:bg-emerald-900/60 transition text-xs font-medium cursor-pointer"
          title="Single disclosure surface — view simulation environment details"
        >
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          <span className="hidden sm:inline">DIGITAL TWIN</span>
          <Info className="w-3 h-3 text-emerald-400/80" />
        </button>

        {/* E-Stop Trigger Button */}
        <button
          type="button"
          onClick={() => setStore({ isEStopModalOpen: true })}
          className="flex items-center gap-1 px-2.5 py-1 rounded bg-red-950/40 border border-red-800 text-red-400 hover:bg-red-900/60 transition font-medium text-xs cursor-pointer shadow-sm"
          title="Trigger emergency stop"
        >
          <AlertTriangle className="w-3.5 h-3.5" />
          <span>E-STOP</span>
        </button>

        {/* Theme Toggle */}
        <button
          type="button"
          onClick={toggleTheme}
          className="p-1.5 rounded text-gray-400 hover:text-white hover:bg-gray-800 transition cursor-pointer"
          title="Toggle light/dark theme"
        >
          {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>

        {/* Connection status indicator */}
        <div
          className="flex items-center gap-1.5 pl-2 border-l border-gray-800 text-xs font-mono"
          title={connected ? "Connected to simulation stream" : "Reconnecting to simulation stream..."}
        >
          <span className={`w-2 h-2 rounded-full ${connected ? "bg-emerald-500" : "bg-amber-500"}`} />
          <span className="text-gray-400 hidden sm:inline">{connected ? "Live" : "Offline"}</span>
        </div>

        {/* Toggle Right Sidebar */}
        <button
          type="button"
          onClick={() => setStore({ rightPanelOpen: !rightPanelOpen })}
          className="p-1.5 rounded text-gray-400 hover:text-white hover:bg-gray-800 transition cursor-pointer"
          title={rightPanelOpen ? "Collapse alerts sidebar (])" : "Expand alerts sidebar (])"}
        >
          {rightPanelOpen ? <PanelRightClose className="w-4 h-4" /> : <PanelRightOpen className="w-4 h-4" />}
        </button>
      </div>
    </header>
  );
};
