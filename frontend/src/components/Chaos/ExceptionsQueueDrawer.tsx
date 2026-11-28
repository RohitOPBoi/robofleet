import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle,
  Clock,
  Layers,
  Loader2,
  RefreshCw,
  UserCheck,
  X,
} from "lucide-react";
import {
  approveReslotRecommendation,
  fetchExceptions,
  fetchReslotRecommendations,
  resolveException,
} from "../../services/api";
import { setStore, useStore } from "../../store/useStore";

export const ExceptionsQueueDrawer: React.FC = () => {
  const store = useStore();
  const { isExceptionsQueueOpen, pendingExceptions, reslotRecommendations, kpis, tick } = store;

  const [loading, setLoading] = useState(false);
  const [submittingKey, setSubmittingKey] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"exceptions" | "reslot">("exceptions");
  const [actionNotice, setActionNotice] = useState<{ type: "success" | "error"; text: string } | null>(null);

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
    } catch (e: any) {
      setActionNotice({
        type: "error",
        text: `Failed to refresh exceptions: ${e?.message || String(e)}`,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!isExceptionsQueueOpen) return;
    refreshData();
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setStore({ isExceptionsQueueOpen: false });
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isExceptionsQueueOpen]);

  if (!isExceptionsQueueOpen) return null;

  const handleClose = () => setStore({ isExceptionsQueueOpen: false });

  const handleResolve = async (
    exceptionId: string,
    action: string,
    reason: string = "Supervisor manual decision"
  ) => {
    const key = `${exceptionId}:${action}`;
    setSubmittingKey(key);
    setActionNotice(null);
    try {
      await resolveException(exceptionId, action, "supervisor", "supervisor", reason);
      setActionNotice({ type: "success", text: `Resolved ${exceptionId} with action: ${action}` });
      await refreshData();
    } catch (e: any) {
      setActionNotice({ type: "error", text: `Failed to resolve: ${e.message || String(e)}` });
    } finally {
      setSubmittingKey(null);
    }
  };

  const handleApproveReslot = async (recommendationId: string) => {
    const key = `reslot:${recommendationId}`;
    setSubmittingKey(key);
    setActionNotice(null);
    try {
      await approveReslotRecommendation(recommendationId, "supervisor", "supervisor");
      setActionNotice({ type: "success", text: `Approved reslotting plan ${recommendationId}` });
      await refreshData();
    } catch (e: any) {
      setActionNotice({ type: "error", text: `Failed to approve: ${e.message || String(e)}` });
    } finally {
      setSubmittingKey(null);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-[#191310]/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="exceptions-drawer-title"
        className="studio-card-modal studio-drawer-enter w-full max-w-xl h-full rounded-l-[20px] border border-[var(--studio-border-strong)] flex flex-col overflow-hidden"
        style={{
          background: "var(--studio-surface-elevated)",
          borderRight: "none",
          boxShadow: "var(--studio-shadow-hover)",
        }}
      >
        {/* Header */}
        <div
          className="px-6 py-4 border-b flex items-center justify-between bg-studio-amber/[0.06]"
          style={{ borderColor: "var(--studio-border)" }}
        >
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-studio-amber/15 border border-studio-amber/30 flex items-center justify-center text-[#8F4F0D] dark:text-amber-300">
              <UserCheck className="w-5 h-5" strokeWidth={1.5} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2
                  id="exceptions-drawer-title"
                  className="text-base font-semibold tracking-tight"
                  style={{ color: "var(--studio-text-primary)" }}
                >
                  Supervisor Exceptions Queue
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-studio-amber/15 text-[#8F4F0D] dark:text-amber-300 border border-studio-amber/30 tabular-nums">
                  {pendingExceptions.length} pending
                </span>
              </div>
              <p className="text-[11px]" style={{ color: "var(--studio-text-muted)" }}>
                Audited human-in-the-loop escalation ledger & dynamic re-slotting approvals
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={refreshData}
              disabled={loading}
              aria-label="Refresh exceptions queue"
              className="studio-btn p-2 rounded-xl text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)] hover:bg-black/5 dark:hover:bg-white/10 cursor-pointer"
              title="Refresh Queue"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} strokeWidth={1.5} />
            </button>
            <button
              type="button"
              aria-label="Close exceptions queue"
              onClick={handleClose}
              className="studio-btn p-2 rounded-xl text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)] hover:bg-black/5 dark:hover:bg-white/10 cursor-pointer"
            >
              <X className="w-5 h-5" strokeWidth={1.5} />
            </button>
          </div>
        </div>

        {/* Resilience KPI Pill */}
        <div
          className="grid grid-cols-2 gap-2 px-6 py-2.5 border-b font-mono text-xs tabular-nums"
          style={{
            background: "var(--studio-surface-subtle)",
            borderColor: "var(--studio-border)",
          }}
        >
          <div>
            <span className="text-[10.5px] block" style={{ color: "var(--studio-text-muted)" }}>
              Human interventions
            </span>
            <span className="text-sm font-semibold text-[#8F4F0D] dark:text-amber-300">
              {kpis.human_interventions_per_100_orders ?? 0} / 100 orders
            </span>
          </div>
          <div>
            <span className="text-[10.5px] block" style={{ color: "var(--studio-text-muted)" }}>
              SLA policy
            </span>
            <span className="text-sm font-semibold text-[#1D6144] dark:text-emerald-300">
              Auto-Fallback on Timeout
            </span>
          </div>
        </div>

        {/* Action Notice */}
        {actionNotice && (
          <div
            className={`px-6 py-2 border-b text-xs flex items-center justify-between ${
              actionNotice.type === "error"
                ? "bg-red-600/12 border-red-700/25 text-[#9E2418] dark:text-red-300"
                : "bg-studio-sage/12 border-studio-sage/25 text-[#1D6144] dark:text-emerald-300"
            }`}
          >
            <span className="font-medium">{actionNotice.text}</span>
            <button
              type="button"
              aria-label="Dismiss notice"
              onClick={() => setActionNotice(null)}
              className="studio-btn p-1 rounded-lg hover:bg-black/5 dark:hover:bg-white/10 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" strokeWidth={1.5} />
            </button>
          </div>
        )}

        {/* Tabs */}
        <div
          className="flex items-center gap-5 px-6 pt-3 border-b text-xs font-semibold"
          style={{
            borderColor: "var(--studio-border)",
            background: "var(--studio-surface-subtle)",
          }}
        >
          <button
            type="button"
            onClick={() => setActiveTab("exceptions")}
            className={`pb-2.5 border-b-2 flex items-center gap-1.5 transition-colors duration-150 cursor-pointer tabular-nums ${
              activeTab === "exceptions"
                ? "border-studio-amber text-[var(--studio-text-primary)]"
                : "border-transparent text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)]"
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5 text-[#8F4F0D] dark:text-amber-300" strokeWidth={1.5} />
            Exceptions Queue ({pendingExceptions.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("reslot")}
            className={`pb-2.5 border-b-2 flex items-center gap-1.5 transition-colors duration-150 cursor-pointer tabular-nums ${
              activeTab === "reslot"
                ? "border-studio-terracotta text-[var(--studio-text-primary)]"
                : "border-transparent text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)]"
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-[#A53420] dark:text-studio-coral" strokeWidth={1.5} />
            Re-Slotting Recommendations ({reslotRecommendations.length})
          </button>
        </div>

        {/* Drawer Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {activeTab === "exceptions" && (
            <div className="space-y-3">
              {pendingExceptions.length === 0 ? (
                <div
                  className="text-center py-16 border border-dashed rounded-2xl"
                  style={{
                    borderColor: "var(--studio-border-strong)",
                    background: "var(--studio-surface-subtle)",
                  }}
                >
                  <CheckCircle
                    className="w-10 h-10 text-[#1D6144] dark:text-emerald-300 mx-auto mb-2 opacity-85"
                    strokeWidth={1.5}
                  />
                  <p className="text-sm font-semibold" style={{ color: "var(--studio-text-primary)" }}>
                    All Exceptions Resolved
                  </p>
                  <p className="text-xs mt-1" style={{ color: "var(--studio-text-muted)" }}>
                    Autonomous self-healing has handled all active operational alerts.
                  </p>
                </div>
              ) : (
                pendingExceptions.map((rawEx: any) => {
                  const exId = rawEx.id || rawEx.exception_id || "EXC-01";
                  const deadlineTick = rawEx.sla_deadline_tick ?? rawEx.deadline_tick ?? 1000;
                  const ticksRemaining = Math.max(0, deadlineTick - tick);
                  const priorityNum =
                    rawEx.priority ?? (rawEx.severity === "CRITICAL" ? 4 : rawEx.severity === "HIGH" ? 3 : 2);
                  const isCritical = priorityNum >= 3 || ticksRemaining < 50;
                  const desc =
                    rawEx.description ||
                    `Exception on ${rawEx.entity_id || "item"}: ${rawEx.exception_type || "operational_fault"}`;
                  const actionSuggested =
                    rawEx.suggested_action ||
                    rawEx.recommended_action ||
                    rawEx.default_action ||
                    "Autonomous reassignment";
                  const orderId = rawEx.order_id || (String(rawEx.entity_id).startsWith("ORD") ? rawEx.entity_id : null);
                  const robotId = rawEx.robot_id || (String(rawEx.entity_id).startsWith("R-") ? rawEx.entity_id : null);
                  const isExSubmitting = submittingKey?.startsWith(`${exId}:`) ?? false;

                  return (
                    <div
                      key={exId}
                      className="p-4 rounded-2xl border space-y-3 text-xs"
                      style={{
                        background: "var(--studio-surface)",
                        borderColor: "var(--studio-border)",
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 tabular-nums">
                          <span
                            className={`px-2 py-0.5 rounded-md text-[10px] font-mono font-semibold border ${
                              isCritical
                                ? "bg-studio-crimson/15 text-[#9E2418] dark:text-red-300 border-studio-crimson/30"
                                : "bg-studio-amber/15 text-[#8F4F0D] dark:text-amber-300 border-studio-amber/30"
                            }`}
                          >
                            P{priorityNum} {isCritical ? "Critical" : "Urgent"}
                          </span>
                          <span
                            className="font-mono text-[11px]"
                            style={{ color: "var(--studio-text-muted)" }}
                          >
                            {exId}
                          </span>
                        </div>
                        <div
                          className="flex items-center gap-1 font-mono text-[11px] tabular-nums"
                          style={{ color: "var(--studio-text-muted)" }}
                        >
                          <Clock className="w-3.5 h-3.5 text-[#8F4F0D] dark:text-amber-300" strokeWidth={1.5} />
                          <span>Timeout: {ticksRemaining}t</span>
                        </div>
                      </div>

                      <div>
                        <p className="font-semibold" style={{ color: "var(--studio-text-primary)" }}>
                          {desc}
                        </p>
                        {(orderId || robotId) && (
                          <div className="flex items-center gap-3 mt-1 text-[11px] font-mono text-[#A53420] dark:text-studio-coral tabular-nums">
                            {orderId && <span>Order: {orderId}</span>}
                            {robotId && <span>Robot: {robotId}</span>}
                            {rawEx.station_id && <span>Station: {rawEx.station_id}</span>}
                          </div>
                        )}
                      </div>

                      <div
                        className="p-3 rounded-xl border text-[11px]"
                        style={{
                          background: "var(--studio-surface-subtle)",
                          borderColor: "var(--studio-border)",
                        }}
                      >
                        <span
                          className="block mb-0.5 font-semibold"
                          style={{ color: "var(--studio-text-muted)" }}
                        >
                          Suggested Action:
                        </span>
                        <span
                          className="font-mono"
                          style={{ color: "var(--studio-text-primary)" }}
                        >
                          {actionSuggested}
                        </span>
                      </div>

                      {/* Supervisor Decision Triggers */}
                      <div
                        className="pt-2.5 border-t flex flex-wrap gap-1.5"
                        style={{ borderColor: "var(--studio-border)" }}
                      >
                        <button
                          type="button"
                          disabled={isExSubmitting}
                          onClick={() => handleResolve(exId, "approve_partial")}
                          className="studio-btn px-2.5 py-1.5 rounded-lg bg-studio-sage/15 hover:bg-studio-sage/25 text-[#1D6144] dark:text-emerald-300 border border-studio-sage/30 text-[11px] font-semibold cursor-pointer inline-flex items-center gap-1 disabled:opacity-50"
                        >
                          {submittingKey === `${exId}:approve_partial` && (
                            <Loader2 className="w-3 h-3 animate-spin" strokeWidth={1.5} />
                          )}
                          Approve Partial
                        </button>
                        <button
                          type="button"
                          disabled={isExSubmitting}
                          onClick={() => handleResolve(exId, "extend_sla_300t")}
                          className="studio-btn px-2.5 py-1.5 rounded-lg bg-studio-amber/15 hover:bg-studio-amber/25 text-[#8F4F0D] dark:text-amber-300 border border-studio-amber/30 text-[11px] font-semibold cursor-pointer tabular-nums inline-flex items-center gap-1 disabled:opacity-50"
                        >
                          {submittingKey === `${exId}:extend_sla_300t` && (
                            <Loader2 className="w-3 h-3 animate-spin" strokeWidth={1.5} />
                          )}
                          Delay 300t
                        </button>
                        <button
                          type="button"
                          disabled={isExSubmitting}
                          onClick={() => handleResolve(exId, "cancel_line")}
                          className="studio-btn px-2.5 py-1.5 rounded-lg bg-studio-crimson/15 hover:bg-studio-crimson/25 text-[#9E2418] dark:text-red-300 border border-studio-crimson/30 text-[11px] font-semibold cursor-pointer inline-flex items-center gap-1 disabled:opacity-50"
                        >
                          {submittingKey === `${exId}:cancel_line` && (
                            <Loader2 className="w-3 h-3 animate-spin" strokeWidth={1.5} />
                          )}
                          Cancel Line
                        </button>
                        <button
                          type="button"
                          disabled={isExSubmitting}
                          onClick={() => handleResolve(exId, "dispatch_manual_runner")}
                          className="studio-btn px-2.5 py-1.5 rounded-lg bg-studio-terracotta/15 hover:bg-studio-terracotta/25 text-[#A53420] dark:text-studio-coral border border-studio-terracotta/30 text-[11px] font-semibold cursor-pointer inline-flex items-center gap-1 disabled:opacity-50"
                        >
                          {submittingKey === `${exId}:dispatch_manual_runner` && (
                            <Loader2 className="w-3 h-3 animate-spin" strokeWidth={1.5} />
                          )}
                          Dispatch Runner
                        </button>
                        <button
                          type="button"
                          disabled={isExSubmitting}
                          onClick={() => handleResolve(exId, "tow_amr")}
                          className="studio-btn px-2.5 py-1.5 rounded-lg border text-[11px] font-semibold cursor-pointer inline-flex items-center gap-1 disabled:opacity-50"
                          style={{
                            background: "var(--studio-surface-subtle)",
                            borderColor: "var(--studio-border-strong)",
                            color: "var(--studio-text-primary)",
                          }}
                        >
                          {submittingKey === `${exId}:tow_amr` && (
                            <Loader2 className="w-3 h-3 animate-spin" strokeWidth={1.5} />
                          )}
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
                <div
                  className="text-center py-16 border border-dashed rounded-2xl"
                  style={{
                    borderColor: "var(--studio-border-strong)",
                    background: "var(--studio-surface-subtle)",
                  }}
                >
                  <Layers
                    className="w-10 h-10 text-[#A53420] dark:text-studio-coral mx-auto mb-2 opacity-85"
                    strokeWidth={1.5}
                  />
                  <p className="text-sm font-semibold" style={{ color: "var(--studio-text-primary)" }}>
                    Slots Optimized
                  </p>
                  <p className="text-xs mt-1" style={{ color: "var(--studio-text-muted)" }}>
                    No pending re-slotting recommendations. SKUs match velocity profiles.
                  </p>
                </div>
              ) : (
                reslotRecommendations.map((rawRec: any) => {
                  const recId = rawRec.id || rawRec.recommendation_id || "REC-01";
                  const skuName = rawRec.sku_name || rawRec.sku_id || "SKU Item";
                  const distSaved = Number(rawRec.distance_saved_m ?? rawRec.travel_distance_reduction ?? 0);
                  const currentBin = rawRec.current_bin_id || "BIN-A";
                  const recBin = rawRec.recommended_bin_id || "BIN-B";
                  const rationale =
                    rawRec.rationale ||
                    "Relocate high-velocity item closer to pick stations to reduce AMR travel time.";
                  const isApproving = submittingKey === `reslot:${recId}`;

                  return (
                    <div
                      key={recId}
                      className="p-4 rounded-2xl border space-y-3 text-xs"
                      style={{
                        background: "var(--studio-surface)",
                        borderColor: "var(--studio-border)",
                      }}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span
                            className="font-semibold text-sm truncate"
                            style={{ color: "var(--studio-text-primary)" }}
                          >
                            {skuName}
                          </span>
                          <span
                            className="font-mono text-[11px] shrink-0"
                            style={{ color: "var(--studio-text-muted)" }}
                          >
                            ({rawRec.sku_id})
                          </span>
                        </div>
                        <span className="px-2 py-0.5 rounded-md bg-studio-sage/15 text-[#1D6144] dark:text-emerald-300 border border-studio-sage/30 font-mono text-[10px] font-semibold tabular-nums shrink-0">
                          Save {distSaved.toFixed(1)}m/pick
                        </span>
                      </div>

                      <div
                        className="grid grid-cols-2 gap-2 p-3 rounded-xl border font-mono text-[11px] tabular-nums"
                        style={{
                          background: "var(--studio-surface-subtle)",
                          borderColor: "var(--studio-border)",
                        }}
                      >
                        <div>
                          <span className="block text-[10.5px]" style={{ color: "var(--studio-text-muted)" }}>
                            Current bin
                          </span>
                          <span className="text-[#8F4F0D] dark:text-amber-300 font-semibold">{currentBin}</span>
                        </div>
                        <div>
                          <span className="block text-[10.5px]" style={{ color: "var(--studio-text-muted)" }}>
                            Recommended bin
                          </span>
                          <span className="text-[#1D6144] dark:text-emerald-300 font-semibold">{recBin}</span>
                        </div>
                      </div>

                      <p className="text-[11px]" style={{ color: "var(--studio-text-secondary)" }}>
                        {rationale}
                      </p>

                      <div
                        className="pt-2.5 border-t flex items-center justify-between"
                        style={{ borderColor: "var(--studio-border)" }}
                      >
                        <span className="text-[10px] font-mono" style={{ color: "var(--studio-text-muted)" }}>
                          Requires human supervisor sign-off
                        </span>
                        <button
                          type="button"
                          disabled={isApproving}
                          onClick={() => handleApproveReslot(recId)}
                          className="studio-btn px-3.5 py-1.5 rounded-xl bg-[var(--studio-accent-solid)] hover:bg-[var(--studio-accent-hover)] text-white font-semibold text-xs flex items-center gap-1.5 cursor-pointer shadow-sm disabled:opacity-50"
                        >
                          {isApproving ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" strokeWidth={1.5} />
                          ) : (
                            <Check className="w-3.5 h-3.5" strokeWidth={1.5} />
                          )}
                          {isApproving ? "Approving…" : "Approve Re-Slot Move"}
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
        <div
          className="px-6 py-3 border-t flex items-center justify-between text-xs"
          style={{
            borderColor: "var(--studio-border)",
            background: "var(--studio-surface-subtle)",
            color: "var(--studio-text-muted)",
          }}
        >
          <span className="font-mono text-[10.5px]">
            All supervisor actions are recorded to the immutable audit ledger
          </span>
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
