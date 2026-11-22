import React, { useEffect, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle,
  Clock,
  ExternalLink,
  Flame,
  Layers,
  Package,
  RefreshCw,
  Sparkles,
  Truck,
  UserCheck,
  Wrench,
  X,
  XCircle,
} from "lucide-react";
import {
  approveReslotRecommendation,
  fetchExceptions,
  fetchReslotRecommendations,
  resolveException,
} from "../../services/api";
import { setStore, useStore } from "../../store/useStore";
import type { ExceptionItem, ReslotRecommendation } from "../../types/generated";

export const ExceptionsQueueDrawer: React.FC = () => {
  const store = useStore();
  const { isExceptionsQueueOpen, pendingExceptions, reslotRecommendations, kpis, tick } = store;

  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"exceptions" | "reslot">("exceptions");
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const refreshData = async () => {
    setLoading(true);
    try {
      const [exRes, reslotRes] = await Promise.all([
        fetchExceptions(),
        fetchReslotRecommendations(),
      ]);
      setStore({
        pendingExceptions: exRes.pending_exceptions || [],
        reslotRecommendations: reslotRes || [],
      });
    } catch (e) {
      console.warn("Failed to refresh exceptions:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isExceptionsQueueOpen) {
      refreshData();
    }
  }, [isExceptionsQueueOpen]);

  if (!isExceptionsQueueOpen) return null;

  const handleResolve = async (
    exceptionId: string,
    action: string,
    reason: string = "Supervisor manual decision"
  ) => {
    setActionNotice(null);
    try {
      await resolveException(exceptionId, action, "supervisor", "supervisor", reason);
      setActionNotice(`Resolved ${exceptionId} with action: ${action}`);
      await refreshData();
    } catch (e: any) {
      setActionNotice(`Failed to resolve: ${e.message || String(e)}`);
    }
  };

  const handleApproveReslot = async (recommendationId: string) => {
    setActionNotice(null);
    try {
      await approveReslotRecommendation(recommendationId, "supervisor", "supervisor");
      setActionNotice(`Approved reslotting plan ${recommendationId}`);
      await refreshData();
    } catch (e: any) {
      setActionNotice(`Failed to approve: ${e.message || String(e)}`);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-full max-w-xl h-full bg-gray-950 border-l border-white/10 shadow-2xl flex flex-col text-gray-200 animate-in slide-in-from-right duration-300">
        {/* Header */}
        <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between bg-gradient-to-r from-amber-950/40 via-gray-900 to-gray-950">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
              <UserCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white tracking-tight">Supervisor Exceptions Queue</h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  {pendingExceptions.length} PENDING
                </span>
              </div>
              <p className="text-[11px] text-gray-400">
                Audited human-in-the-loop escalation ledger & dynamic re-slotting approvals
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={refreshData}
              disabled={loading}
              className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition cursor-pointer"
              title="Refresh Queue"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
            <button
              type="button"
              onClick={() => setStore({ isExceptionsQueueOpen: false })}
              className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Resilience KPI Pill */}
        <div className="grid grid-cols-2 gap-2 px-6 py-2.5 bg-gray-900/60 border-b border-white/5 font-mono text-xs">
          <div>
            <span className="text-[10px] text-gray-400 block">HUMAN INTERVENTIONS</span>
            <span className="text-sm font-bold text-amber-400">
              {kpis.human_interventions_per_100_orders ?? 0} / 100 orders
            </span>
          </div>
          <div>
            <span className="text-[10px] text-gray-400 block">SLA STRICTNESS</span>
            <span className="text-sm font-bold text-emerald-400">
              Auto-Fallback on Timeout
            </span>
          </div>
        </div>

        {/* Action Notice */}
        {actionNotice && (
          <div className="px-6 py-2 bg-cyan-950/40 border-b border-cyan-800/40 text-cyan-300 text-xs flex items-center justify-between">
            <span>{actionNotice}</span>
            <button
              type="button"
              onClick={() => setActionNotice(null)}
              className="text-cyan-400 hover:text-white"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Tabs */}
        <div className="flex items-center gap-4 px-6 pt-3 border-b border-white/5 bg-gray-900/40 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setActiveTab("exceptions")}
            className={`pb-2.5 border-b-2 flex items-center gap-1.5 transition cursor-pointer ${
              activeTab === "exceptions"
                ? "border-amber-500 text-white"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
            Exceptions Queue ({pendingExceptions.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("reslot")}
            className={`pb-2.5 border-b-2 flex items-center gap-1.5 transition cursor-pointer ${
              activeTab === "reslot"
                ? "border-cyan-500 text-white"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-cyan-400" />
            Re-Slotting Recommendations ({reslotRecommendations.length})
          </button>
        </div>

        {/* Drawer Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {activeTab === "exceptions" && (
            <div className="space-y-3">
              {pendingExceptions.length === 0 ? (
                <div className="text-center py-16 border border-dashed border-white/10 rounded-xl bg-gray-900/20">
                  <CheckCircle className="w-10 h-10 text-emerald-400 mx-auto mb-2 opacity-80" />
                  <p className="text-sm font-semibold text-gray-300">All Exceptions Resolved</p>
                  <p className="text-xs text-gray-500 mt-1">Autonomous self-healing has handled all active operational alerts.</p>
                </div>
              ) : (
                pendingExceptions.map((rawEx: any) => {
                  const exId = rawEx.id || rawEx.exception_id || "EXC-01";
                  const deadlineTick = rawEx.sla_deadline_tick ?? rawEx.deadline_tick ?? 1000;
                  const ticksRemaining = Math.max(0, deadlineTick - tick);
                  const priorityNum = rawEx.priority ?? (rawEx.severity === "CRITICAL" ? 4 : rawEx.severity === "HIGH" ? 3 : 2);
                  const isCritical = priorityNum >= 3 || ticksRemaining < 50;
                  const desc = rawEx.description || `Exception on ${rawEx.entity_id || "item"}: ${rawEx.exception_type || "operational_fault"}`;
                  const actionSuggested = rawEx.suggested_action || rawEx.recommended_action || rawEx.default_action || "Autonomous reassignment";
                  const orderId = rawEx.order_id || (String(rawEx.entity_id).startsWith("ORD") ? rawEx.entity_id : null);
                  const robotId = rawEx.robot_id || (String(rawEx.entity_id).startsWith("R-") ? rawEx.entity_id : null);

                  return (
                    <div
                      key={exId}
                      className="p-4 rounded-xl bg-gray-900/80 border border-white/10 shadow-sm space-y-3 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                              isCritical
                                ? "bg-red-500/20 text-red-300 border border-red-500/30 animate-pulse"
                                : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                            }`}
                          >
                            P{priorityNum} {isCritical ? "CRITICAL" : "URGENT"}
                          </span>
                          <span className="font-mono text-gray-400 text-[11px]">{exId}</span>
                        </div>
                        <div className="flex items-center gap-1 font-mono text-[11px] text-gray-400">
                          <Clock className="w-3.5 h-3.5 text-amber-400" />
                          <span>Timeout: {ticksRemaining}t</span>
                        </div>
                      </div>

                      <div>
                        <p className="text-gray-100 font-semibold">{desc}</p>
                        {(orderId || robotId) && (
                          <div className="flex items-center gap-3 mt-1 text-[11px] font-mono text-cyan-400">
                            {orderId && <span>Order: {orderId}</span>}
                            {robotId && <span>Robot: {robotId}</span>}
                            {rawEx.station_id && <span>Station: {rawEx.station_id}</span>}
                          </div>
                        )}
                      </div>

                      <div className="p-2.5 rounded-lg bg-gray-950/80 border border-white/5 text-[11px]">
                        <span className="text-gray-400 block mb-0.5 font-semibold">Suggested Action:</span>
                        <span className="text-gray-200 font-mono">{actionSuggested}</span>
                      </div>

                      {/* Supervisor Decision Triggers */}
                      <div className="pt-2 border-t border-white/5 flex flex-wrap gap-1.5">
                        <button
                          type="button"
                          onClick={() => handleResolve(exId, "approve_partial")}
                          className="px-2.5 py-1.5 rounded-lg bg-emerald-600/30 hover:bg-emerald-600/50 text-emerald-300 border border-emerald-500/40 text-[11px] font-semibold transition active:scale-95 cursor-pointer"
                        >
                          Approve Partial
                        </button>
                        <button
                          type="button"
                          onClick={() => handleResolve(exId, "extend_sla_300t")}
                          className="px-2.5 py-1.5 rounded-lg bg-cyan-600/30 hover:bg-cyan-600/50 text-cyan-300 border border-cyan-500/40 text-[11px] font-semibold transition active:scale-95 cursor-pointer"
                        >
                          Delay 300t
                        </button>
                        <button
                          type="button"
                          onClick={() => handleResolve(exId, "cancel_line")}
                          className="px-2.5 py-1.5 rounded-lg bg-red-600/30 hover:bg-red-600/50 text-red-300 border border-red-500/40 text-[11px] font-semibold transition active:scale-95 cursor-pointer"
                        >
                          Cancel Line
                        </button>
                        <button
                          type="button"
                          onClick={() => handleResolve(exId, "dispatch_manual_runner")}
                          className="px-2.5 py-1.5 rounded-lg bg-purple-600/30 hover:bg-purple-600/50 text-purple-300 border border-purple-500/40 text-[11px] font-semibold transition active:scale-95 cursor-pointer"
                        >
                          Dispatch Runner
                        </button>
                        <button
                          type="button"
                          onClick={() => handleResolve(exId, "tow_amr")}
                          className="px-2.5 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 text-[11px] font-semibold transition active:scale-95 cursor-pointer"
                        >
                          Tow AMR
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}

          {activeTab === "reslot" && (
            <div className="space-y-3">
              {reslotRecommendations.length === 0 ? (
                <div className="text-center py-16 border border-dashed border-white/10 rounded-xl bg-gray-900/20">
                  <Layers className="w-10 h-10 text-cyan-400 mx-auto mb-2 opacity-80" />
                  <p className="text-sm font-semibold text-gray-300">Slots Optimized</p>
                  <p className="text-xs text-gray-500 mt-1">No pending re-slotting recommendations. SKUs match velocity profiles.</p>
                </div>
              ) : (
                reslotRecommendations.map((rawRec: any) => {
                  const recId = rawRec.id || rawRec.recommendation_id || "REC-01";
                  const skuName = rawRec.sku_name || rawRec.sku_id || "SKU Item";
                  const distSaved = Number(rawRec.distance_saved_m ?? rawRec.travel_distance_reduction ?? 0);
                  const currentBin = rawRec.current_bin_id || "BIN-A";
                  const recBin = rawRec.recommended_bin_id || "BIN-B";
                  const rationale = rawRec.rationale || "Relocate high-velocity item closer to pick stations to reduce AMR travel time.";

                  return (
                    <div
                      key={recId}
                      className="p-4 rounded-xl bg-gray-900/80 border border-white/10 shadow-sm space-y-3 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-white text-sm">{skuName}</span>
                          <span className="font-mono text-gray-400 text-[11px]">({rawRec.sku_id})</span>
                        </div>
                        <span className="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 font-mono text-[10px] font-bold">
                          Save {distSaved.toFixed(1)}m/pick
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-2 p-2.5 rounded-lg bg-gray-950/80 border border-white/5 font-mono text-[11px]">
                        <div>
                          <span className="text-gray-500 block">CURRENT BIN</span>
                          <span className="text-amber-400 font-bold">{currentBin}</span>
                        </div>
                        <div>
                          <span className="text-gray-500 block">RECOMMENDED BIN</span>
                          <span className="text-emerald-400 font-bold">{recBin}</span>
                        </div>
                      </div>

                      <p className="text-gray-300 text-[11px]">{rationale}</p>

                      <div className="pt-2 border-t border-white/5 flex items-center justify-between">
                        <span className="text-[10px] text-gray-500 font-mono">
                          Requires human supervisor sign-off
                        </span>
                        <button
                          type="button"
                          onClick={() => handleApproveReslot(recId)}
                          className="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs flex items-center gap-1.5 transition active:scale-95 cursor-pointer shadow-md shadow-cyan-600/30"
                        >
                          <Check className="w-3.5 h-3.5" />
                          Approve Re-Slot Move
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-white/10 bg-gray-950/80 flex items-center justify-between text-xs text-gray-400">
          <span className="font-mono text-[10px]">
            Every action appended immutably to runs/audit.db
          </span>
          <button
            type="button"
            onClick={() => setStore({ isExceptionsQueueOpen: false })}
            className="px-4 py-1.5 rounded-lg bg-gray-900 hover:bg-gray-800 text-gray-200 border border-white/10 text-xs font-semibold cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
