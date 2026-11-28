import React, { useEffect, useMemo, useRef, useState } from "react";
import { TopBar } from "./components/TopBar";
import { SidebarNav } from "./components/SidebarNav";
import { OverviewDashboard } from "./components/OverviewDashboard";
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
import { AISettingsModal } from "./components/Brain/AISettingsModal";
import { ChaosControlModal } from "./components/Chaos/ChaosControlModal";
import { ExceptionsQueueDrawer } from "./components/Chaos/ExceptionsQueueDrawer";
import { AuditLogViewerModal } from "./components/Chaos/AuditLogViewerModal";
import { ReplayTimeline } from "./components/ReplayTimeline";
import { pauseSimulation, resumeSimulation, setSimulationSpeed } from "./services/api";
import { setStore, useStore, useWebSocketConnection } from "./store/useStore";
import { BarChart3, BatteryCharging, Brain, Gauge, Package, Terminal, Truck } from "lucide-react";

const VIEW_MODES: Array<"2d" | "3d" | "split"> = ["2d", "3d", "split"];

export const App: React.FC = () => {
  // Establish persistent WebSocket connection & reactive state
  useWebSocketConnection();
  const store = useStore();
  const {
    activeWorkspaceView,
    isPaused,
    leftPanelOpen,
    rightPanelOpen,
    activeRightTab,
    alerts,
    kpis,
    robots,
    orders,
    aiMode,
    brainModelName,
    brainInferenceInFlight,
    viewMode,
    isSupervisorBarOpen,
    theme,
  } = store;

  const activeAlertCount = alerts.filter((a) => !a.cleared).length;

  const liveMetrics = useMemo(() => {
    const robotList = Object.values(robots);
    const orderList = Object.values(orders);
    const totalRobots = robotList.length;
    const moving = robotList.filter((r) => String(r.state).startsWith("MOVING") || r.state === "PICKING").length;
    const charging = robotList.filter((r) => r.state === "CHARGING").length;
    const avgBattery =
      totalRobots > 0
        ? Math.round(robotList.reduce((acc, r) => acc + Number(r.battery_percent ?? 100), 0) / totalRobots)
        : 100;
    const delivered = orderList.filter((o) => o.status === "HANDED_OVER").length;
    const atRisk = orderList.filter((o) => o.at_risk).length;
    const utilPct =
      totalRobots > 0 ? Math.round((moving / totalRobots) * 100) : Math.round((kpis.fleet_utilization ?? 0) * 100);
    return {
      totalRobots,
      moving,
      charging,
      avgBattery,
      delivered: Math.max(delivered, kpis.completed_orders_total ?? 0),
      atRisk: Math.max(atRisk, kpis.at_risk_orders ?? 0),
      utilPct,
      throughput: Math.round(kpis.throughput_orders_per_hr ?? 0),
      queueDepth: kpis.queue_depth ?? 0,
    };
  }, [robots, orders, kpis]);

  // Sync html root class with store theme
  useEffect(() => {
    if (theme === "light") {
      document.documentElement.classList.remove("dark");
      document.documentElement.classList.add("light");
    } else {
      document.documentElement.classList.remove("light");
      document.documentElement.classList.add("dark");
    }
  }, [theme]);

  // Draggable Split Divider State
  const [splitRatio, setSplitRatio] = useState<number>(0.45);
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
    const applySpeed = async (multiplier: number) => {
      setStore({ speedMultiplier: multiplier });
      try {
        await setSimulationSpeed(multiplier);
      } catch (err) {
        console.error(err);
      }
    };

    const handleKeyDown = async (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        target?.isContentEditable
      ) {
        return;
      }

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setStore({ isSupervisorBarOpen: !isSupervisorBarOpen });
        return;
      }

      if (e.key === "Escape") {
        setStore({
          isEnvironmentModalOpen: false,
          isEStopModalOpen: false,
          isDecisionLogOpen: false,
          isApprovalsDrawerOpen: false,
          isSupervisorBarOpen: false,
          isAISettingsOpen: false,
          isChaosControlOpen: false,
          isExceptionsQueueOpen: false,
          isAuditLogOpen: false,
          selectedRobotId: null,
          selectedOrderId: null,
          blockModeActive: false,
        });
        return;
      }

      if (e.ctrlKey || e.metaKey || e.altKey) {
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
        await applySpeed(1.0);
      } else if (e.code === "Digit2") {
        await applySpeed(2.0);
      } else if (e.code === "Digit5") {
        await applySpeed(5.0);
      } else if (e.code === "KeyV") {
        e.preventDefault();
        const nextMode = VIEW_MODES[(VIEW_MODES.indexOf(viewMode) + 1) % VIEW_MODES.length];
        setStore({ viewMode: nextMode, activeWorkspaceView: nextMode });
      } else if (e.code === "BracketLeft") {
        setStore({ leftPanelOpen: !leftPanelOpen });
      } else if (e.code === "BracketRight") {
        setStore({ rightPanelOpen: !rightPanelOpen });
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isPaused, leftPanelOpen, rightPanelOpen, viewMode, isSupervisorBarOpen]);

  const isTwinView =
    activeWorkspaceView === "2d" ||
    activeWorkspaceView === "3d" ||
    activeWorkspaceView === "split";

  const aiLabel =
    aiMode === "baseline"
      ? "Baseline"
      : aiMode === "local_llm"
        ? `Ollama · ${brainModelName || "qwen3.5:4b"}`
        : aiMode === "ai"
          ? `Cloud AI · ${brainModelName || "ready"}`
          : "Heuristic";

  return (
    <div className="flex h-screen w-screen overflow-hidden studio-backdrop text-[var(--studio-text-primary)] font-sans">
      {/* Compact Frosted Bronze Quick-Dock Rail */}
      <SidebarNav />

      {/* Main Studio Column */}
      <div className="flex-1 min-w-0 h-full flex flex-col overflow-hidden relative">
        {/* Top Frosted Control Bar */}
        <TopBar />

        {/* Floating High-Priority Alert Banner */}
        <AlertBanner />

        {/* Compact Single-Window Live Telemetry & Quick Command Strip */}
        {isTwinView && (
          <div className="px-3 pt-2 pb-0 shrink-0 z-10 studio-enter stagger-1">
            <div className="studio-glass-bar rounded-2xl border px-3 py-1.5 flex items-center justify-between gap-3 text-[11.5px] overflow-x-auto">
              <div className="flex items-center gap-3 xl:gap-5 tabular-nums shrink-0">
                <div className="flex items-center gap-1.5" title="Fulfilment throughput per hour">
                  <Gauge className="w-3.5 h-3.5 text-studio-terracotta" strokeWidth={1.5} />
                  <span className="text-[var(--studio-text-muted)]">Throughput</span>
                  <span className="font-mono font-semibold text-[var(--studio-text-primary)]">
                    {liveMetrics.throughput} ord/hr
                  </span>
                </div>

                <span className="w-px h-3.5 bg-[var(--studio-border)]" />

                <div className="flex items-center gap-1.5" title="Queued vs delivered orders">
                  <Package className="w-3.5 h-3.5 text-[var(--studio-text-secondary)]" strokeWidth={1.5} />
                  <span className="text-[var(--studio-text-muted)]">Queue</span>
                  <span className="font-mono font-semibold text-[var(--studio-text-primary)]">
                    {liveMetrics.queueDepth}
                  </span>
                  <span className="text-[var(--studio-text-muted)]">/ {liveMetrics.delivered} done</span>
                  {liveMetrics.atRisk > 0 && (
                    <span className="px-1.5 py-0.5 rounded-md bg-amber-600/15 text-[#8F4F0D] dark:text-amber-300 font-mono text-[10px] font-semibold">
                      {liveMetrics.atRisk} at risk
                    </span>
                  )}
                </div>

                <span className="w-px h-3.5 bg-[var(--studio-border)]" />

                <div className="flex items-center gap-1.5" title="Active moving & picking AMRs">
                  <Truck className="w-3.5 h-3.5 text-[#1D6144] dark:text-emerald-400" strokeWidth={1.5} />
                  <span className="text-[var(--studio-text-muted)]">Fleet</span>
                  <span className="font-mono font-semibold text-[var(--studio-text-primary)]">
                    {liveMetrics.moving}/{liveMetrics.totalRobots}
                  </span>
                  <span className="text-[var(--studio-text-muted)]">({liveMetrics.utilPct}% util)</span>
                </div>

                <span className="hidden md:block w-px h-3.5 bg-[var(--studio-border)]" />

                <div className="hidden md:flex items-center gap-1.5" title="Fleet mean battery state of charge">
                  <BatteryCharging className="w-3.5 h-3.5 text-[#1D6144] dark:text-emerald-400" strokeWidth={1.5} />
                  <span className="text-[var(--studio-text-muted)]">Battery</span>
                  <span className="font-mono font-semibold text-[var(--studio-text-primary)]">
                    {liveMetrics.avgBattery}%
                  </span>
                  {liveMetrics.charging > 0 && (
                    <span className="text-[10.5px] font-mono text-[var(--studio-text-muted)]">
                      ({liveMetrics.charging} chg)
                    </span>
                  )}
                </div>
              </div>

              {/* Right Side Quick Studio Actions inside Main Window */}
              <div className="flex items-center gap-1.5 shrink-0">
                <button
                  type="button"
                  onClick={() => setStore({ isAISettingsOpen: true })}
                  className="studio-btn flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-[var(--studio-surface-subtle)] hover:bg-[var(--studio-surface-elevated)] border border-[var(--studio-border)] text-[11px] font-medium cursor-pointer"
                  title="Configure AI Operating Mode, Keys & Local Ollama"
                >
                  <Brain className="w-3 h-3 text-studio-terracotta" strokeWidth={1.5} />
                  <span className="font-mono">{aiLabel}</span>
                  {brainInferenceInFlight && (
                    <span className="text-[10px] text-[#B4691E] dark:text-amber-300">thinking</span>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => setStore({ isSupervisorBarOpen: true })}
                  className="studio-btn hidden xl:flex items-center gap-1 px-2.5 py-1 rounded-xl bg-[var(--studio-surface-subtle)] hover:bg-[var(--studio-surface-elevated)] border border-[var(--studio-border)] text-[11px] font-medium cursor-pointer"
                  title="Open Natural-Language Supervisor Console (Ctrl+K)"
                >
                  <Terminal className="w-3 h-3 text-[var(--studio-text-secondary)]" strokeWidth={1.5} />
                  <span>Command</span>
                  <kbd className="text-[9.5px] font-mono text-[var(--studio-text-muted)]">⌘K</kbd>
                </button>

                <button
                  type="button"
                  onClick={() => setStore({ activeWorkspaceView: "overview" })}
                  className="studio-btn hidden lg:flex items-center gap-1 px-2.5 py-1 rounded-xl bg-studio-terracotta/12 hover:bg-studio-terracotta hover:text-white border border-studio-terracotta/25 text-[#A53420] dark:text-[#FFA991] text-[11px] font-medium cursor-pointer"
                  title="Expand throughput charts and fleet breakdown view"
                >
                  <BarChart3 className="w-3 h-3" strokeWidth={1.5} />
                  <span>Charts</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Main Operations Workspace */}
        <div className="flex flex-1 overflow-hidden relative min-h-0">
          {/* Left Docked Orders Queue (Visible Directly in Twin Modes) */}
          {isTwinView && leftPanelOpen && (
            <aside className="studio-drawer-left w-64 xl:w-72 flex-shrink-0 h-full pt-2.5 pl-3 pb-2.5 flex flex-col z-20 overflow-hidden">
              <div className="w-full h-full rounded-2xl overflow-hidden border border-[var(--studio-border-strong)] studio-card flex flex-col">
                <OrderBoard />
              </div>
            </aside>
          )}

          {/* Center Canvas Area */}
          <main ref={mainRef} className="flex-1 min-w-0 h-full relative overflow-hidden flex">
            {activeWorkspaceView === "overview" && (
              <div className="w-full h-full overflow-y-auto relative studio-enter">
                <OverviewDashboard />
                <SelectedRobotPanel />
              </div>
            )}

            {isTwinView && (
              <div className="flex-1 min-w-0 h-full p-2.5 relative overflow-hidden flex">
                <div
                  className="w-full h-full rounded-2xl overflow-hidden border border-[var(--studio-border-strong)] bg-[var(--studio-canvas)] relative"
                  style={{ boxShadow: "var(--studio-shadow)" }}
                >
                  {activeWorkspaceView === "2d" && (
                    <div className="w-full h-full relative">
                      <CanvasMap />
                    </div>
                  )}

                  {activeWorkspaceView === "3d" && (
                    <div className="w-full h-full relative">
                      <Scene3D />
                    </div>
                  )}

                  {activeWorkspaceView === "split" && (
                    <div className="flex w-full h-full relative overflow-hidden">
                      <div
                        style={{ width: `${splitRatio * 100}%` }}
                        className="h-full relative overflow-hidden"
                      >
                        <CanvasMap />
                      </div>

                      {/* Draggable Divider */}
                      <div
                        role="separator"
                        tabIndex={0}
                        aria-orientation="vertical"
                        aria-label="Resize 2D and 3D split view"
                        aria-valuemin={20}
                        aria-valuemax={80}
                        aria-valuenow={Math.round(splitRatio * 100)}
                        onMouseDown={() => setIsDraggingSplit(true)}
                        onKeyDown={(e) => {
                          if (e.key === "ArrowLeft") {
                            e.preventDefault();
                            setSplitRatio((prev) => Math.max(0.2, +(prev - 0.05).toFixed(2)));
                          } else if (e.key === "ArrowRight") {
                            e.preventDefault();
                            setSplitRatio((prev) => Math.min(0.8, +(prev + 0.05).toFixed(2)));
                          }
                        }}
                        className={`w-1.5 h-full cursor-col-resize z-20 flex items-center justify-center transition-colors duration-150 select-none ${isDraggingSplit
                            ? "bg-[var(--studio-accent-solid)] shadow-md"
                            : "bg-[var(--studio-border-strong)] hover:bg-[var(--studio-accent)]"
                          }`}
                        title="Drag or use Left/Right arrows to resize 2D/3D split view"
                      >
                        <div className="w-0.5 h-8 bg-[var(--studio-text-muted)]/60 rounded-full" />
                      </div>

                      <div
                        style={{ width: `${(1 - splitRatio) * 100}%` }}
                        className="h-full relative overflow-hidden"
                      >
                        <Scene3D />
                      </div>
                    </div>
                  )}

                  <SelectedRobotPanel />
                  <ReplayTimeline />
                </div>
              </div>
            )}

            {/* Orders & SLA Focus */}
            {activeWorkspaceView === "orders" && (
              <div className="w-full h-full p-2.5 flex gap-2.5 relative overflow-hidden studio-enter">
                <div className="w-80 xl:w-96 shrink-0 h-full rounded-2xl overflow-hidden border border-[var(--studio-border-strong)] studio-card flex flex-col">
                  <OrderBoard />
                </div>
                <div className="flex-1 min-w-0 h-full rounded-2xl overflow-hidden border border-[var(--studio-border-strong)] bg-[var(--studio-canvas)] relative">
                  <CanvasMap />
                  <SelectedRobotPanel />
                </div>
              </div>
            )}

            {/* Run Replay & Historical Scrubber */}
            {activeWorkspaceView === "replay" && (
              <div className="w-full h-full p-2.5 relative overflow-hidden studio-enter">
                <div className="w-full h-full rounded-2xl overflow-hidden border border-[var(--studio-border-strong)] bg-[var(--studio-canvas)] relative">
                  {viewMode === "3d" ? <Scene3D /> : <CanvasMap />}
                  <SelectedRobotPanel />
                  <ReplayTimeline />
                </div>
              </div>
            )}
          </main>

          {/* Right Docked Alerts & Event Feed Drawer (Visible in Main Window) */}
          {rightPanelOpen && (
            <aside className="studio-drawer-right w-64 xl:w-72 flex-shrink-0 h-full pt-2.5 pr-3 pb-2.5 flex flex-col z-20 overflow-hidden">
              <div className="w-full h-full rounded-2xl overflow-hidden border border-[var(--studio-border-strong)] studio-card flex flex-col">
                <div
                  role="tablist"
                  aria-label="Activity panels"
                  className="px-2.5 pt-2.5 pb-2 border-b border-[var(--studio-border)] bg-[var(--studio-surface-subtle)] flex items-center gap-1.5 shrink-0"
                >
                  <button
                    type="button"
                    role="tab"
                    aria-selected={activeRightTab === "alerts"}
                    onClick={() => setStore({ activeRightTab: "alerts" })}
                    className={`studio-btn flex-1 py-1.5 px-2 rounded-xl font-medium text-xs flex items-center justify-center gap-1.5 cursor-pointer ${activeRightTab === "alerts"
                        ? "bg-[var(--studio-surface-elevated)] text-[var(--studio-text-primary)] shadow-sm border border-[var(--studio-border)]"
                        : "text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)]"
                      }`}
                  >
                    <span>Alerts</span>
                    <span
                      className={`px-1.5 py-0.5 rounded-full text-[10px] font-mono tabular-nums ${activeAlertCount > 0
                          ? "bg-[var(--studio-accent-solid)] text-[var(--studio-terracotta-text)] font-semibold"
                          : "bg-[var(--studio-surface)] text-[var(--studio-text-muted)] border border-[var(--studio-border)]"
                        }`}
                    >
                      {activeAlertCount}
                    </span>
                  </button>

                  <button
                    type="button"
                    role="tab"
                    aria-selected={activeRightTab === "events"}
                    onClick={() => setStore({ activeRightTab: "events" })}
                    className={`studio-btn flex-1 py-1.5 px-2 rounded-xl font-medium text-xs flex items-center justify-center gap-1.5 cursor-pointer ${activeRightTab === "events"
                        ? "bg-[var(--studio-surface-elevated)] text-[var(--studio-text-primary)] shadow-sm border border-[var(--studio-border)]"
                        : "text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)]"
                      }`}
                  >
                    <span>Events</span>
                  </button>
                </div>

                <div role="tabpanel" className="flex-1 min-h-0 overflow-hidden flex flex-col">
                  {activeRightTab === "alerts" ? <AlertDrawer /> : <EventFeed />}
                </div>
              </div>
            </aside>
          )}
        </div>
      </div>

      {/* Modals & Dialogs */}
      <EnvironmentModal />
      <ControlModals />

      {/* AI Operations Brain Overlays */}
      <DecisionLogPanel />
      <ApprovalsDrawer />
      <SupervisorCommandBar />
      <AISettingsModal />

      {/* Chaos & Resilience Studio Overlays */}
      <ChaosControlModal />
      <ExceptionsQueueDrawer />
      <AuditLogViewerModal />
    </div>
  );
};

export default App;
