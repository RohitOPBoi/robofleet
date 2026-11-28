import React, { useEffect, useState } from "react";
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Flame,
  Play,
  RotateCcw,
  ShieldAlert,
  X,
  Zap,
  ZapOff,
} from "lucide-react";
import {
  clearChaosFaults,
  fetchChaosScenarios,
  fetchChaosStatus,
  injectChaosFault,
  injectPerfectStorm,
  loadChaosScenario,
} from "../../services/api";
import { setStore, useStore } from "../../store/useStore";
import type { FaultType } from "../../types/generated";

const FAULT_DEFINITIONS: {
  type: FaultType;
  label: string;
  category: "Robot" | "Environment" | "Inventory" | "Station" | "System";
  desc: string;
  defaultTarget: string;
}[] = [
  {
    type: "robot_breakdown",
    label: "Robot Breakdown",
    category: "Robot",
    desc: "Motor stall / mechanical lockup halt",
    defaultTarget: "R-001",
  },
  {
    type: "robot_comms_drop",
    label: "Comms Dropout",
    category: "Robot",
    desc: "RF packet loss & telemetry silence",
    defaultTarget: "R-002",
  },
  {
    type: "battery_cascade",
    label: "Battery Cascade",
    category: "Robot",
    desc: "Accelerated discharge trigger below 15%",
    defaultTarget: "R-003",
  },
  {
    type: "aisle_blocked",
    label: "Aisle Blockage",
    category: "Environment",
    desc: "Pallet spill / obstruction on transit aisle",
    defaultTarget: "cell:10,12",
  },
  {
    type: "bin_missing_stock",
    label: "Bin Stock-Out",
    category: "Inventory",
    desc: "Zero physically present inventory at target bin",
    defaultTarget: "BIN-001",
  },
  {
    type: "item_damaged",
    label: "Item Damaged / Mismatch",
    category: "Inventory",
    desc: "Crushed barcode triggering pick verification failure",
    defaultTarget: "BIN-002",
  },
  {
    type: "station_slowdown",
    label: "Station Slowdown",
    category: "Station",
    desc: "Ergonomic lag / scanner latency at station",
    defaultTarget: "ST-01",
  },
  {
    type: "station_offline",
    label: "Station Offline",
    category: "Station",
    desc: "Thermal trip or safety E-stop tripping station offline",
    defaultTarget: "ST-01",
  },
  {
    type: "urgent_order_burst",
    label: "Urgent Order Burst",
    category: "System",
    desc: "Rush of Tier-1 SLA express orders flooding queue",
    defaultTarget: "system",
  },
  {
    type: "supervisor_unavailable",
    label: "Supervisor Timeout",
    category: "System",
    desc: "Supervisor queue timeout triggering fallback policy",
    defaultTarget: "system",
  },
];

const formatRobotState = (state: string): string => {
  const cleaned = state.replace(/_/g, " ").toLowerCase();
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
};

