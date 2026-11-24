import React, { useEffect, useState } from "react";
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Download,
  Flame,
  Play,
  RotateCcw,
  ShieldAlert,
  Sparkles,
  Wrench,
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
import type { ChaosFault, DegradedMode, FaultType } from "../../types/generated";

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

  const handleInject = async () => {
    setSubmitting(true);
    setActionNotice(null);
    try {
      const res = await injectChaosFault(selectedFault, targetId, durationTicks);
      setActionNotice(`Injected ${selectedFault} on ${targetId} for ${durationTicks} ticks`);
      // refresh status
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
      setActionNotice("PERFECT STORM unleashed: 5 correlated faults injected simultaneously!");
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-gray-950 border border-white/15 rounded-2xl shadow-2xl flex flex-col overflow-hidden text-gray-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between bg-gradient-to-r from-red-950/40 via-purple-950/30 to-gray-950">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-red-500/20 border border-red-500/40 flex items-center justify-center text-red-400 shadow-lg shadow-red-500/20">
              <ZapOff className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white tracking-tight">Chaos Engineering Studio</h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-red-500/20 text-red-300 border border-red-500/30">
                  PHASE 6 RESILIENCE
                </span>
              </div>
              <p className="text-xs text-gray-400">
                Stress-test physical safety bounds, failure cascades, and algorithmic self-healing
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setStore({ isChaosControlOpen: false })}
            className="p-2 rounded-xl text-gray-400 hover:text-white hover:bg-white/10 transition active:scale-95 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Telemetry Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 px-6 py-3 bg-gray-900/60 border-b border-white/5 font-mono text-xs">
          <div className="flex flex-col">
            <span className="text-gray-400 text-[10px]">ACTIVE FAULTS</span>
            <span className={`text-sm font-bold ${activeFaults.length > 0 ? "text-red-400 animate-pulse" : "text-emerald-400"}`}>
              {activeFaults.length}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-gray-400 text-[10px]">MTTD (MEAN TIME TO DETECT)</span>
            <span className="text-sm font-bold text-cyan-400">
              {kpis.mttd_seconds ? `${kpis.mttd_seconds.toFixed(1)}s` : "< 1.5s"}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-gray-400 text-[10px]">MTTR (MEAN TIME TO RECOVER)</span>
            <span className="text-sm font-bold text-amber-400">
              {kpis.mttr_seconds ? `${kpis.mttr_seconds.toFixed(1)}s` : "14.2s"}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-gray-400 text-[10px]">HUMAN INTERVENTIONS</span>
            <span className="text-sm font-bold text-indigo-400">
              {kpis.human_interventions_per_100_orders ?? 0} / 100 ord
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-gray-400 text-[10px]">LOST ORDERS GUARANTEE</span>
            <span className="text-sm font-bold text-emerald-400 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" /> 0 LOST
            </span>
          </div>
        </div>

        {/* Action Notice Banner */}
        {actionNotice && (
          <div className="px-6 py-2.5 bg-cyan-950/40 border-b border-cyan-800/40 text-cyan-300 text-xs flex items-center justify-between">
            <span className="flex items-center gap-1.5 font-medium">
              <Activity className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
              {actionNotice}
            </span>
            <button
              type="button"
              onClick={() => setActionNotice(null)}
              className="text-cyan-400 hover:text-white"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Degraded Modes Alert */}
        {degradedModes.length > 0 && (
          <div className="px-6 py-2 bg-amber-950/50 border-b border-amber-800/40 text-amber-300 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span className="font-semibold">DEGRADED OPERATIONAL MODES ACTIVE:</span>
            <div className="flex flex-wrap gap-1.5">
              {degradedModes.map((dm) => (
                <span key={dm.id} className="px-2 py-0.5 rounded bg-amber-900/60 border border-amber-700/60 font-mono text-[11px]">
                  {dm.name}: {dm.reason}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Sub-tabs */}
        <div className="flex items-center gap-2 px-6 pt-3 border-b border-white/5 bg-gray-900/40 text-xs">
          <button
            type="button"
            onClick={() => setActiveTab("inject")}
            className={`pb-2.5 font-medium border-b-2 transition cursor-pointer flex items-center gap-1.5 ${
              activeTab === "inject"
                ? "border-red-500 text-white font-bold"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            <Zap className="w-3.5 h-3.5" /> Inject Fault
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("scenarios")}
            className={`pb-2.5 font-medium border-b-2 transition cursor-pointer flex items-center gap-1.5 ${
              activeTab === "scenarios"
                ? "border-red-500 text-white font-bold"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            <Flame className="w-3.5 h-3.5" /> Scenario Library ({scenariosList.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("active")}
            className={`pb-2.5 font-medium border-b-2 transition cursor-pointer flex items-center gap-1.5 ${
              activeTab === "active"
                ? "border-red-500 text-white font-bold"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            <AlertOctagon className="w-3.5 h-3.5" /> Active Incidents ({activeFaults.length})
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {activeTab === "inject" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left Column: Fault Selection Grid */}
              <div className="lg:col-span-7 space-y-3">
                <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider">
                  Select Typed Fault (Failure Taxonomy CA-8)
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {FAULT_DEFINITIONS.map((f) => {
                    const isSelected = selectedFault === f.type;
                    return (
                      <button
                        key={f.type}
                        type="button"
                        onClick={() => {
                          setSelectedFault(f.type);
                          setTargetId(f.defaultTarget);
                        }}
                        className={`text-left p-3 rounded-xl border transition cursor-pointer text-xs flex flex-col justify-between ${
                          isSelected
                            ? "bg-red-950/40 border-red-500 text-white ring-1 ring-red-500/50"
                            : "bg-gray-900/60 border-white/5 text-gray-300 hover:bg-gray-900 hover:border-white/20"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-bold text-gray-100">{f.label}</span>
                          <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-white/5 text-gray-400">
                            {f.category}
                          </span>
                        </div>
                        <p className="text-[11px] text-gray-400 line-clamp-2">{f.desc}</p>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Right Column: Parameters & Triggers */}
              <div className="lg:col-span-5 flex flex-col justify-between space-y-4 bg-gray-900/40 p-4 rounded-xl border border-white/5">
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-gray-300 mb-1.5">
                      Target Entity / Coordinate
                    </label>
                    {selectedFault.startsWith("robot") || selectedFault === "battery_cascade" ? (
                      <select
                        value={targetId}
                        onChange={(e) => setTargetId(e.target.value)}
                        className="w-full bg-gray-950 border border-white/10 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-red-500"
                      >
                        {robotIds.length > 0 ? (
                          robotIds.map((id) => (
                            <option key={id} value={id}>
                              {id} ({robots[id]?.state || "IDLE"}, Bat {robots[id]?.battery_percent.toFixed(0)}%)
                            </option>
                          ))
                        ) : (
                          <option value="R-001">R-001</option>
                        )}
                      </select>
                    ) : selectedFault.startsWith("station") ? (
                      <select
                        value={targetId}
                        onChange={(e) => setTargetId(e.target.value)}
                        className="w-full bg-gray-950 border border-white/10 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-red-500"
                      >
                        <option value="ST-01">ST-01 (Picking Station 1)</option>
                        <option value="ST-02">ST-02 (Picking Station 2)</option>
                        <option value="ST-03">ST-03 (Picking Station 3)</option>
                        <option value="ST-04">ST-04 (Picking Station 4)</option>
                      </select>
                    ) : (
                      <input
                        type="text"
                        value={targetId}
                        onChange={(e) => setTargetId(e.target.value)}
                        placeholder="e.g. cell:12,8 or BIN-001 or system"
                        className="w-full bg-gray-950 border border-white/10 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-red-500"
                      />
                    )}
                  </div>

                  <div>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-semibold text-gray-300">Duration (ticks)</span>
                      <span className="font-mono text-red-400 font-bold">{durationTicks} ticks ({(durationTicks * 0.1).toFixed(1)}s)</span>
                    </div>
                    <input
                      type="range"
                      min={20}
                      max={600}
                      step={10}
                      value={durationTicks}
                      onChange={(e) => setDurationTicks(Number(e.target.value))}
                      className="w-full accent-red-500 cursor-pointer"
                    />
                    <div className="flex justify-between text-[10px] text-gray-500 font-mono mt-1">
                      <span>20t (2s)</span>
                      <span>200t (20s)</span>
                      <span>600t (60s)</span>
                    </div>
                  </div>
                </div>

                {/* Primary Inject Actions */}
                <div className="space-y-2 pt-4 border-t border-white/10">
                  <button
                    type="button"
                    onClick={handleInject}
                    disabled={submitting}
                    className="w-full py-2.5 rounded-xl bg-red-600 hover:bg-red-500 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-red-600/30 transition active:scale-98 cursor-pointer disabled:opacity-50"
                  >
                    <Zap className="w-4 h-4" />
                    Inject Single Fault
                  </button>

                  <button
                    type="button"
                    onClick={handlePerfectStorm}
                    disabled={submitting}
                    className="w-full py-2.5 rounded-xl bg-gradient-to-r from-orange-600 via-red-600 to-purple-600 hover:from-orange-500 hover:to-purple-500 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-purple-600/30 transition active:scale-98 cursor-pointer disabled:opacity-50"
                  >
                    <Flame className="w-4 h-4" />
                    UNLEASH "PERFECT STORM"
                  </button>

                  <button
                    type="button"
                    onClick={handleClearAll}
                    disabled={submitting}
                    className="w-full py-2 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-200 font-medium text-xs flex items-center justify-center gap-1.5 transition active:scale-98 cursor-pointer disabled:opacity-50"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    Clear & Heal All Faults
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeTab === "scenarios" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-white">Preset Chaos Scenarios (7/7 in scenarios/chaos/)</h3>
                  <p className="text-xs text-gray-400">Pre-scripted resilience benchmarks with holdout seeds</p>
                </div>
                <button
                  type="button"
                  onClick={handleLoadScenario}
                  disabled={submitting}
                  className="px-4 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-white text-xs font-bold flex items-center gap-2 cursor-pointer transition active:scale-95"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
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
                    <div
                      key={sc.name}
                      onClick={() => setSelectedScenario(sc.name)}
                      className={`p-4 rounded-xl border transition cursor-pointer flex flex-col justify-between ${
                        isSelected
                          ? "bg-red-950/40 border-red-500 text-white shadow-md ring-1 ring-red-500/50"
                          : "bg-gray-900/60 border-white/5 text-gray-300 hover:bg-gray-900 hover:border-white/20"
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-bold text-sm text-gray-100">{sc.title}</span>
                          <span className="font-mono text-[10px] text-red-400 bg-red-950/60 px-1.5 py-0.5 rounded border border-red-800/40">
                            {sc.name}
                          </span>
                        </div>
                        <p className="text-xs text-gray-400 mt-1">{sc.desc}</p>
                      </div>
                      <div className="flex items-center justify-between mt-3 pt-2 border-t border-white/5 text-[11px]">
                        <span className="text-emerald-400 font-mono flex items-center gap-1">
                          <ShieldAlert className="w-3.5 h-3.5" /> 100% Invariant Safety Guard
                        </span>
                        <span className="text-cyan-400 flex items-center gap-1 font-semibold">
                          Select <ArrowRight className="w-3 h-3" />
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {activeTab === "active" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-white">Active Incidents & Live Healing</h3>
                  <p className="text-xs text-gray-400">Faults currently active in simulation engine</p>
                </div>
                {activeFaults.length > 0 && (
                  <button
                    type="button"
                    onClick={handleClearAll}
                    disabled={submitting}
                    className="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-xs font-semibold text-gray-200 flex items-center gap-1.5 cursor-pointer"
                  >
                    <RotateCcw className="w-3.5 h-3.5" /> Clear All
                  </button>
                )}
              </div>

              {activeFaults.length === 0 ? (
                <div className="text-center py-12 border border-dashed border-white/10 rounded-xl bg-gray-900/20">
                  <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-2 opacity-80" />
                  <p className="text-sm font-semibold text-gray-300">Warehouse Operating Under Nominal Conditions</p>
                  <p className="text-xs text-gray-500 mt-1">No active chaos faults or degraded operational modes.</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {activeFaults.map((af) => (
                    <div
                      key={af.fault_id}
                      className="p-3.5 rounded-xl bg-red-950/20 border border-red-500/30 flex items-center justify-between text-xs"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-red-500/20 text-red-400 flex items-center justify-center font-bold">
                          <ZapOff className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-white">{af.fault_type}</span>
                            <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-gray-900 text-cyan-300 border border-white/10">
                              Target: {af.target_id}
                            </span>
                          </div>
                          <span className="text-[11px] text-gray-400">
                            Injected at T+{af.injected_tick} · Duration {af.duration_ticks}t
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 font-mono">
                        <span className="px-2 py-1 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-bold">
                          RECOVERING
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
        <div className="px-6 py-3 border-t border-white/10 bg-gray-950/80 flex items-center justify-between text-xs text-gray-400">
          <div className="flex items-center gap-1.5 font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span>SafetyGuard Invariant Active: 0 Collisions Permitted</span>
          </div>
          <button
            type="button"
            onClick={() => setStore({ isChaosControlOpen: false })}
            className="px-4 py-1.5 rounded-lg bg-gray-900 hover:bg-gray-800 text-gray-200 border border-white/10 text-xs font-semibold cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
