import React, { useState } from "react";
import {
  AlertOctagon,
  AlertTriangle,
  BatteryCharging,
  Brain,
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
  RotateCcw,
  RotateCw,
  ShieldCheck,
  StepForward,
  Sun,
  Terminal,
  Truck,
  UserCheck,
  Zap,
  ZapOff,
} from "lucide-react";
import {
  pauseSimulation,
  restartSimulation,
  resumeSimulation,
  scaleFleet,
  setBrainMode,
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

  const handleRestart = async () => {
    try {
      await restartSimulation();
      setStore({
        tick: 0,
        simTimeMs: 0,
        orders: {},
        activeFaults: [],
        alerts: [],
        selectedRobotId: null,
      });
    } catch (e) {
      console.error("Simulation restart error:", e);
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

  const handleToggleAiMode = async (mode: "baseline" | "ai") => {
    const isAi = mode === "ai";
    setStore({ aiMode: mode });
    try {
      await setBrainMode(isAi);
    } catch (e) {
      console.error("Failed to toggle AI mode:", e);
    }
  };

  return (
    <header className="h-14 border-b border-white/10 bg-gray-950/95 backdrop-blur-xl px-2 sm:px-3 flex items-center justify-between text-xs z-30 select-none overflow-hidden shrink-0 gap-1.5 md:gap-2">
      {/* Left: Brand, Panel Toggle & Sim Controls */}
      <div className="flex items-center gap-1.5 shrink-0">
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
        </div>

        {/* Sim Clock */}
        <div className="flex items-center gap-1 px-2 py-1 rounded-lg bg-gray-900 border border-white/5 font-mono text-gray-200">
          <Clock className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
          <span className="font-bold text-xs">{formattedTime}</span>
          <span className="text-[10px] text-gray-500 hidden md:inline">T+{store.tick}</span>
        </div>

        {/* Sim Controls: Play/Pause, Step, Restart */}
        <div className="flex items-center gap-0.5 bg-gray-900 border border-white/5 rounded-lg p-0.5">
          <button
            type="button"
            onClick={togglePause}
            title={isPaused ? "Resume simulation (Space)" : "Pause simulation (Space)"}
            className={`p-1.5 rounded-md transition active:scale-95 cursor-pointer ${isPaused
              ? "bg-amber-500/20 text-amber-400 hover:bg-amber-500/30"
              : "text-gray-300 hover:bg-white/10 hover:text-white"
              }`}
          >
            {isPaused ? <Play className="w-3.5 h-3.5 fill-current" /> : <Pause className="w-3.5 h-3.5 fill-current" />}
          </button>
          <button
            type="button"
            onClick={handleStep}
            title="Single step (1 tick)"
            className="p-1.5 rounded-md text-gray-400 hover:bg-white/10 hover:text-white transition active:scale-95 cursor-pointer"
          >
            <StepForward className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={handleRestart}
            title="Restart simulation (Reset to T+0)"
            className="p-1.5 rounded-md text-amber-400 hover:bg-amber-500/20 hover:text-amber-300 transition active:scale-95 cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Speed Controls: Ultra-Sleek Segmented Pill Tabs */}
        <div className="hidden sm:flex items-center gap-0.5 bg-gray-900 border border-white/5 rounded-lg p-0.5">
          {[0.5, 1, 2, 5, 10, 20].map((speed) => (
            <button
              key={speed}
              type="button"
              onClick={() => handleSpeed(speed)}
              className={`px-1.5 py-0.5 text-[10px] font-mono rounded-md transition active:scale-95 cursor-pointer ${speedMultiplier === speed
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
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-medium text-xs transition border cursor-pointer active:scale-95 ${
            rushPending
              ? "bg-orange-600 text-white border-orange-500 shadow-md shadow-orange-600/30 animate-pulse font-bold"
              : "bg-orange-950/50 border-orange-700/80 text-orange-400 hover:bg-orange-900/60 hover:text-orange-300"
          }`}
          title="Inject immediate 2.5x demand surge + 6 priority orders burst"
        >
          <Flame className={`w-3.5 h-3.5 ${rushPending ? "animate-bounce text-yellow-300" : ""}`} />
          <span className="text-[11px] font-semibold">{rushPending ? "Rushing..." : "Rush Mode"}</span>
        </button>

        {/* Dynamic Fleet Scale Controls */}
        <div className="hidden md:flex items-center gap-1 bg-gray-900 border border-white/5 rounded-lg px-2 py-1 font-mono text-[10px]">
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

        {/* Baseline | AI Mode Segmented Switcher */}
        <div className="flex items-center gap-0.5 bg-gray-900 border border-white/10 rounded-lg p-0.5 font-mono text-[10px]">
          <button
            type="button"
            onClick={() => handleToggleAiMode("baseline")}
            className={`px-1.5 py-0.5 rounded-md font-bold transition active:scale-95 cursor-pointer ${store.aiMode === "baseline"
              ? "bg-gray-700 text-white shadow-sm"
              : "text-gray-400 hover:text-gray-200"
              }`}
            title="Baseline deterministic heuristic control"
          >
            BASE
          </button>
          <button
            type="button"
            onClick={() => handleToggleAiMode("ai")}
            className={`px-1.5 py-0.5 rounded-md font-bold transition active:scale-95 cursor-pointer flex items-center gap-1 ${store.aiMode === "ai"
              ? "bg-gradient-to-r from-indigo-500 to-purple-600 text-white shadow-sm shadow-indigo-500/30"
              : "text-gray-400 hover:text-gray-200"
              }`}
            title="AI Operations Brain (Mission Orchestrator + Specialists)"
          >
            <Brain className="w-3 h-3" />
            AI
          </button>
        </div>
      </div>

      {/* Middle: Live KPI Strip (Responsive) */}
      <div className="hidden 2xl:flex items-center gap-2 bg-gray-900/90 border border-white/5 px-2 py-1 rounded-lg font-mono text-[11px] shrink-0">
        <div className="flex items-center gap-1" title="Orders waiting in queue">
          <Truck className="w-3 h-3 text-cyan-400" />
          <span className="text-gray-400">Q:</span>
          <span className="font-bold text-white">{kpis.queue_depth ?? 0}</span>
        </div>
        <div className="h-3 w-px bg-white/10" />
        <div className="flex items-center gap-1" title="Throughput per hour">
          <Zap className="w-3 h-3 text-amber-400" />
          <span className="text-gray-400">Rate:</span>
          <span className="font-bold text-white">{kpis.throughput_orders_per_hr ?? 0}/h</span>
        </div>
        <div className="h-3 w-px bg-white/10" />
        <div
          className={`flex items-center gap-1 ${(kpis.at_risk_orders ?? 0) > 0 ? "text-red-400 font-bold" : "text-gray-400"
            }`}
          title="Orders nearing SLA deadline"
        >
          <Clock className="w-3 h-3" />
          <span>Risk:</span>
          <span>{kpis.at_risk_orders ?? 0}</span>
        </div>
        <div className="h-3 w-px bg-white/10" />
        <div className="flex items-center gap-1" title="AMR Fleet Utilization">
          <BatteryCharging className="w-3 h-3 text-emerald-400" />
          <span className="text-emerald-400">{kpis.robots_moving ?? 0}m</span>
          <span className="text-gray-500">/</span>
          <span className="text-gray-300">{kpis.robots_idle ?? 0}i</span>
        </div>
        <div className="h-3 w-px bg-white/10" />
        <div
          className={`flex items-center gap-1 ${(kpis.active_alerts_count ?? 0) > 0 ? "text-amber-400 font-bold" : "text-gray-400"
            }`}
          title="Active safety alerts"
        >
          <AlertTriangle className="w-3 h-3" />
          <span>{kpis.active_alerts_count ?? 0}</span>
        </div>
      </div>

      {/* Right: Operations Intelligence Buttons, 2D/3D Switcher, E-Stop, Twin Badge */}
      <div className="flex items-center gap-1 shrink-0">
        {/* AI Operations Brain Buttons */}
        <button
          type="button"
          onClick={() => setStore({ isDecisionLogOpen: true })}
          className={`flex items-center gap-1 px-1.5 py-1 rounded-lg border text-[10px] font-medium transition cursor-pointer active:scale-95 ${store.isDecisionLogOpen
            ? "bg-indigo-950 border-indigo-700 text-indigo-300 shadow-sm"
            : "bg-gray-900 border-white/5 text-gray-300 hover:bg-gray-800"
            }`}
          title="Open AI Operations Decision Log"
        >
          <Brain className="w-3.5 h-3.5 text-indigo-400" />
          <span className="hidden xl:inline">Decisions</span>
          <span className="px-1 py-0.2 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-800 text-[9px] font-mono">
            {store.decisions.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setStore({ isApprovalsDrawerOpen: true })}
          className={`flex items-center gap-1 px-1.5 py-1 rounded-lg border text-[10px] font-medium transition cursor-pointer active:scale-95 ${store.pendingApprovals.length > 0
            ? "bg-amber-950/80 border-amber-600 text-amber-300 animate-pulse"
            : "bg-gray-900 border-white/5 text-gray-300 hover:bg-gray-800"
            }`}
          title="Open Human-In-The-Loop Governance Queue"
        >
          <UserCheck className="w-3.5 h-3.5 text-amber-400" />
          <span className="hidden xl:inline">Approvals</span>
          {store.pendingApprovals.length > 0 && (
            <span className="px-1 py-0.2 rounded-full bg-amber-500 text-black font-extrabold text-[9px] font-mono">
              {store.pendingApprovals.length}
            </span>
          )}
        </button>

        {/* Phase 6: Chaos Engineering Studio */}
        <button
          type="button"
          onClick={() => setStore({ isChaosControlOpen: true })}
          className={`flex items-center gap-1 px-1.5 py-1 rounded-lg border text-[10px] font-medium transition cursor-pointer active:scale-95 ${store.activeFaults.length > 0
            ? "bg-red-950/80 border-red-500 text-red-300 animate-pulse shadow-sm shadow-red-500/20"
            : "bg-gray-900 border-white/5 text-gray-300 hover:bg-gray-800"
            }`}
          title="Open Chaos Engineering & Resilience Studio"
        >
          <ZapOff className="w-3.5 h-3.5 text-red-400" />
          <span className="hidden xl:inline">Chaos</span>
          {store.activeFaults.length > 0 && (
            <span className="px-1 py-0.2 rounded-full bg-red-500 text-white font-extrabold text-[9px] font-mono">
              {store.activeFaults.length}
            </span>
          )}
        </button>

        {/* Phase 6: Supervisor Exceptions Queue */}
        <button
          type="button"
          onClick={() => setStore({ isExceptionsQueueOpen: true })}
          className={`flex items-center gap-1 px-1.5 py-1 rounded-lg border text-[10px] font-medium transition cursor-pointer active:scale-95 ${store.pendingExceptions.length > 0
            ? "bg-amber-950/80 border-amber-500 text-amber-300 animate-pulse shadow-sm shadow-amber-500/20"
            : "bg-gray-900 border-white/5 text-gray-300 hover:bg-gray-800"
            }`}
          title="Open Supervisor Exceptions Queue"
        >
          <AlertOctagon className="w-3.5 h-3.5 text-amber-400" />
          <span className="hidden xl:inline">Exceptions</span>
          {store.pendingExceptions.length > 0 && (
            <span className="px-1 py-0.2 rounded-full bg-amber-500 text-black font-extrabold text-[9px] font-mono">
              {store.pendingExceptions.length}
            </span>
          )}
        </button>

        {/* Phase 6: Immutable Audit Log Viewer */}
        <button
          type="button"
          onClick={() => setStore({ isAuditLogOpen: true })}
          className={`flex items-center gap-1 px-1.5 py-1 rounded-lg border text-[10px] font-medium transition cursor-pointer active:scale-95 ${store.isAuditLogOpen
            ? "bg-emerald-950 border-emerald-700 text-emerald-300 shadow-sm"
            : "bg-gray-900 border-white/5 text-gray-300 hover:bg-gray-800"
            }`}
          title="Open Immutable SQLite Audit Ledger"
        >
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span className="hidden xl:inline">Audit</span>
        </button>

        {/* Natural Language Command Bar Trigger */}
        <button
          type="button"
          onClick={() => setStore({ isSupervisorBarOpen: true })}
          className="flex items-center gap-1 px-1.5 py-1 rounded-lg bg-gray-900 hover:bg-gray-800 border border-white/5 text-gray-300 hover:text-white text-[10px] font-medium transition cursor-pointer active:scale-95"
          title="Open Natural Language Supervisor Command Bar (Ctrl+K)"
        >
          <Terminal className="w-3.5 h-3.5 text-cyan-400" />
          <span className="hidden 2xl:inline">Command</span>
        </button>

        {/* 2D / 3D / Split View Mode Switcher */}
        <div className="flex items-center gap-0.5 bg-gray-900 border border-white/10 rounded-lg p-0.5 font-mono text-[10px]">
          <button
            type="button"
            onClick={() => setStore({ viewMode: "2d" })}
            className={`px-1.5 py-0.5 rounded-md transition cursor-pointer active:scale-95 font-bold ${store.viewMode === "2d"
              ? "bg-cyan-500 text-black shadow-sm shadow-cyan-500/40"
              : "text-gray-400 hover:text-white hover:bg-white/5"
              }`}
            title="2D Tactical Map View"
          >
            2D
          </button>
          <button
            type="button"
            onClick={() => setStore({ viewMode: "3d" })}
            className={`px-1.5 py-0.5 rounded-md transition cursor-pointer active:scale-95 font-bold ${store.viewMode === "3d"
              ? "bg-cyan-500 text-black shadow-sm shadow-cyan-500/40"
              : "text-gray-400 hover:text-white hover:bg-white/5"
              }`}
            title="3D WebGL Digital Twin View"
          >
            3D
          </button>
          <button
            type="button"
            onClick={() => setStore({ viewMode: "split" })}
            className={`px-1.5 py-0.5 rounded-md transition cursor-pointer active:scale-95 font-bold ${store.viewMode === "split"
              ? "bg-cyan-500 text-black shadow-sm shadow-cyan-500/40"
              : "text-gray-400 hover:text-white hover:bg-white/5"
              }`}
            title="Split Screen (2D + 3D Synchronized View)"
          >
            SPLIT
          </button>
        </div>

        {/* Environment Disclosure Badge */}
        <button
          type="button"
          aria-label="DIGITAL TWIN"
          onClick={() => setStore({ isEnvironmentModalOpen: true })}
          className="flex items-center gap-1 px-1.5 py-1 rounded-full bg-emerald-950/60 border border-emerald-800/80 text-emerald-400 hover:bg-emerald-900/60 transition text-[10px] font-semibold cursor-pointer active:scale-95"
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
          className="flex items-center gap-1 px-1.5 py-1 rounded-lg bg-red-950/60 border border-red-800/80 text-red-400 hover:bg-red-900/60 transition font-bold text-[10px] cursor-pointer shadow-sm active:scale-95"
          title="Trigger emergency stop"
        >
          <AlertTriangle className="w-3 h-3" />
          <span>E-STOP</span>
        </button>

        {/* Theme Toggle */}
        <button
          type="button"
          onClick={toggleTheme}
          className="p-1 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition active:scale-95 cursor-pointer"
          title="Toggle Light/Dark Theme"
        >
          {theme === "dark" ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
        </button>

        {/* Connection status indicator */}
        <div
          className="flex items-center gap-1 pl-1 border-l border-white/10 text-[10px] font-mono"
          title={connected ? "Connected to simulation stream" : "Reconnecting to simulation stream..."}
        >
          <span className={`w-2 h-2 rounded-full ${connected ? "bg-emerald-400 shadow-sm shadow-emerald-400/80 animate-pulse" : "bg-amber-500"}`} />
          <span className="text-gray-400 hidden xl:inline">{connected ? "Live" : "Offline"}</span>
        </div>

        {/* Toggle Right Sidebar */}
        <button
          type="button"
          onClick={() => setStore({ rightPanelOpen: !rightPanelOpen })}
          className="p-1 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition active:scale-95 cursor-pointer"
          title={rightPanelOpen ? "Collapse alerts sidebar (])" : "Expand alerts sidebar (])"}
        >
          {rightPanelOpen ? <PanelRightClose className="w-4 h-4" /> : <PanelRightOpen className="w-4 h-4" />}
        </button>
      </div>
    </header>
  );
};