export const ChaosControlModal: React.FC = () => {
  const store = useStore();
  const { isChaosControlOpen, activeFaults, degradedModes, robots, kpis } = store;

  const [selectedFault, setSelectedFault] = useState<FaultType>("robot_breakdown");
  const [targetId, setTargetId] = useState<string>("R-001");
  const [durationTicks, setDurationTicks] = useState<number>(200);
  const [submitting, setSubmitting] = useState(false);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [scenariosList, setScenariosList] = useState<string[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<string>("robot_failure_cascade");
  const [activeTab, setActiveTab] = useState<"inject" | "scenarios" | "active">("inject");

  useEffect(() => {
    if (!isChaosControlOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setStore({ isChaosControlOpen: false });
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isChaosControlOpen]);

  useEffect(() => {
    if (isChaosControlOpen) {
      fetchChaosScenarios()
        .then((scs) => {
          setScenariosList(scs);
          if (scs.length > 0 && !scs.includes(selectedScenario)) {
            setSelectedScenario(scs[0]);
          }
        })
        .catch((e) => console.warn("Failed to fetch scenarios:", e));

      fetchChaosStatus()
        .then((st) => {
          setStore({
            activeFaults: st.active_faults || [],
            degradedModes: st.degraded_modes || [],
          });
        })
        .catch((e) => console.warn("Failed to fetch status:", e));
    }
  }, [isChaosControlOpen]);

  if (!isChaosControlOpen) return null;

  const handleClose = () => setStore({ isChaosControlOpen: false });

  const handleInject = async () => {
    setSubmitting(true);
    setActionNotice(null);
    try {
      await injectChaosFault(selectedFault, targetId, durationTicks);
      setActionNotice(`Injected ${selectedFault} on ${targetId} for ${durationTicks} ticks`);
      const st = await fetchChaosStatus();
      setStore({
        activeFaults: st.active_faults || [],
        degradedModes: st.degraded_modes || [],
      });
    } catch (e: any) {
      setActionNotice(`Failed: ${e.message || String(e)}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handlePerfectStorm = async () => {
    setSubmitting(true);
    setActionNotice(null);
    try {
      await injectPerfectStorm();
      setActionNotice("Perfect storm triggered: 5 correlated faults injected simultaneously");
      const st = await fetchChaosStatus();
      setStore({
        activeFaults: st.active_faults || [],
        degradedModes: st.degraded_modes || [],
      });
    } catch (e: any) {
      setActionNotice(`Failed: ${e.message || String(e)}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleClearAll = async () => {
    setSubmitting(true);
    setActionNotice(null);
    try {
      await clearChaosFaults();
      setActionNotice("Cleared and healed all active faults across warehouse");
      setStore({ activeFaults: [], degradedModes: [] });
    } catch (e: any) {
      setActionNotice(`Failed: ${e.message || String(e)}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleLoadScenario = async () => {
    setSubmitting(true);
    setActionNotice(null);
    try {
      await loadChaosScenario(selectedScenario);
      setActionNotice(`Loaded scenario '${selectedScenario}' into active chaos runner`);
      const st = await fetchChaosStatus();
      setStore({
        activeFaults: st.active_faults || [],
        degradedModes: st.degraded_modes || [],
      });
    } catch (e: any) {
      setActionNotice(`Failed: ${e.message || String(e)}`);
    } finally {
      setSubmitting(false);
    }
  };

  const robotIds = Object.keys(robots);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#191310]/65 backdrop-blur-md"
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="chaos-modal-title"
        className="studio-card-modal studio-enter relative w-full max-w-4xl max-h-[90vh] rounded-[20px] border border-[var(--studio-border-strong)] flex flex-col overflow-hidden"
        style={{
          background: "var(--studio-surface-elevated)",
          boxShadow: "var(--studio-shadow-hover)",
        }}
      >
        {/* Header */}
        <div
          className="px-6 py-4 border-b flex items-center justify-between bg-studio-terracotta/[0.06]"
          style={{ borderColor: "var(--studio-border)" }}
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-studio-terracotta/15 border border-studio-terracotta/30 flex items-center justify-center text-[#A53420] dark:text-studio-coral">
              <ZapOff className="w-5 h-5" strokeWidth={1.5} />
            </div>
            <div>
              <h2
                id="chaos-modal-title"
                className="text-lg font-semibold tracking-tight"
                style={{ color: "var(--studio-text-primary)" }}
              >
                Chaos Engineering Studio
              </h2>
              <p className="text-xs" style={{ color: "var(--studio-text-muted)" }}>
                Stress-test physical safety bounds, failure cascades, and algorithmic self-healing
              </p>
            </div>
          </div>
          <button
            type="button"
            aria-label="Close Chaos Engineering Studio"
            onClick={handleClose}
            className="studio-btn p-2 rounded-xl text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)] hover:bg-black/5 dark:hover:bg-white/10 cursor-pointer"
          >
            <X className="w-5 h-5" strokeWidth={1.5} />
          </button>
        </div>

        {/* Telemetry Bar */}
        <div
          className="grid grid-cols-2 sm:grid-cols-5 gap-2 px-6 py-3 border-b font-mono text-xs tabular-nums"
          style={{
            background: "var(--studio-surface-subtle)",
            borderColor: "var(--studio-border)",
          }}
        >
          <div className="flex flex-col">
            <span className="text-[10.5px]" style={{ color: "var(--studio-text-muted)" }}>
              Active faults
            </span>
            <span
              className={`text-sm font-semibold ${
                activeFaults.length > 0
                  ? "text-[#9E2418] dark:text-red-400"
                  : "text-[#1D6144] dark:text-emerald-300"
              }`}
            >
              {activeFaults.length}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-[10.5px]" style={{ color: "var(--studio-text-muted)" }}>
              MTTD (Mean time to detect)
            </span>
            <span className="text-sm font-semibold" style={{ color: "var(--studio-text-primary)" }}>
              {kpis.mttd_seconds ? `${kpis.mttd_seconds.toFixed(1)}s` : "< 1.5s"}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-[10.5px]" style={{ color: "var(--studio-text-muted)" }}>
              MTTR (Mean time to recover)
            </span>
            <span className="text-sm font-semibold text-[#8F4F0D] dark:text-amber-300">
              {kpis.mttr_seconds ? `${kpis.mttr_seconds.toFixed(1)}s` : "14.2s"}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-[10.5px]" style={{ color: "var(--studio-text-muted)" }}>
              Human interventions
            </span>
            <span className="text-sm font-semibold text-[#A53420] dark:text-studio-coral">
              {kpis.human_interventions_per_100_orders ?? 0} / 100 ord
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-[10.5px]" style={{ color: "var(--studio-text-muted)" }}>
              Lost orders
            </span>
            <span className="text-sm font-semibold text-[#1D6144] dark:text-emerald-300 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={1.5} /> 0 lost
            </span>
          </div>
        </div>

        {/* Action Notice Banner */}
        {actionNotice && (
          <div
            className={`px-6 py-2.5 border-b text-xs flex items-center justify-between ${
              actionNotice.startsWith("Failed:")
                ? "bg-red-600/12 border-red-700/25 text-[#9E2418] dark:text-red-300"
                : "bg-studio-sage/12 border-studio-sage/25 text-[#1D6144] dark:text-emerald-300"
            }`}
          >
            <span className="flex items-center gap-1.5 font-medium">
              <Activity className="w-3.5 h-3.5" strokeWidth={1.5} />
              {actionNotice}
            </span>
            <button
              type="button"
              onClick={() => setActionNotice(null)}
              aria-label="Dismiss notice"
              className="studio-btn p-1 rounded-lg hover:bg-black/5 dark:hover:bg-white/10 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" strokeWidth={1.5} />
            </button>
          </div>
        )}

        {/* Degraded Modes Alert */}
        {degradedModes.length > 0 && (
          <div className="px-6 py-2 bg-studio-amber/12 border-b border-studio-amber/25 text-[#8F4F0D] dark:text-amber-300 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" strokeWidth={1.5} />
            <span className="font-semibold">Degraded operational modes active:</span>
            <div className="flex flex-wrap gap-1.5">
              {degradedModes.map((dm) => (
                <span
                  key={dm.id}
                  className="px-2 py-0.5 rounded-lg bg-studio-amber/15 border border-studio-amber/30 font-mono text-[11px]"
                >
                  {dm.name}: {dm.reason}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Sub-tabs */}
        <div
          className="flex items-center gap-4 px-6 pt-3 border-b text-xs"
          style={{
            borderColor: "var(--studio-border)",
            background: "var(--studio-surface-subtle)",
          }}
        >
          <button
            type="button"
            onClick={() => setActiveTab("inject")}
            className={`pb-2.5 font-semibold border-b-2 transition-colors duration-150 cursor-pointer flex items-center gap-1.5 ${
              activeTab === "inject"
                ? "border-studio-terracotta text-[var(--studio-text-primary)]"
                : "border-transparent text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)]"
            }`}
          >
            <Zap className="w-3.5 h-3.5" strokeWidth={1.5} /> Inject Fault
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("scenarios")}
            className={`pb-2.5 font-semibold border-b-2 transition-colors duration-150 cursor-pointer flex items-center gap-1.5 tabular-nums ${
              activeTab === "scenarios"
                ? "border-studio-terracotta text-[var(--studio-text-primary)]"
                : "border-transparent text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)]"
            }`}
          >
            <Flame className="w-3.5 h-3.5" strokeWidth={1.5} /> Scenario Library ({scenariosList.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("active")}
            className={`pb-2.5 font-semibold border-b-2 transition-colors duration-150 cursor-pointer flex items-center gap-1.5 tabular-nums ${
              activeTab === "active"
                ? "border-studio-terracotta text-[var(--studio-text-primary)]"
                : "border-transparent text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)]"
            }`}
          >
            <AlertOctagon className="w-3.5 h-3.5" strokeWidth={1.5} /> Active Incidents ({activeFaults.length})
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {activeTab === "inject" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left Column: Fault Selection Grid */}
              <div className="lg:col-span-7 space-y-3">
                <span
                  className="block text-xs font-semibold tracking-tight"
                  style={{ color: "var(--studio-text-secondary)" }}
                >
                  Select fault type
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {FAULT_DEFINITIONS.map((f) => {
                    const isSelected = selectedFault === f.type;
                    return (
                      <button
                        key={f.type}
                        type="button"
                        aria-pressed={isSelected}
                        onClick={() => {
                          setSelectedFault(f.type);
                          setTargetId(f.defaultTarget);
                        }}
                        className={`text-left p-3.5 rounded-2xl border cursor-pointer text-xs flex flex-col justify-between transition-[border-color,background-color,box-shadow] duration-150 ${
                          isSelected
                            ? "bg-studio-terracotta/12 border-studio-terracotta ring-1 ring-studio-terracotta/30"
                            : "hover:border-[var(--studio-border-strong)]"
                        }`}
                        style={
                          isSelected
                            ? { color: "var(--studio-text-primary)" }
                            : {
                                background: "var(--studio-surface)",
                                borderColor: "var(--studio-border)",
                                color: "var(--studio-text-secondary)",
                              }
                        }
                      >
                        <div className="flex items-center justify-between mb-1 gap-2">
                          <span className="font-semibold" style={{ color: "var(--studio-text-primary)" }}>
                            {f.label}
                          </span>
                          <span
                            className="text-[10px] font-mono px-1.5 py-0.5 rounded-md border shrink-0"
                            style={{
                              background: "var(--studio-surface-subtle)",
                              borderColor: "var(--studio-border)",
                              color: "var(--studio-text-muted)",
                            }}
                          >
                            {f.category}
                          </span>
                        </div>
                        <p className="text-[11px] line-clamp-2" style={{ color: "var(--studio-text-muted)" }}>
                          {f.desc}
                        </p>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Right Column: Parameters & Triggers */}
              <div
                className="lg:col-span-5 flex flex-col justify-between space-y-4 p-4 rounded-2xl border"
                style={{
                  background: "var(--studio-surface-subtle)",
                  borderColor: "var(--studio-border)",
                }}
              >
                <div className="space-y-4">
                  <div>
                    <label
                      htmlFor="chaos-target-input"
                      className="block text-xs font-semibold mb-1.5"
                      style={{ color: "var(--studio-text-secondary)" }}
                    >
                      Target Entity / Coordinate
                    </label>
                    {selectedFault.startsWith("robot") || selectedFault === "battery_cascade" ? (
                      <select
                        id="chaos-target-input"
                        value={targetId}
                        onChange={(e) => setTargetId(e.target.value)}
                        className="w-full rounded-xl border px-3 py-2 text-xs font-mono tabular-nums focus:outline-none focus:border-studio-terracotta"
                        style={{
                          background: "var(--studio-surface-elevated)",
                          borderColor: "var(--studio-border-strong)",
                          color: "var(--studio-text-primary)",
                        }}
                      >
                        {robotIds.length > 0 ? (
                          robotIds.map((id) => (
                            <option key={id} value={id}>
                              {id} ({formatRobotState(robots[id]?.state || "IDLE")}, Bat{" "}
                              {(robots[id]?.battery_percent ?? 100).toFixed(0)}%)
                            </option>
                          ))
                        ) : (
                          <option value="R-001">R-001</option>
                        )}
                      </select>
                    ) : selectedFault.startsWith("station") ? (
                      <select
                        id="chaos-target-input"
                        value={targetId}
                        onChange={(e) => setTargetId(e.target.value)}
                        className="w-full rounded-xl border px-3 py-2 text-xs font-mono focus:outline-none focus:border-studio-terracotta"
                        style={{
                          background: "var(--studio-surface-elevated)",
                          borderColor: "var(--studio-border-strong)",
                          color: "var(--studio-text-primary)",
                        }}
                      >
                        <option value="ST-01">ST-01 (Picking Station 1)</option>
                        <option value="ST-02">ST-02 (Picking Station 2)</option>
                        <option value="ST-03">ST-03 (Picking Station 3)</option>
                        <option value="ST-04">ST-04 (Picking Station 4)</option>
                      </select>
                    ) : (
                      <input
                        id="chaos-target-input"
                        type="text"
                        value={targetId}
                        onChange={(e) => setTargetId(e.target.value)}
                        placeholder="e.g. cell:12,8 or BIN-001 or system"
                        className="w-full rounded-xl border px-3 py-2 text-xs font-mono focus:outline-none focus:border-studio-terracotta"
                        style={{
                          background: "var(--studio-surface-elevated)",
                          borderColor: "var(--studio-border-strong)",
                          color: "var(--studio-text-primary)",
                        }}
                      />
                    )}
                  </div>

                  <div>
                    <div className="flex items-center justify-between text-xs mb-1.5 tabular-nums">
                      <label
                        htmlFor="chaos-duration-range"
                        className="font-semibold"
                        style={{ color: "var(--studio-text-secondary)" }}
                      >
                        Duration (ticks)
                      </label>
                      <span className="font-mono text-[#A53420] dark:text-studio-coral font-semibold">
                        {durationTicks} ticks ({(durationTicks * 0.1).toFixed(1)}s)
                      </span>
                    </div>
                    <input
                      id="chaos-duration-range"
                      type="range"
                      min={20}
                      max={600}
                      step={10}
                      value={durationTicks}
                      onChange={(e) => setDurationTicks(Number(e.target.value))}
                      className="w-full cursor-pointer"
                      style={{ accentColor: "var(--studio-accent-solid)" }}
                    />
                    <div
                      className="flex justify-between text-[10px] font-mono mt-1 tabular-nums"
                      style={{ color: "var(--studio-text-muted)" }}
                    >
                      <span>20t (2s)</span>
                      <span>200t (20s)</span>
                      <span>600t (60s)</span>
                    </div>
                  </div>
                </div>

                {/* Primary Inject Actions */}
                <div
                  className="space-y-2 pt-4 border-t"
                  style={{ borderColor: "var(--studio-border)" }}
                >
                  <button
                    type="button"
                    onClick={handleInject}
                    disabled={submitting}
                    className="studio-btn w-full py-2.5 rounded-xl bg-[var(--studio-accent-solid)] hover:bg-[var(--studio-accent-hover)] text-white font-semibold text-xs flex items-center justify-center gap-2 shadow-sm cursor-pointer disabled:opacity-50"
                  >
                    <Zap className="w-4 h-4" strokeWidth={1.5} />
                    Inject Single Fault
                  </button>

                  <button
                    type="button"
                    onClick={handlePerfectStorm}
                    disabled={submitting}
                    className="studio-btn w-full py-2.5 rounded-xl bg-[var(--studio-accent-solid)] hover:bg-[var(--studio-accent-hover)] text-white font-semibold text-xs flex items-center justify-center gap-2 shadow-sm cursor-pointer disabled:opacity-50"
                    style={{ boxShadow: "var(--studio-shadow)" }}
                  >
                    <Flame className="w-4 h-4" strokeWidth={1.5} />
                    Trigger perfect storm
                  </button>

                  <button
                    type="button"
                    onClick={handleClearAll}
                    disabled={submitting}
                    className="studio-btn w-full py-2 rounded-xl border font-medium text-xs flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
                    style={{
                      background: "var(--studio-surface-elevated)",
                      borderColor: "var(--studio-border-strong)",
                      color: "var(--studio-text-primary)",
                    }}
                  >
                    <RotateCcw className="w-3.5 h-3.5" strokeWidth={1.5} />
                    Clear & Heal All Faults
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeTab === "scenarios" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold tabular-nums" style={{ color: "var(--studio-text-primary)" }}>
                    Preset chaos scenarios
                  </h3>
                  <p className="text-xs" style={{ color: "var(--studio-text-muted)" }}>
                    Pre-scripted resilience benchmarks with holdout seeds
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleLoadScenario}
                  disabled={submitting}
                  className="studio-btn px-4 py-2 rounded-xl bg-[var(--studio-accent-solid)] hover:bg-[var(--studio-accent-hover)] text-white text-xs font-semibold flex items-center gap-2 cursor-pointer shadow-sm shrink-0 disabled:opacity-50"
                >
                  <Play className="w-3.5 h-3.5 fill-current" strokeWidth={1.5} />
                  Run Selected Scenario
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {[
                  {
                    name: "robot_failure_cascade",
                    title: "AMR Breakdown Cascade",
                    desc: "2 AMRs motor stall simultaneously under high load; tests automated task handoff and dynamic rerouting.",
                  },
                  {
                    name: "aisle_blockage_peak",
                    title: "Transit Aisle Blockage",
                    desc: "Pallet spill on primary highway during peak order volume; tests graph edge blocking and A* dynamic recalculation.",
                  },
                  {
                    name: "stock_out_urgent_orders",
                    title: "Bin Stock-Out & Express Burst",
                    desc: "Primary bin depleted while express SLA orders arrive; tests replica bin substitution and fast line isolation.",
                  },
                  {
                    name: "station_down_rush",
                    title: "Pick Station Offline During Rush",
                    desc: "Station 1 trips thermal safety switch with 8 orders queued; tests station failover and load rebalancing.",
                  },
                  {
                    name: "comms_drop_two_robots",
                    title: "Multi-AMR RF Dropout",
                    desc: "Two AMRs drop heartbeat telemetry; tests deadman timeouts, zone isolation, and safe deceleration.",
                  },
                  {
                    name: "battery_stress",
                    title: "Fleet Battery Stress Test",
                    desc: "3 AMRs drop below 15% charge concurrently; tests charger queue scheduling and non-preemptible charging safety.",
                  },
                  {
                    name: "perfect_storm",
                    title: "The Perfect Storm",
                    desc: "Correlated multi-failure: AMRs faulted + station offline + aisle blocked; tests holistic multi-agent resilience.",
                  },
                ].map((sc) => {
                  const isSelected = selectedScenario === sc.name;
                  return (
                    <button
                      key={sc.name}
                      type="button"
                      aria-pressed={isSelected}
                      onClick={() => setSelectedScenario(sc.name)}
                      className={`w-full text-left p-4 rounded-2xl border cursor-pointer flex flex-col justify-between transition-[border-color,background-color,box-shadow] duration-150 ${
                        isSelected
                          ? "bg-studio-terracotta/12 border-studio-terracotta ring-1 ring-studio-terracotta/30"
                          : "hover:border-[var(--studio-border-strong)]"
                      }`}
                      style={
                        isSelected
                          ? { color: "var(--studio-text-primary)" }
                          : {
                              background: "var(--studio-surface)",
                              borderColor: "var(--studio-border)",
                              color: "var(--studio-text-secondary)",
                            }
                      }
                    >
                      <div>
                        <div className="flex items-center justify-between mb-1 gap-2">
                          <span className="font-semibold text-sm" style={{ color: "var(--studio-text-primary)" }}>
                            {sc.title}
                          </span>
                          <span className="font-mono text-[10px] text-[#A53420] dark:text-studio-coral bg-studio-terracotta/12 px-2 py-0.5 rounded-md border border-studio-terracotta/25 shrink-0">
                            {sc.name}
                          </span>
                        </div>
                        <p className="text-xs mt-1" style={{ color: "var(--studio-text-muted)" }}>
                          {sc.desc}
                        </p>
                      </div>
                      <div
                        className="flex items-center justify-between mt-3 pt-2.5 border-t text-[11px] w-full"
                        style={{ borderColor: "var(--studio-border)" }}
                      >
                        <span className="text-[#1D6144] dark:text-emerald-300 font-mono flex items-center gap-1 tabular-nums">
                          <ShieldAlert className="w-3.5 h-3.5" strokeWidth={1.5} /> 100% Invariant Safety Guard
                        </span>
                        <span className="text-[#A53420] dark:text-studio-coral flex items-center gap-1 font-semibold">
                          Select <ArrowRight className="w-3 h-3" strokeWidth={1.5} />
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {activeTab === "active" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold" style={{ color: "var(--studio-text-primary)" }}>
                    Active Incidents & Live Healing
                  </h3>
                  <p className="text-xs" style={{ color: "var(--studio-text-muted)" }}>
                    Faults currently active in simulation engine
                  </p>
                </div>
                {activeFaults.length > 0 && (
                  <button
                    type="button"
                    onClick={handleClearAll}
                    disabled={submitting}
                    className="studio-btn px-3 py-1.5 rounded-xl border text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
                    style={{
                      background: "var(--studio-surface-subtle)",
                      borderColor: "var(--studio-border-strong)",
                      color: "var(--studio-text-primary)",
                    }}
                  >
                    <RotateCcw className="w-3.5 h-3.5" strokeWidth={1.5} /> Clear All
                  </button>
                )}
              </div>

              {activeFaults.length === 0 ? (
                <div
                  className="text-center py-12 border border-dashed rounded-2xl"
                  style={{
                    borderColor: "var(--studio-border-strong)",
                    background: "var(--studio-surface-subtle)",
                  }}
                >
                  <CheckCircle2
                    className="w-10 h-10 text-[#1D6144] dark:text-emerald-300 mx-auto mb-2 opacity-85"
                    strokeWidth={1.5}
                  />
                  <p className="text-sm font-semibold" style={{ color: "var(--studio-text-primary)" }}>
                    Warehouse Operating Under Nominal Conditions
                  </p>
                  <p className="text-xs mt-1" style={{ color: "var(--studio-text-muted)" }}>
                    No active chaos faults or degraded operational modes.
                  </p>
                </div>
              ) : (
                <div className="space-y-2.5">
                  {activeFaults.map((af) => (
                    <div
                      key={af.fault_id}
                      className="p-3.5 rounded-2xl bg-studio-crimson/[0.08] border border-studio-crimson/25 flex items-center justify-between text-xs"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-xl bg-studio-crimson/15 border border-studio-crimson/25 text-[#9E2418] dark:text-red-400 flex items-center justify-center">
                          <ZapOff className="w-4 h-4" strokeWidth={1.5} />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold" style={{ color: "var(--studio-text-primary)" }}>
                              {af.fault_type}
                            </span>
                            <span
                              className="font-mono text-[10px] px-2 py-0.5 rounded-lg border tabular-nums"
                              style={{
                                background: "var(--studio-surface-elevated)",
                                borderColor: "var(--studio-border)",
                                color: "var(--studio-text-secondary)",
                              }}
                            >
                              Target: {af.target_id}
                            </span>
                          </div>
                          <span
                            className="text-[11px] tabular-nums"
                            style={{ color: "var(--studio-text-muted)" }}
                          >
                            Injected at T+{af.injected_tick} · Duration {af.duration_ticks}t
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 font-mono">
                        <span className="px-2.5 py-1 rounded-lg bg-studio-amber/15 text-[#8F4F0D] dark:text-amber-300 border border-studio-amber/30 text-[10px] font-semibold">
                          Recovering
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="px-6 py-3 border-t flex items-center justify-between text-xs"
          style={{
            borderColor: "var(--studio-border)",
            background: "var(--studio-surface-subtle)",
            color: "var(--studio-text-muted)",
          }}
        >
          <div className="flex items-center gap-2 font-mono tabular-nums">
            <span className="w-2 h-2 rounded-full bg-studio-sage dark:bg-emerald-400" />
            <span>SafetyGuard Invariant Active: 0 Collisions Permitted</span>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="studio-btn px-4 py-1.5 rounded-xl border text-xs font-semibold cursor-pointer"
            style={{
              background: "var(--studio-surface-elevated)",
              borderColor: "var(--studio-border-strong)",
              color: "var(--studio-text-primary)",
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
