import React, { useEffect, useState } from "react";
import { AlertCircle, AlertTriangle, Crosshair, X } from "lucide-react";
import { setStore, useStore } from "../store/useStore";

export const AlertBanner: React.FC = () => {
  const {
    alerts,
    isEnvironmentModalOpen,
    isEStopModalOpen,
    isChaosControlOpen,
    isExceptionsQueueOpen,
    isAuditLogOpen,
  } = useStore();
  const [dismissedAlertIds, setDismissedAlertIds] = useState<Set<string>>(new Set());
  const [currentIndex, setCurrentIndex] = useState(0);

  // Combine active simulation alerts
  const activeAlerts = alerts.filter((a) => !a.cleared && !dismissedAlertIds.has(a.id));

  // If new alerts arrive or list shrinks, keep index in bounds
  useEffect(() => {
    if (activeAlerts.length > 0 && currentIndex >= activeAlerts.length) {
      setCurrentIndex(0);
    }
  }, [activeAlerts.length, currentIndex]);

  const currentAlert = activeAlerts[currentIndex] || activeAlerts[0];

  const anyModalOpen =
    isEnvironmentModalOpen ||
    isEStopModalOpen ||
    isChaosControlOpen ||
    isExceptionsQueueOpen ||
    isAuditLogOpen;

  useEffect(() => {
    if (!currentAlert || anyModalOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !e.defaultPrevented) {
        setDismissedAlertIds((prev) => new Set(prev).add(currentAlert.id));
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [currentAlert?.id, anyModalOpen]);

  if (activeAlerts.length === 0 || !currentAlert) return null;

  const isCritical = currentAlert.severity === "CRITICAL";

  const handleLocate = () => {
    if (currentAlert.entity_id) {
      setStore({
        selectedRobotId: currentAlert.entity_id,
        focusedCoord: currentAlert.coord || undefined,
        activeRightTab: "alerts",
        rightPanelOpen: true,
      });
    } else if (currentAlert.coord) {
      setStore({
        focusedCoord: currentAlert.coord,
        activeRightTab: "alerts",
        rightPanelOpen: true,
      });
    }
  };

  const handleDismiss = () => {
    setDismissedAlertIds((prev) => new Set(prev).add(currentAlert.id));
  };

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed top-[72px] left-1/2 -translate-x-1/2 z-40 max-w-2xl w-full px-4"
    >
      <div
        className={`studio-enter flex items-center justify-between gap-3 px-4 py-2.5 rounded-2xl border backdrop-blur-xl ${
          isCritical
            ? "bg-[#FFF5F3]/95 dark:bg-[#2C1815]/95 border-red-700/30 dark:border-red-500/45 text-[var(--studio-text-primary)]"
            : "bg-[#FFF9F0]/95 dark:bg-[#2A2015]/95 border-amber-700/30 dark:border-amber-500/45 text-[var(--studio-text-primary)]"
        }`}
        style={{ boxShadow: "var(--studio-shadow-hover)" }}
      >
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div
            className={`p-2 rounded-xl shrink-0 ${
              isCritical
                ? "bg-red-600/12 text-[#B93829] dark:bg-red-500/20 dark:text-red-300"
                : "bg-amber-600/12 text-[#B4691E] dark:bg-amber-500/20 dark:text-amber-300"
            }`}
          >
            {isCritical ? (
              <AlertCircle className="w-4 h-4" strokeWidth={1.5} />
            ) : (
              <AlertTriangle className="w-4 h-4" strokeWidth={1.5} />
            )}
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span
                className={`text-[10.5px] font-mono font-semibold px-1.5 py-0.5 rounded-md border ${
                  isCritical
                    ? "bg-red-600/10 border-red-700/25 text-[#9E2418] dark:bg-red-500/20 dark:border-red-500/35 dark:text-red-200"
                    : "bg-amber-600/10 border-amber-700/25 text-[#8F4F0D] dark:bg-amber-500/20 dark:border-amber-500/35 dark:text-amber-200"
                }`}
              >
                {currentAlert.severity} · {currentAlert.category}
              </span>

              {activeAlerts.length > 1 && (
                <span className="text-[11px] font-mono text-[var(--studio-text-muted)] tabular-nums">
                  {currentIndex + 1} of {activeAlerts.length}
                </span>
              )}
            </div>

            <p className="text-xs font-medium tracking-tight text-[var(--studio-text-primary)] truncate mt-0.5">
              {currentAlert.message}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {(currentAlert.entity_id || currentAlert.coord) && (
            <button
              type="button"
              onClick={handleLocate}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold shadow-sm cursor-pointer studio-btn ${
                isCritical
                  ? "bg-[#B93829] hover:bg-[#9E2D20] text-white"
                  : "bg-[#B4691E] hover:bg-[#965515] text-white"
              }`}
              title="Locate and highlight this entity on the map"
            >
              <Crosshair className="w-3.5 h-3.5" strokeWidth={1.5} />
              <span>Locate</span>
            </button>
          )}

          {activeAlerts.length > 1 && (
            <button
              type="button"
              onClick={() => setCurrentIndex((prev) => (prev + 1) % activeAlerts.length)}
              className="px-2 py-1.5 rounded-xl hover:bg-stone-900/[0.06] dark:hover:bg-white/10 text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] cursor-pointer text-xs font-medium studio-btn"
              title="Next alert"
            >
              Next
            </button>
          )}

          <button
            type="button"
            onClick={handleDismiss}
            className="p-1.5 rounded-xl hover:bg-stone-900/[0.06] dark:hover:bg-white/10 text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] cursor-pointer studio-btn"
            title="Dismiss notification"
            aria-label="Dismiss notification"
          >
            <X className="w-4 h-4" strokeWidth={1.5} />
          </button>
        </div>
      </div>
    </div>
  );
};
