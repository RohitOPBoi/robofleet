import React from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  Info,
  ShieldAlert,
} from "lucide-react";
import { setStore, useStore } from "../store/useStore";

export const AlertDrawer: React.FC = () => {
  const { alerts, tick } = useStore();

  const activeAlerts = alerts.filter((a) => !a.cleared);

  const locateOnMap = (alert: (typeof alerts)[0]) => {
    if (alert.entity_id) {
      setStore({
        selectedRobotId: alert.entity_id,
        focusedCoord: alert.coord || null,
      });
    } else if (alert.coord) {
      setStore({ focusedCoord: alert.coord });
    }
  };

  return (
    <div className="w-full h-full flex flex-col text-xs overflow-hidden bg-[var(--studio-surface)] text-[var(--studio-text-primary)]">
      {/* Alert list */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-2 min-h-0">
        {activeAlerts.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center px-4 py-8">
            <CheckCircle
              className="w-6 h-6 text-[#1D6144] dark:text-emerald-300 mb-2"
              strokeWidth={1.5}
            />
            <p className="font-medium text-[var(--studio-text-primary)] text-xs">
              All systems nominal
            </p>
            <p className="text-[11px] text-[var(--studio-text-muted)] mt-0.5">
              Zero active safety or operational violations
            </p>
          </div>
        ) : (
          activeAlerts.map((alert) => {
            const ageTicks = tick - alert.tick;
            const ageSecs = Math.max(0, Math.floor(ageTicks / 10));

            return (
              <div
                key={alert.id}
                className={`p-3 rounded-xl border transition-[border-color,background-color] duration-150 ${
                  alert.severity === "CRITICAL"
                    ? "bg-red-50/80 dark:bg-red-950/30 border-red-700/25 dark:border-red-500/40"
                    : alert.severity === "WARN"
                      ? "bg-amber-50/80 dark:bg-amber-950/25 border-amber-700/25 dark:border-amber-500/40"
                      : "bg-[var(--studio-surface-elevated)] border-[var(--studio-border-strong)]"
                }`}
              >
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-1.5 font-semibold text-xs min-w-0">
                    {alert.severity === "CRITICAL" ? (
                      <AlertCircle
                        className="w-4 h-4 text-[#B93829] dark:text-red-400 shrink-0"
                        strokeWidth={1.5}
                      />
                    ) : alert.severity === "WARN" ? (
                      <AlertTriangle
                        className="w-4 h-4 text-[#B4691E] dark:text-amber-300 shrink-0"
                        strokeWidth={1.5}
                      />
                    ) : (
                      <Info
                        className="w-4 h-4 text-[#A53420] dark:text-studio-coral shrink-0"
                        strokeWidth={1.5}
                      />
                    )}
                    <span className="font-mono text-[11px] text-[var(--studio-text-primary)] truncate">
                      {alert.category}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 font-mono text-[10.5px] text-[var(--studio-text-muted)] tabular-nums shrink-0">
                    <span>{ageSecs}s ago</span>
                    {alert.requires_human && (
                      <span className="flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-amber-600/12 dark:bg-amber-500/20 text-[#8F4F0D] dark:text-amber-300 border border-amber-700/25 dark:border-amber-500/35 font-semibold text-[10px]">
                        <ShieldAlert className="w-3 h-3" strokeWidth={1.5} />
                        <span>Human</span>
                      </span>
                    )}
                  </div>
                </div>

                <p className="text-[var(--studio-text-secondary)] text-[11.5px] leading-relaxed mb-2">
                  {alert.message}
                </p>

                {(alert.entity_id || alert.coord) && (
                  <div className="flex items-center justify-between border-t border-[var(--studio-border)] pt-2">
                    <span className="font-mono text-[var(--studio-text-muted)] text-[10.5px] tabular-nums">
                      {alert.entity_id
                        ? `Target: ${alert.entity_id}`
                        : `Location: (${alert.coord!.x}, ${alert.coord!.y})`}
                    </span>
                    <button
                      type="button"
                      onClick={() => locateOnMap(alert)}
                      className="flex items-center gap-1 px-2 py-1 rounded-lg bg-studio-terracotta/12 hover:bg-studio-terracotta/20 text-[#A53420] dark:text-studio-coral font-medium text-[11px] cursor-pointer studio-btn"
                    >
                      <span>Locate</span>
                      <ArrowRight className="w-3 h-3" strokeWidth={1.5} />
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
