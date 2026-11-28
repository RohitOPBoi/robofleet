import React, { useEffect, useState } from "react";
import { AlertTriangle, Loader2, ShieldAlert, X } from "lucide-react";
import { blockCells, emergencyStop, resumeEmergency } from "../services/api";
import { setStore, useStore } from "../store/useStore";

export const ControlModals: React.FC = () => {
  const { isEStopModalOpen, selectedCellsToBlock, blockModeActive } = useStore();
  const [submitting, setSubmitting] = useState<"estop" | "resume" | "block" | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleClose = () => {
    setErrorMsg(null);
    if (blockModeActive) {
      setStore({ isEStopModalOpen: false, blockModeActive: false, selectedCellsToBlock: [] });
    } else {
      setStore({ isEStopModalOpen: false });
    }
  };

  useEffect(() => {
    if (!isEStopModalOpen) {
      setSubmitting(null);
      setErrorMsg(null);
      return;
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        handleClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isEStopModalOpen, blockModeActive]);

  if (!isEStopModalOpen) return null;

  const handleEStopAll = async () => {
    setSubmitting("estop");
    setErrorMsg(null);
    try {
      await emergencyStop("all");
      setStore({ isEStopModalOpen: false });
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : "Failed to execute emergency stop");
    } finally {
      setSubmitting(null);
    }
  };

  const handleResumeAll = async () => {
    setSubmitting("resume");
    setErrorMsg(null);
    try {
      await resumeEmergency("all");
      setStore({ isEStopModalOpen: false });
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : "Failed to resume fleet operations");
    } finally {
      setSubmitting(null);
    }
  };

  const handleConfirmBlock = async () => {
    setSubmitting("block");
    setErrorMsg(null);
    try {
      await blockCells(selectedCellsToBlock);
      setStore({
        isEStopModalOpen: false,
        blockModeActive: false,
        selectedCellsToBlock: [],
      });
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : "Failed to apply cell block");
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#191310]/65 backdrop-blur-md p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="control-modal-title"
        className="studio-card-modal studio-enter rounded-[20px] border max-w-md w-full overflow-hidden"
        style={{
          background: "var(--studio-surface-elevated)",
          borderColor: "rgba(185, 56, 41, 0.30)",
          boxShadow: "var(--studio-shadow-hover)",
        }}
      >
        {/* Header */}
        <div
          className="px-6 py-4 border-b flex items-center justify-between bg-studio-crimson/[0.08]"
          style={{ borderColor: "var(--studio-border)" }}
        >
          <div className="flex items-center gap-2.5 text-[#9E2418] dark:text-red-400 font-semibold text-sm">
            <div className="w-8 h-8 rounded-xl bg-studio-crimson/15 border border-studio-crimson/30 flex items-center justify-center">
              <ShieldAlert className="w-4 h-4 text-[#9E2418] dark:text-red-400" strokeWidth={1.5} />
            </div>
            <span id="control-modal-title" style={{ color: "var(--studio-text-primary)" }}>
              Emergency Operations Control
            </span>
          </div>
          <button
            type="button"
            aria-label="Close modal"
            onClick={handleClose}
            className="studio-btn p-1.5 rounded-xl text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)] hover:bg-black/5 dark:hover:bg-white/10 cursor-pointer"
          >
            <X className="w-4 h-4" strokeWidth={1.5} />
          </button>
        </div>

        {/* Content */}
        <div
          className="p-6 space-y-4 text-xs"
          style={{ color: "var(--studio-text-secondary)" }}
        >
          {errorMsg && (
            <div className="p-3 rounded-xl bg-red-600/12 border border-red-700/25 text-[#9E2418] dark:text-red-300 font-medium">
              {errorMsg}
            </div>
          )}

          {blockModeActive && selectedCellsToBlock.length > 0 ? (
            <div>
              <p
                className="text-sm font-semibold mb-1.5 tabular-nums"
                style={{ color: "var(--studio-text-primary)" }}
              >
                Confirm blocking {selectedCellsToBlock.length} warehouse grid cell(s)?
              </p>
              <p
                className="leading-relaxed mb-4"
                style={{ color: "var(--studio-text-secondary)" }}
              >
                All pathfinding algorithms will dynamically re-route AMRs around these coordinates. If an AMR is
                currently occupying a blocked cell, it will yield and request replanning.
              </p>
              <button
                type="button"
                onClick={handleConfirmBlock}
                disabled={submitting !== null}
                className="studio-btn w-full py-2.5 bg-studio-crimson hover:bg-[#9E2E21] text-white font-semibold rounded-xl flex items-center justify-center gap-2 cursor-pointer shadow-sm disabled:opacity-50"
              >
                {submitting === "block" && <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.5} />}
                <span>{submitting === "block" ? "Applying block…" : "Apply Cell Block"}</span>
              </button>
            </div>
          ) : (
            <div>
              <div className="p-3.5 rounded-2xl bg-studio-crimson/10 border border-studio-crimson/25 flex items-start gap-2.5 mb-4">
                <AlertTriangle
                  className="w-4 h-4 text-[#9E2418] dark:text-red-400 shrink-0 mt-0.5"
                  strokeWidth={1.5}
                />
                <span
                  className="leading-relaxed"
                  style={{ color: "var(--studio-text-primary)" }}
                >
                  Executing Emergency Stop immediately halts motion on the selected scope. Path reservations will be held
                  until a supervisory resume command is authenticated.
                </span>
              </div>

              <div className="space-y-2.5">
                <button
                  type="button"
                  onClick={handleEStopAll}
                  disabled={submitting !== null}
                  className="studio-btn w-full py-2.5 bg-studio-crimson hover:bg-[#9E2E21] text-white font-semibold rounded-xl flex items-center justify-center gap-2 cursor-pointer shadow-sm disabled:opacity-50"
                >
                  {submitting === "estop" ? (
                    <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.5} />
                  ) : (
                    <ShieldAlert className="w-4 h-4" strokeWidth={1.5} />
                  )}
                  <span>{submitting === "estop" ? "Stopping fleet…" : "Emergency stop all AMRs"}</span>
                </button>

                <button
                  type="button"
                  onClick={handleResumeAll}
                  disabled={submitting !== null}
                  className="studio-btn w-full py-2.5 bg-studio-sage/15 hover:bg-studio-sage/25 text-[#1D6144] dark:text-emerald-300 border border-studio-sage/30 font-semibold rounded-xl flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                >
                  {submitting === "resume" && <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.5} />}
                  <span>{submitting === "resume" ? "Resuming fleet…" : "Resume Fleet Operations"}</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="px-6 py-3 border-t flex justify-end"
          style={{
            borderColor: "var(--studio-border)",
            background: "var(--studio-surface-subtle)",
          }}
        >
          <button
            type="button"
            onClick={handleClose}
            className="studio-btn px-3.5 py-1.5 rounded-xl text-xs font-semibold border cursor-pointer"
            style={{
              background: "var(--studio-surface-elevated)",
              borderColor: "var(--studio-border-strong)",
              color: "var(--studio-text-primary)",
            }}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};
