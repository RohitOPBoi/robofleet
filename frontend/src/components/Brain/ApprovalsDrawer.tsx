import React, { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  ShieldAlert,
  UserCheck,
  X,
  XCircle,
} from "lucide-react";
import type { ApprovalRequest } from "../../types/generated";
import { actOnApproval } from "../../services/api";
import { setStore, useStore } from "../../store/useStore";

export const ApprovalsDrawer: React.FC = () => {
  const store = useStore();
  const { pendingApprovals, isApprovalsDrawerOpen, tick } = store;
  const [submittingId, setSubmittingId] = useState<string | null>(null);

  if (!isApprovalsDrawerOpen) return null;

  const handleAction = async (requestId: string, action: "approve" | "reject") => {
    setSubmittingId(requestId);
    try {
      await actOnApproval(requestId, action);
      // Remove from store's pending list immediately
      setStore({
        pendingApprovals: pendingApprovals.filter((a) => a.request_id !== requestId),
      });
    } catch (e) {
      console.error(`Failed to ${action} approval:`, e);
    } finally {
      setSubmittingId(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="bg-gray-950 border border-gray-800 rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-800 bg-gray-900/60 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center text-white shadow-lg shadow-amber-500/25">
              <UserCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white tracking-tight">
                  Human-In-The-Loop Governance Queue
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-amber-950 text-amber-300 border border-amber-800/80 font-bold">
                  {pendingApprovals.length} Pending
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-0.5">
                Declarative policy gates requiring supervisor sign-off before execution
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setStore({ isApprovalsDrawerOpen: false })}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Requests List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {pendingApprovals.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-gray-500">
              <CheckCircle2 className="w-10 h-10 mb-2 stroke-[1.25] text-emerald-500/80" />
              <p className="text-sm font-medium text-gray-300">Approvals Queue Clear</p>
              <p className="text-xs text-gray-500 mt-1">
                Zero pending actions requiring supervisor escalation.
              </p>
            </div>
          ) : (
            pendingApprovals.map((req) => {
              const remainingTicks = Math.max(0, req.timeout_tick - tick);
              const isSubmitting = submittingId === req.request_id;

              return (
                <div
                  key={req.request_id}
                  className="p-4 rounded-xl bg-gray-900/80 border border-amber-500/30 shadow-md flex flex-col gap-3"
                >
                  <div className="flex items-center justify-between text-xs flex-wrap gap-2">
                    <div className="flex items-center gap-2 font-mono">
                      <span className="px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800 font-bold text-[10px]">
                        REQ #{req.request_id}
                      </span>
                      <span className="text-gray-400">Decision #{req.decision_id}</span>
                      <span className="text-gray-500">Created: T+{req.created_tick}</span>
                    </div>

                    <div className="flex items-center gap-1.5 font-mono text-[11px] text-amber-400">
                      <Clock className="w-3.5 h-3.5" />
                      <span>Expires in {remainingTicks} ticks ({(remainingTicks / 10).toFixed(1)}s)</span>
                    </div>
                  </div>

                  <div>
                    <h4 className="text-sm font-semibold text-white">
                      {req.reason || "Action requires human operational approval"}
                    </h4>
                    <div className="mt-1.5 p-2.5 rounded-lg bg-gray-950 border border-gray-800 font-mono text-[11px] text-cyan-300 overflow-x-auto">
                      Command: {JSON.stringify(req.command)}
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-2 border-t border-gray-800 text-xs">
                    <span className="text-gray-400 text-[11px]">
                      Default on timeout:{" "}
                      <strong className="text-gray-200 uppercase">{req.default_action}</strong>
                    </span>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        disabled={isSubmitting}
                        onClick={() => handleAction(req.request_id, "reject")}
                        className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-rose-950/60 hover:bg-rose-900/80 text-rose-300 border border-rose-800/80 font-medium transition active:scale-95 cursor-pointer disabled:opacity-50"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        <span>Deny</span>
                      </button>

                      <button
                        type="button"
                        disabled={isSubmitting}
                        onClick={() => handleAction(req.request_id, "approve")}
                        className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium shadow-md shadow-emerald-600/30 transition active:scale-95 cursor-pointer disabled:opacity-50"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Approve & Execute</span>
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
