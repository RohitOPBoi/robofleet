import React, { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  UserCheck,
  X,
  XCircle,
} from "lucide-react";
import { actOnApproval } from "../../services/api";
import { setStore, updateStore, useStore } from "../../store/useStore";

export const ApprovalsDrawer: React.FC = () => {
  const store = useStore();
  const { pendingApprovals, isApprovalsDrawerOpen, tick } = store;
  const [submittingState, setSubmittingState] = useState<{
    id: string;
    action: "approve" | "reject";
  } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (isApprovalsDrawerOpen) {
      setActionError(null);
      dialogRef.current?.focus();
    }
  }, [isApprovalsDrawerOpen]);

  if (!isApprovalsDrawerOpen) return null;

  const closeDrawer = () => setStore({ isApprovalsDrawerOpen: false });

  const handleAction = async (requestId: string, action: "approve" | "reject") => {
    setSubmittingState({ id: requestId, action });
    setActionError(null);
    try {
      await actOnApproval(requestId, action);
      updateStore((prev) => ({
        ...prev,
        pendingApprovals: prev.pendingApprovals.filter((a) => a.request_id !== requestId),
      }));
    } catch (e: any) {
      console.error(`Failed to ${action} approval:`, e);
      setActionError(e?.message || `Failed to ${action} approval request #${requestId}.`);
    } finally {
      setSubmittingState(null);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#191310]/65 backdrop-blur-sm p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) closeDrawer();
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.stopPropagation();
          closeDrawer();
        }
      }}
    >
      <div
        ref={dialogRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="approvals-drawer-title"
        className="studio-card-modal studio-drawer-enter bg-[#FFFBF8] dark:bg-[#241B16] border border-[var(--studio-border-strong)] shadow-[var(--studio-shadow)] text-[var(--studio-text-primary)] rounded-[20px] w-full max-w-2xl max-h-[80vh] flex flex-col overflow-hidden select-text outline-none"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-[var(--studio-border)] bg-[var(--studio-surface-subtle)]/55 flex items-center justify-between gap-3 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-[12px] bg-[#B4691E]/14 text-[#85470D] dark:text-amber-300 border border-[#B4691E]/30 flex items-center justify-center shrink-0">
              <UserCheck className="w-5 h-5" strokeWidth={1.5} />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h2
                  id="approvals-drawer-title"
                  className="text-base font-semibold text-[var(--studio-text-primary)] tracking-tight"
                >
                  Human-in-the-loop governance queue
                </h2>
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-[#B4691E]/12 text-[#85470D] dark:text-amber-300 border border-[#B4691E]/30 font-semibold tabular-nums">
                  {pendingApprovals.length} pending
                </span>
              </div>
              <p className="text-xs text-[var(--studio-text-muted)] mt-0.5">
                Declarative policy gates requiring supervisor sign-off before execution
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={closeDrawer}
            className="studio-btn p-2 rounded-[10px] text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-subtle)] cursor-pointer shrink-0"
            aria-label="Close approvals queue"
          >
            <X className="w-4 h-4" strokeWidth={1.5} />
          </button>
        </div>

        {/* Requests List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {actionError && (
            <div
              role="alert"
              className="p-3 rounded-[12px] bg-[#B93829]/12 border border-[#B93829]/30 text-[#A32D20] dark:text-[#F28B7D] flex items-center justify-between gap-2 text-xs"
            >
              <div className="flex items-center gap-2 min-w-0">
                <AlertCircle className="w-4 h-4 shrink-0" strokeWidth={1.5} />
                <span className="break-words">{actionError}</span>
              </div>
              <button
                type="button"
                onClick={() => setActionError(null)}
                className="p-1 rounded-[6px] hover:bg-[#B93829]/15 transition-colors duration-150 cursor-pointer shrink-0"
                aria-label="Dismiss error"
              >
                <X className="w-3.5 h-3.5" strokeWidth={1.5} />
              </button>
            </div>
          )}

          {pendingApprovals.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-[var(--studio-text-muted)]">
              <CheckCircle2
                className="w-10 h-10 mb-2 text-[#176441] dark:text-emerald-300"
                strokeWidth={1.5}
              />
              <p className="text-sm font-medium text-[var(--studio-text-primary)]">
                Approvals queue clear
              </p>
              <p className="text-xs text-[var(--studio-text-muted)] mt-1">
                Zero pending actions requiring supervisor escalation.
              </p>
            </div>
          ) : (
            pendingApprovals.map((req) => {
              const remainingTicks = Math.max(0, req.timeout_tick - tick);
              const isExpired = remainingTicks === 0;
              const isSubmitting = submittingState?.id === req.request_id;
              const isRejecting = isSubmitting && submittingState?.action === "reject";
              const isApproving = isSubmitting && submittingState?.action === "approve";

              return (
                <div
                  key={req.request_id}
                  className={`p-4 rounded-[12px] bg-[var(--studio-surface-elevated)]/85 border flex flex-col gap-3 ${
                    isExpired
                      ? "border-[#B93829]/35 opacity-85"
                      : "border-[#B4691E]/30"
                  }`}
                >
                  <div className="flex items-center justify-between text-xs flex-wrap gap-2">
                    <div className="flex items-center gap-2 font-mono tabular-nums flex-wrap">
                      <span className="px-2 py-0.5 rounded-[8px] bg-[#B4691E]/12 text-[#85470D] dark:text-amber-300 border border-[#B4691E]/30 font-semibold text-[11px]">
                        Req #{req.request_id}
                      </span>
                      <span className="text-[var(--studio-text-secondary)]">
                        Decision #{req.decision_id}
                      </span>
                      <span className="text-[var(--studio-text-muted)]">
                        Created: T+{req.created_tick}
                      </span>
                    </div>

                    <div
                      className={`flex items-center gap-1.5 font-mono text-[11px] tabular-nums ${
                        isExpired
                          ? "text-[#A32D20] dark:text-[#F28B7D] font-semibold"
                          : "text-[#85470D] dark:text-amber-300"
                      }`}
                    >
                      <Clock className="w-3.5 h-3.5" strokeWidth={1.5} />
                      <span>
                        {isExpired
                          ? "Expired (timeout reached)"
                          : `Expires in ${remainingTicks} ticks (${(remainingTicks / 10).toFixed(1)}s)`}
                      </span>
                    </div>
                  </div>

                  <div>
                    <h4 className="text-sm font-semibold text-[var(--studio-text-primary)]">
                      {req.reason || "Action requires human operational approval"}
                    </h4>
                    <div className="mt-2 p-3 rounded-[12px] bg-[var(--studio-surface-subtle)] border border-[var(--studio-border)] font-mono text-[11px] text-[var(--studio-text-primary)] overflow-x-auto">
                      Command: {JSON.stringify(req.command)}
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-2.5 border-t border-[var(--studio-border)] text-xs gap-2 flex-wrap">
                    <span className="text-[var(--studio-text-muted)] text-[11px]">
                      Default on timeout:{" "}
                      <strong className="text-[var(--studio-text-primary)] capitalize font-semibold">
                        {req.default_action}
                      </strong>
                    </span>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        disabled={isSubmitting || isExpired}
                        onClick={() => handleAction(req.request_id, "reject")}
                        className="studio-btn flex items-center gap-1.5 px-3.5 py-1.5 rounded-[10px] bg-[#B93829]/12 hover:bg-[#B93829]/20 text-[#A32D20] dark:text-[#F28B7D] border border-[#B93829]/30 font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isRejecting ? (
                          <Loader2 className="w-3.5 h-3.5 motion-safe:animate-spin" strokeWidth={1.5} />
                        ) : (
                          <XCircle className="w-3.5 h-3.5" strokeWidth={1.5} />
                        )}
                        <span>{isRejecting ? "Denying..." : "Deny"}</span>
                      </button>

                      <button
                        type="button"
                        disabled={isSubmitting || isExpired}
                        onClick={() => handleAction(req.request_id, "approve")}
                        className="studio-btn flex items-center gap-1.5 px-3.5 py-1.5 rounded-[10px] bg-[#1E7E53] hover:bg-[#176441] text-[#FFFBF8] font-semibold cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isApproving ? (
                          <Loader2 className="w-3.5 h-3.5 motion-safe:animate-spin" strokeWidth={1.5} />
                        ) : (
                          <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={1.5} />
                        )}
                        <span>{isApproving ? "Approving..." : "Approve & execute"}</span>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
