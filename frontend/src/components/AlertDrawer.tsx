import React from "react";
import { AlertCircle, AlertTriangle, ArrowRight, CheckCircle, Info, ShieldAlert } from "lucide-react";
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
    <div className="w-full h-full flex flex-col text-xs select-none overflow-hidden">
      {/* Alert list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5 min-h-0">
        {activeAlerts.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-gray-500 text-center px-4 py-8">
            <CheckCircle className="w-6 h-6 text-emerald-500 mb-1 opacity-70" />
            <p className="font-medium text-gray-300 text-xs">All systems nominal</p>
            <p className="text-[10px] text-gray-500">Zero active safety or operational violations</p>
          </div>
        ) : (
          activeAlerts.map((alert) => {
            const ageTicks = tick - alert.tick;
            const ageSecs = Math.max(0, Math.floor(ageTicks / 10));

            return (
              <div
                key={alert.id}
                className={`p-2.5 rounded-lg border transition ${
                  alert.severity === "CRITICAL"
                    ? "bg-red-950/30 border-red-800/80 text-red-200"
                    : alert.severity === "WARN"
                    ? "bg-amber-950/30 border-amber-800/80 text-amber-200"
                    : "bg-blue-950/30 border-blue-800/80 text-blue-200"
                }`}
              >
                <div className="flex items-start justify-between gap-1.5 mb-1">
                  <div className="flex items-center gap-1.5 font-semibold text-xs">
                    {alert.severity === "CRITICAL" ? (
                      <AlertCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />
                    ) : alert.severity === "WARN" ? (
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                    ) : (
                      <Info className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                    )}
                    <span className="font-mono text-[11px]">{alert.category}</span>
                  </div>
                  <div className="flex items-center gap-1 font-mono text-[10px] text-gray-400">
                    <span>{ageSecs}s ago</span>
                    {alert.requires_human && (
                      <span className="flex items-center gap-0.5 px-1 py-0.2 rounded bg-amber-950 text-amber-400 border border-amber-800 font-bold">
                        <ShieldAlert className="w-2.5 h-2.5" /> HUMAN
                      </span>
                    )}
                  </div>
                </div>

                <p className="text-gray-300 text-[11px] leading-relaxed mb-2">{alert.message}</p>

                {alert.entity_id && (
                  <div className="flex items-center justify-between border-t border-gray-800/60 pt-1.5">
                    <span className="font-mono text-gray-400 text-[10px]">Target: {alert.entity_id}</span>
                    <button
                      type="button"
                      onClick={() => locateOnMap(alert)}
                      className="flex items-center gap-0.5 text-blue-400 hover:text-blue-300 font-medium text-[10px] transition cursor-pointer"
                    >
                      <span>Locate</span>
                      <ArrowRight className="w-3 h-3" />
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
