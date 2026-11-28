import React, { useState } from "react";
import {
  Activity,
  BarChart3,
  Brain,
  Flame,
  Info,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Pause,
  Play,
  RotateCcw,
  Settings,
  StepForward,
  Sun,
  UserCheck,
  ZapOff,
} from "lucide-react";
import {
  pauseSimulation,
  restartSimulation,
  resumeSimulation,
  scaleFleet,
  setBrainMode,
  setBrainProvider,
  setSimulationSpeed,
  stepSimulation,
  triggerRush,
} from "../services/api";
import { setStore, useStore } from "../store/useStore";

export const TopBar: React.FC = () => {
  const store = useStore();
  const {
    activeWorkspaceView,
    alerts,
    activeFaults,
    activeFaultsCount,
    aiMode,
    brainConnectionState,
    decisions,
    environmentDisclosure,
    isPaused,
    leftPanelOpen,
    pendingApprovals,
    rightPanelOpen,
    robots,
    simTimeMs,
    speedMultiplier,
    staticWorld,
    theme,
    tick,
  } = store;

  const [rushPending, setRushPending] = useState(false);

  // Format sim time in HH:mm:ss
  const totalSeconds = Math.floor(simTimeMs / 1000);
  const hours = Math.floor(totalSeconds / 3600) % 24;
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const formattedTime = `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;

  const robotCount = Object.keys(robots).length;
  const activeAlertCount = alerts.filter((a) => !a.cleared).length;
  const faultCount = Math.max(activeFaults.length, activeFaultsCount);
  const scenarioRaw =
    environmentDisclosure?.scenario ||
    staticWorld?.meta?.scenario_name ||
    "standard";
  const scenarioBase = scenarioRaw.charAt(0).toUpperCase() + scenarioRaw.slice(1);

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
        kpiHistory: [],
        selectedRobotId: null,
      });
    } catch (e) {
      console.error("Simulation restart error:", e);
    }
  };

  const handleRush = async () => {
    if (rushPending) return;
    setRushPending(true);
    try {
      await triggerRush(2.5, 300);
    } catch (e) {
      console.error("Rush burst error:", e);
    } finally {
      setTimeout(() => setRushPending(false), 600);
    }
  };

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setStore({ theme: nextTheme });
    if (typeof localStorage !== "undefined") {
      localStorage.setItem("ROBOFLEET_THEME", nextTheme);
    }
    if (nextTheme === "light") {
      document.documentElement.classList.remove("dark");
      document.documentElement.classList.add("light");
    } else {
      document.documentElement.classList.remove("light");
      document.documentElement.classList.add("dark");
    }
  };

  const handleSelectOperatingMode = async (
    mode: "baseline" | "heuristic" | "ai" | "local_llm"
  ) => {
    setStore({ aiMode: mode });
    try {
      const res =
        mode === "baseline" ? await setBrainMode(false) : await setBrainProvider(mode);
      if (res) {
        setStore({
          aiMode: res.mode || mode,
          brainProvider: res.provider || mode,
          brainConnectionState: res.connection_state || brainConnectionState,
          brainModelName: res.model_name || "",
        });
      }
    } catch (e) {
      console.error("Failed to switch Brain operating mode:", e);
    }
  };

  return (
    <header className="h-14 px-3 xl:px-4 flex items-center justify-between border-b studio-glass-bar z-30 shrink-0 gap-2 select-none">
      {/* Left: Drawer Toggle, Title & Clock Metadata */}
      <div className="flex items-center gap-2 min-w-0 shrink">
        <button
          type="button"
          onClick={() => setStore({ leftPanelOpen: !leftPanelOpen })}
          className="studio-btn p-1.5 rounded-xl bg-[var(--studio-surface-subtle)] hover:bg-[var(--studio-surface-elevated)] border border-[var(--studio-border)] text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] cursor-pointer shrink-0"
          title={leftPanelOpen ? "Collapse orders drawer ([)" : "Expand orders drawer ([)"}
          aria-label={leftPanelOpen ? "Collapse orders drawer" : "Expand orders drawer"}
        >
          {leftPanelOpen ? (
            <PanelLeftClose className="w-4 h-4" strokeWidth={1.5} />
          ) : (
            <PanelLeftOpen className="w-4 h-4" strokeWidth={1.5} />
          )}
        </button>

        <div className="min-w-0 flex flex-col justify-center">
          <h1 className="text-[14px] xl:text-[15px] font-semibold tracking-tight text-[var(--studio-text-primary)] leading-tight whitespace-nowrap">
            RoboFleet<span className="hidden 2xl:inline"> Studio</span>
          </h1>
          <p className="text-[11px] text-[var(--studio-text-muted)] leading-tight whitespace-nowrap font-normal tabular-nums">
            <span>{scenarioBase}</span>
            <span className="mx-1 opacity-55">·</span>
            <span className="font-mono">{formattedTime}</span>
            <span className="mx-1 opacity-55 hidden xl:inline">·</span>
            <span className="font-mono hidden xl:inline">T+{tick}</span>
            <span className="mx-1 opacity-55 hidden sm:inline">·</span>
            <span
              className={`hidden sm:inline font-medium ${isPaused
                ? "text-[#B4691E] dark:text-amber-300"
                : "text-[#1D6144] dark:text-emerald-400"
                }`}
            >
              {isPaused ? "Paused" : "Live"}
            </span>
          </p>
        </div>
      </div>

      {/* Center: Instant View Mode Switcher + Simulation Transport + Fleet & Rush */}
      <div className="flex items-center gap-1.5 shrink-0">
        {/* 2D | 3D | Split | Analytics Direct Switcher */}
        <div
          className="flex items-center gap-0.5 rounded-full p-0.5 border text-[11px]"
          style={{
            background: "var(--studio-surface-subtle)",
            borderColor: "var(--studio-border)",
          }}
        >
          {(["2d", "3d", "split"] as const).map((mode) => {
            const active = activeWorkspaceView === mode;
            return (
              <button
                key={mode}
                type="button"
                aria-pressed={active}
                onClick={() => setStore({ activeWorkspaceView: mode, viewMode: mode })}
                className={`studio-btn px-2 py-1 rounded-full font-semibold uppercase tracking-wide text-[10.5px] cursor-pointer ${active
                  ? "bg-[#1C1917] text-white dark:bg-[#FFFBF8] dark:text-[#241B16] shadow-sm"
                  : "text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)]"
                  }`}
                title={`Switch to ${mode.toUpperCase()} view (V to cycle)`}
              >
                {mode}
              </button>
            );
          })}
          <button
            type="button"
            aria-pressed={activeWorkspaceView === "overview"}
            onClick={() =>
              setStore({
                activeWorkspaceView: activeWorkspaceView === "overview" ? "split" : "overview",
              })
            }
            className={`studio-btn px-2 py-1 rounded-full font-medium text-[10.5px] flex items-center gap-1 cursor-pointer ${activeWorkspaceView === "overview"
              ? "bg-studio-terracotta text-white shadow-sm"
              : "text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)]"
              }`}
            title="Toggle full analytics overview"
          >
            <BarChart3 className="w-3 h-3" strokeWidth={1.5} />
            <span className="hidden lg:inline">Analytics</span>
          </button>
        </div>

        {/* Simulation Transport Pill */}
        <div
          className="flex items-center gap-0.5 rounded-full p-0.5 border text-[11px]"
          style={{
            background: "var(--studio-surface-subtle)",
            borderColor: "var(--studio-border)",
          }}
        >
          <button
            type="button"
            onClick={togglePause}
            aria-label={isPaused ? "Resume simulation" : "Pause simulation"}
            aria-pressed={isPaused}
            title={isPaused ? "Resume simulation (Space)" : "Pause simulation (Space)"}
            className={`studio-btn p-1.5 rounded-full cursor-pointer ${isPaused
              ? "bg-amber-600/18 text-[#8F4F0D] dark:text-amber-300"
              : "text-[var(--studio-text-primary)] hover:bg-black/5 dark:hover:bg-white/10"
              }`}
          >
            {isPaused ? (
              <Play className="w-3.5 h-3.5 fill-current" strokeWidth={1.5} />
            ) : (
              <Pause className="w-3.5 h-3.5 fill-current" strokeWidth={1.5} />
            )}
          </button>
          <button
            type="button"
            onClick={handleStep}
            aria-label="Step simulation one tick"
            title="Single step (1 tick)"
            className="studio-btn p-1.5 rounded-full text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-black/5 dark:hover:bg-white/10 cursor-pointer"
          >
            <StepForward className="w-3.5 h-3.5" strokeWidth={1.5} />
          </button>

          <div className="hidden xl:block w-px h-3.5 bg-[var(--studio-border-strong)] mx-0.5" />

          <div className="hidden xl:flex items-center gap-0.5 font-mono">
            {[1, 2, 5, 10].map((speed) => (
              <button
                key={speed}
                type="button"
                aria-pressed={speedMultiplier === speed}
                onClick={() => handleSpeed(speed)}
                className={`studio-btn px-1.5 py-0.5 rounded-full text-[10px] font-medium cursor-pointer tabular-nums ${speedMultiplier === speed
                  ? "bg-[#1C1917] text-white dark:bg-[#FFFBF8] dark:text-[#241B16]"
                  : "text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)]"
                  }`}
                title={`Set speed to ${speed}x`}
              >
                {speed}x
              </button>
            ))}
          </div>

          <div className="w-px h-3.5 bg-[var(--studio-border-strong)] mx-0.5" />

          <button
            type="button"
            onClick={handleRestart}
            aria-label="Restart simulation"
            title="Restart simulation (Reset to T+0)"
            className="studio-btn p-1.5 rounded-full text-studio-terracotta hover:bg-studio-terracotta/12 cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" strokeWidth={1.5} />
          </button>
        </div>

        {/* Rush Burst & Fleet Scale Direct Access */}
        <button
          type="button"
          onClick={handleRush}
          disabled={rushPending}
          className={`studio-btn flex items-center gap-1 px-2.5 py-1.5 rounded-full text-[11px] font-semibold cursor-pointer border ${rushPending
            ? "bg-studio-terracotta text-white border-studio-terracotta"
            : "bg-studio-terracotta/14 hover:bg-studio-terracotta text-[#A53420] hover:text-white dark:text-[#FFA991] dark:hover:text-white border-studio-terracotta/30"
            }`}
          title="Inject immediate 2.5x express demand surge"
        >
          <Flame className="w-3.5 h-3.5" strokeWidth={1.5} />
          <span className="hidden lg:inline">{rushPending ? "Rushing..." : "Rush"}</span>
        </button>

        <div
          className="hidden lg:flex items-center gap-1 rounded-full px-2 py-1 border font-mono text-[10.5px] tabular-nums"
          style={{
            background: "var(--studio-surface-subtle)",
            borderColor: "var(--studio-border)",
          }}
        >
          <span className="text-[var(--studio-text-secondary)]">{robotCount} AMRs</span>
          <button
            type="button"
            onClick={() => scaleFleet(Math.max(1, robotCount - 1))}
            className="studio-btn w-4 h-4 rounded-full bg-[var(--studio-surface-elevated)] hover:bg-studio-terracotta hover:text-white border border-[var(--studio-border)] text-[var(--studio-text-primary)] flex items-center justify-center cursor-pointer"
            title="Retire 1 AMR"
            aria-label="Decrease fleet size"
          >
            -
          </button>
          <button
            type="button"
            onClick={() => scaleFleet(Math.min(100, robotCount + 1))}
            className="studio-btn w-4 h-4 rounded-full bg-[var(--studio-surface-elevated)] hover:bg-studio-terracotta hover:text-white border border-[var(--studio-border)] text-[var(--studio-text-primary)] flex items-center justify-center cursor-pointer"
            title="Spawn 1 AMR"
            aria-label="Increase fleet size"
          >
            +
          </button>
        </div>
      </div>

      {/* Right: AI Mode Segmented Control, Direct Drawers, Digital Twin, Theme */}
      <div className="flex items-center gap-1.5 shrink-0">
        {/* AI Operating Mode Segmented Pill */}
        <div
          className="hidden md:flex items-center gap-0.5 rounded-full p-0.5 text-[10.5px] font-mono border"
          style={{
            background: "var(--studio-surface-subtle)",
            borderColor: "var(--studio-border)",
          }}
        >
          {(
            [
              { id: "baseline", label: "BASE", activeCls: "bg-[#1C1917] text-white dark:bg-[#FFFBF8] dark:text-[#241B16]" },
              { id: "heuristic", label: "HEUR", activeCls: "bg-studio-terracotta text-white" },
              { id: "ai", label: "AI", activeCls: "bg-studio-amber text-white" },
              { id: "local_llm", label: "LOCAL", activeCls: "bg-studio-sage text-white" },
            ] as const
          ).map((m) => (
            <button
              key={m.id}
              type="button"
              aria-pressed={aiMode === m.id}
              onClick={() => handleSelectOperatingMode(m.id)}
              className={`studio-btn px-2 py-1 rounded-full font-semibold cursor-pointer ${aiMode === m.id
                ? `${m.activeCls} shadow-sm`
                : "text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)]"
                }`}
              title={`Switch Brain mode to ${m.label}`}
            >
              {m.label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setStore({ isAISettingsOpen: true })}
            className="studio-btn p-1.5 rounded-full text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] cursor-pointer"
            title={`Configure AI & Local LLM (${brainConnectionState})`}
            aria-label={`AI & Local Model Settings (${brainConnectionState})`}
          >
            <Settings className="w-3.5 h-3.5" strokeWidth={1.5} />
          </button>
        </div>

        {/* Direct Operational Drawer Pills */}
        <button
          type="button"
          onClick={() => setStore({ isDecisionLogOpen: true })}
          className="studio-btn flex items-center gap-1 px-2 py-1.5 rounded-full bg-[var(--studio-surface-subtle)] hover:bg-[var(--studio-surface-elevated)] border border-[var(--studio-border)] text-[var(--studio-text-primary)] text-[11px] font-medium cursor-pointer"
          title="Open AI Operations Decision Log"
        >
          <Brain className="w-3.5 h-3.5 text-studio-terracotta" strokeWidth={1.5} />
          <span className="hidden 2xl:inline">Decisions</span>
          <span className="font-mono text-[10px] text-[var(--studio-text-muted)] tabular-nums">
            {decisions.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setStore({ isApprovalsDrawerOpen: true })}
          className={`studio-btn flex items-center gap-1 px-2 py-1.5 rounded-full border text-[11px] font-medium cursor-pointer ${pendingApprovals.length > 0
            ? "bg-amber-600/15 border-amber-700/35 text-[#8F4F0D] dark:text-amber-300"
            : "bg-[var(--studio-surface-subtle)] hover:bg-[var(--studio-surface-elevated)] border-[var(--studio-border)] text-[var(--studio-text-primary)]"
            }`}
          title="Open Governance Approvals Queue"
        >
          <UserCheck className="w-3.5 h-3.5" strokeWidth={1.5} />
          {pendingApprovals.length > 0 && (
            <span className="font-mono text-[10px] font-semibold tabular-nums">
              {pendingApprovals.length}
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setStore({ isChaosControlOpen: true })}
          className={`studio-btn flex items-center gap-1 px-2 py-1.5 rounded-full border text-[11px] font-medium cursor-pointer ${faultCount > 0
            ? "bg-red-600/15 border-red-700/35 text-[#9E2418] dark:text-red-300"
            : "bg-[var(--studio-surface-subtle)] hover:bg-[var(--studio-surface-elevated)] border-[var(--studio-border)] text-[var(--studio-text-primary)]"
            }`}
          title="Open Chaos & Fault Resilience Studio"
        >
          <ZapOff className="w-3.5 h-3.5" strokeWidth={1.5} />
          {faultCount > 0 && (
            <span className="font-mono text-[10px] font-semibold tabular-nums">
              {faultCount}
            </span>
          )}
        </button>

        {/* Activity Drawer Toggle */}
        <button
          type="button"
          aria-expanded={rightPanelOpen}
          onClick={() => setStore({ rightPanelOpen: !rightPanelOpen })}
          className={`studio-btn flex items-center gap-1.5 px-2.5 py-1.5 rounded-full border text-[11px] font-medium cursor-pointer whitespace-nowrap ${rightPanelOpen
            ? "bg-[var(--studio-surface-elevated)] border-studio-terracotta/40 text-[var(--studio-text-primary)] shadow-sm"
            : "bg-[var(--studio-surface-subtle)] border-[var(--studio-border)] text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)]"
            }`}
          title={rightPanelOpen ? "Collapse alerts & events drawer (])" : "Open alerts & events drawer (])"}
        >
          <Activity className="w-3.5 h-3.5" strokeWidth={1.5} />
          <span className="hidden 2xl:inline">Activity</span>
          {activeAlertCount > 0 && (
            <span className="px-1.5 py-0.5 rounded-full bg-studio-terracotta text-white text-[9.5px] font-semibold leading-none tabular-nums">
              {activeAlertCount}
            </span>
          )}
        </button>

        {/* Environment Disclosure Pill (Exact Playwright role+name "DIGITAL TWIN") */}
        <button
          type="button"
          aria-label="DIGITAL TWIN"
          onClick={() => setStore({ isEnvironmentModalOpen: true })}
          className="studio-btn flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-emerald-600/12 dark:bg-emerald-500/15 border border-emerald-700/25 dark:border-emerald-500/35 text-[#1D6144] dark:text-emerald-300 hover:bg-emerald-600/20 text-[11px] font-semibold whitespace-nowrap cursor-pointer"
          title="Environment disclosure & twin configuration"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-studio-sage dark:bg-emerald-400" />
          <span className="hidden xl:inline">Digital Twin</span>
          <Info className="w-3 h-3 opacity-80" strokeWidth={1.5} />
        </button>

        {/* Theme Toggle (Exact title for Playwright) */}
        <button
          type="button"
          onClick={toggleTheme}
          aria-label="Toggle Light/Dark Theme"
          className="studio-btn p-1.5 rounded-full bg-[var(--studio-surface-subtle)] hover:bg-[var(--studio-surface-elevated)] border border-[var(--studio-border)] text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] cursor-pointer"
          title="Toggle Light/Dark Theme"
        >
          {theme === "dark" ? (
            <Sun className="w-3.5 h-3.5" strokeWidth={1.5} />
          ) : (
            <Moon className="w-3.5 h-3.5" strokeWidth={1.5} />
          )}
        </button>
      </div>
    </header>
  );
};
