import React, { useState, useEffect } from "react";
import { AlertCircle, AlertTriangle, ArrowRight, Crosshair, ShieldAlert, X } from "lucide-react";
import { setStore, useStore } from "../store/useStore";

export const AlertBanner: React.FC = () => {
  const { alerts, activeFaults, selectedRobotId } = useStore();
  const [dismissedAlertIds, setDismissedAlertIds] = useState<Set<string>>(new Set());
  const [currentIndex, setCurrentIndex] = useState(0);

  // Combine active simulation alerts and chaos faults
  const activeAlerts = alerts.filter((a) => !a.cleared && !dismissedAlertIds.has(a.id));

  // If new alerts arrive, reset index
  useEffect(() => {
    if (activeAlerts.length > 0 && currentIndex >= activeAlerts.length) {
      setCurrentIndex(0);
    }
  }, [activeAlerts.length, currentIndex]);

  if (activeAlerts.length === 0) return null;

  const currentAlert = activeAlerts[currentIndex] || activeAlerts[0];
  if (!currentAlert) return null;

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
    <div className="fixed top-14 left-1/2 -translate-x-1/2 z-40 max-w-2xl w-full px-4 animate-in fade-in slide-in-from-top-2 duration-200">
      <div
        className={`flex items-center justify-between gap-3 px-4 py-2.5 rounded-xl shadow-2xl border backdrop-blur-md ${
          isCritical
            ? "bg-red-950/90 border-red-500/80 text-red-100 shadow-red-950/50"
            : "bg-amber-950/90 border-amber-500/80 text-amber-100 shadow-amber-950/50"
        }`}
      >
        <div className="flex items-center gap-2.5 min-w-0 flex-1">
          <div
            className={`p-1.5 rounded-lg shrink-0 ${
              isCritical ? "bg-red-600/30 text-red-400 animate-pulse" : "bg-amber-600/30 text-amber-400"
            }`}
          >
            {isCritical ? <AlertCircle className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span
                className={`text-[10px] font-mono uppercase font-bold px-1.5 py-0.2 rounded border ${
                  isCritical
                    ? "bg-red-900/60 border-red-700 text-red-200"
                    : "bg-amber-900/60 border-amber-700 text-amber-200"
                }`}
              >
                {currentAlert.severity} {currentAlert.category}
              </span>

              {activeAlerts.length > 1 && (
                <span className="text-[10px] font-mono text-gray-400">
                  ({currentIndex + 1} of {activeAlerts.length})
                </span>
              )}
            </div>

            <p className="text-xs font-medium tracking-tight truncate mt-0.5">{currentAlert.message}</p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {(currentAlert.entity_id || currentAlert.coord) && (
            <button
              type="button"
              onClick={handleLocate}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold transition shadow-sm cursor-pointer ${
                isCritical
                  ? "bg-red-600 hover:bg-red-500 text-white"
                  : "bg-amber-600 hover:bg-amber-500 text-white"
              }`}
              title="Locate and highlight this entity on the map"
            >
              <Crosshair className="w-3.5 h-3.5" />
              <span>Locate</span>
            </button>
          )}

          {activeAlerts.length > 1 && (
            <button
              type="button"
              onClick={() => setCurrentIndex((prev) => (prev + 1) % activeAlerts.length)}
              className="p-1 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition cursor-pointer text-xs"
              title="Next alert"
            >
              Next
            </button>
          )}

          <button
            type="button"
            onClick={handleDismiss}
            className="p-1 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition cursor-pointer"
            title="Dismiss notification"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
