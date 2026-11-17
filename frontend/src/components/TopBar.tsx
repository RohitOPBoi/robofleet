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
  scaleFleet,
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

  const robotCount = Object.keys(store.robots).length;

  return (
    <header className="h-14 border-b border-white/10 bg-gray-950/95 backdrop-blur-xl px-3 flex items-center justify-between text-xs z-30 select-none overflow-x-auto overflow-y-hidden shrink-0 gap-2">
      {/* Left: Brand, Panel Toggle & Sim Controls */}
      <div className="flex items-center gap-2 shrink-0">
        {/* Toggle Left Sidebar */}
        <button
          type="button"
          onClick={() => setStore({ leftPanelOpen: !leftPanelOpen })}
          className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition active:scale-95 cursor-pointer"
          title={leftPanelOpen ? "Collapse orders sidebar ([)" : "Expand orders sidebar ([)"}
        >
          {leftPanelOpen ? <PanelLeftClose className="w-4 h-4" /> : <PanelLeftOpen className="w-4 h-4" />}
        </button>

        {/* Brand */}
        <div className="flex items-center gap-1.5">
          <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center font-black text-black text-xs shadow-md shadow-cyan-500/25">
            RF
          </div>
          <span className="font-bold tracking-tight text-white text-sm hidden sm:inline">RoboFleet</span>
          <span className="hidden lg:inline text-[10px] px-2 py-0.5 rounded-full bg-cyan-950/80 text-cyan-400 border border-cyan-800/60 font-mono">
            {store.staticWorld?.layout.name || "Dark Store 01"}
          </span>
        </div>

        {/* Sim Clock */}
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-gray-900 border border-white/5 font-mono text-gray-200">
          <Clock className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
          <span className="font-bold text-xs">{formattedTime}</span>
          <span className="text-[10px] text-gray-500 hidden md:inline">T+{store.tick}</span>
        </div>

        {/* Sim Controls: Play/Pause, Step */}
        <div className="flex items-center gap-0.5 bg-gray-900 border border-white/5 rounded-lg p-0.5">
          <button
            type="button"
            onClick={togglePause}
            title={isPaused ? "Resume simulation (Space)" : "Pause simulation (Space)"}
            className={`p-1.5 rounded-md transition active:scale-95 cursor-pointer ${
              isPaused
                ? "bg-amber-500/20 text-amber-400 hover:bg-amber-500/30"
                : "text-gray-300 hover:bg-white/10 hover:text-white"
            }`}
          >
            {isPaused ? <Play className="w-3.5 h-3.5 fill-current" /> : <Pause className="w-3.5 h-3.5 fill-current" />}
          </button>
          <button
            type="button"
            onClick={handleStep}
            title="Single step simulation"
            className="p-1.5 rounded-md text-gray-400 hover:bg-white/10 hover:text-white transition active:scale-95 cursor-pointer"
          >
            <RotateCw className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Speed Controls: Ultra-Sleek Segmented Pill Tabs */}
        <div className="flex items-center gap-0.5 bg-gray-900 border border-white/5 rounded-lg p-0.5">
          {[0.5, 1, 2, 5, 10, 20].map((speed) => (
            <button
              key={speed}
              type="button"
              onClick={() => handleSpeed(speed)}
              className={`px-1.5 py-0.5 text-[10px] font-mono rounded-md transition active:scale-95 cursor-pointer ${
                speedMultiplier === speed
                  ? "bg-cyan-500 text-black font-extrabold shadow-sm shadow-cyan-500/40"
                  : "text-gray-400 hover:text-gray-200 hover:bg-white/5"
              }`}
              title={`Set speed to ${speed}x`}
            >
              {speed}x
            </button>
          ))}
        </div>

        {/* Rush Burst Trigger */}
        <button
          type="button"
          onClick={handleRush}
          disabled={rushPending}
          className={`hidden md:flex items-center gap-1 px-2 py-1 rounded-lg font-medium text-xs transition border cursor-pointer active:scale-95 ${
            rushPending
              ? "bg-orange-500/30 border-orange-500 text-orange-300 animate-pulse"
              : "bg-orange-950/40 border-orange-800/80 text-orange-400 hover:bg-orange-900/50"
          }`}
          title="Inject 2.5x demand rush burst"
        >
          <Flame className="w-3.5 h-3.5" />
          <span className="text-[11px]">Rush</span>
        </button>

        {/* Dynamic Fleet Scale Controls (P3-A10) */}
        <div className="flex items-center gap-1 bg-gray-900 border border-white/5 rounded-lg px-2 py-1 font-mono text-[10px]">
          <span className="text-gray-400">{robotCount} AMRs</span>
          <div className="flex items-center gap-0.5 ml-0.5">
            <button
              type="button"
              onClick={async () => {
                const count = Math.max(1, robotCount - 1);
                await scaleFleet(count);
              }}
              className="w-4 h-4 flex items-center justify-center rounded bg-gray-800 hover:bg-gray-700 text-gray-200 transition active:scale-90 cursor-pointer font-bold"
              title="Retire 1 AMR"
            >
              -
            </button>
            <button
              type="button"
              onClick={async () => {
                const count = Math.min(100, robotCount + 1);
                await scaleFleet(count);
              }}
              className="w-4 h-4 flex items-center justify-center rounded bg-gray-800 hover:bg-gray-700 text-gray-200 transition active:scale-90 cursor-pointer font-bold"
              title="Spawn 1 AMR"
            >
              +
            </button>
          </div>
        </div>
      </div>

      {/* Middle: Live KPI Strip (Adaptive / Responsive) */}
      <div className="hidden lg:flex items-center gap-2.5 bg-gray-900/90 border border-white/5 px-2.5 py-1 rounded-lg font-mono text-[11px] shrink-0">
        <div className="flex items-center gap-1" title="Orders waiting in queue">
          <Truck className="w-3 h-3 text-cyan-400" />
          <span className="text-gray-400">Queue:</span>
          <span className="font-bold text-white">{kpis.queue_depth ?? 0}</span>
        </div>
        <div className="h-3 w-px bg-white/10" />
        <div className="flex items-center gap-1" title="Throughput per hour">
          <Zap className="w-3 h-3 text-amber-400" />
          <span className="text-gray-400">Rate:</span>
          <span className="font-bold text-white">{kpis.throughput_orders_per_hr ?? 0}/hr</span>
        </div>
        <div className="h-3 w-px bg-white/10" />
        <div
          className={`flex items-center gap-1 ${
            (kpis.at_risk_orders ?? 0) > 0 ? "text-red-400 font-bold" : "text-gray-400"
          }`}
          title="Orders nearing SLA deadline"
        >
          <Clock className="w-3 h-3" />
          <span>At risk:</span>
          <span>{kpis.at_risk_orders ?? 0}</span>
        </div>
        <div className="h-3 w-px bg-white/10" />
        <div className="flex items-center gap-1" title="AMR Fleet Utilization">
          <BatteryCharging className="w-3 h-3 text-emerald-400" />
          <span className="text-emerald-400">{kpis.robots_moving ?? 0}m</span>
          <span className="text-gray-500">/</span>
          <span className="text-gray-300">{kpis.robots_idle ?? 0}i</span>
          <span className="text-gray-500">/</span>
          <span className="text-amber-400">{kpis.robots_charging ?? 0}c</span>
        </div>
        <div className="h-3 w-px bg-white/10" />
        <div
          className={`flex items-center gap-1 ${
            (kpis.active_alerts_count ?? 0) > 0 ? "text-amber-400 font-bold" : "text-gray-400"
          }`}
          title="Active safety alerts"
        >
          <AlertTriangle className="w-3 h-3" />
          <span>Alerts:</span>
          <span>{kpis.active_alerts_count ?? 0}</span>
        </div>
      </div>

      {/* Right: Environment Badge, E-Stop, Theme & Sidebar Toggle */}
      <div className="flex items-center gap-1.5 shrink-0">
        {/* Environment Disclosure Badge */}
        <button
          type="button"
          onClick={() => setStore({ isEnvironmentModalOpen: true })}
          className="flex items-center gap-1 px-2 py-1 rounded-full bg-emerald-950/60 border border-emerald-800/80 text-emerald-400 hover:bg-emerald-900/60 transition text-[10px] font-semibold cursor-pointer active:scale-95"
          title="Single disclosure surface — view simulation environment details"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
          <span className="hidden sm:inline">DIGITAL TWIN</span>
          <Info className="w-3 h-3 text-emerald-400/80" />
        </button>

        {/* E-Stop Trigger Button */}
        <button
          type="button"
          onClick={() => setStore({ isEStopModalOpen: true })}
          className="flex items-center gap-1 px-2 py-1 rounded-lg bg-red-950/60 border border-red-800/80 text-red-400 hover:bg-red-900/60 transition font-bold text-[10px] cursor-pointer shadow-sm active:scale-95"
          title="Trigger emergency stop"
        >
          <AlertTriangle className="w-3 h-3" />
          <span>E-STOP</span>
        </button>

        {/* Theme Toggle */}
        <button
          type="button"
          onClick={toggleTheme}
          className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition active:scale-95 cursor-pointer"
          title="Toggle light/dark theme"
        >
          {theme === "dark" ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
        </button>

        {/* Connection status indicator */}
        <div
          className="flex items-center gap-1 pl-1.5 border-l border-white/10 text-[10px] font-mono"
          title={connected ? "Connected to simulation stream" : "Reconnecting to simulation stream..."}
        >
          <span className={`w-2 h-2 rounded-full ${connected ? "bg-emerald-400 shadow-sm shadow-emerald-400/80 animate-pulse" : "bg-amber-500"}`} />
          <span className="text-gray-400 hidden sm:inline">{connected ? "Live" : "Offline"}</span>
        </div>

        {/* Toggle Right Sidebar */}
        <button
          type="button"
          onClick={() => setStore({ rightPanelOpen: !rightPanelOpen })}
          className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition active:scale-95 cursor-pointer"
          title={rightPanelOpen ? "Collapse alerts sidebar (])" : "Expand alerts sidebar (])"}
        >
          {rightPanelOpen ? <PanelRightClose className="w-4 h-4" /> : <PanelRightOpen className="w-4 h-4" />}
        </button>
      </div>
    </header>
  );
};
