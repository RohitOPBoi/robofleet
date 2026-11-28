import React, { useEffect, useState } from "react";
import { Battery, Compass, Gauge, Loader2, MapPin, ShieldAlert, X } from "lucide-react";
import { emergencyStop } from "../services/api";
import { setStore, useStore } from "../store/useStore";

const formatRobotState = (state: string): string => {
  const cleaned = state.replace(/_/g, " ").toLowerCase();
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
};

export const SelectedRobotPanel: React.FC = () => {
  const { robots, selectedRobotId } = useStore();
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    setErrorMsg(null);
    setSubmitting(false);
  }, [selectedRobotId]);

  if (!selectedRobotId) return null;

  const robot = robots[selectedRobotId];
  if (!robot) return null;

  const handleStopSingle = async () => {
    setSubmitting(true);
    setErrorMsg(null);
    try {
      await emergencyStop("robot", robot.id);
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : "Failed to halt AMR");
    } finally {
      setSubmitting(false);
    }
  };

  const batteryPct = Math.max(0, Math.min(100, Math.round(robot.battery_percent ?? 100)));
  const isFaulted = robot.state === "FAULTED" || robot.state === "EMERGENCY_STOPPED";
  const isCharging = robot.state === "CHARGING";

  const statusDotClass = isFaulted
    ? "bg-[#B93829] dark:bg-red-400"
    : isCharging
      ? "bg-[#B4691E] dark:bg-amber-400"
      : "bg-[#2E7D5B] dark:bg-emerald-400";

  const statusBadgeClass = isCharging
    ? "bg-amber-600/12 text-[#8F4F0D] border-amber-700/25 dark:bg-amber-500/18 dark:text-amber-300 dark:border-amber-500/35"
    : isFaulted
      ? "bg-red-600/12 text-[#9E2418] border-red-700/25 dark:bg-red-500/18 dark:text-red-300 dark:border-red-500/35"
      : "bg-emerald-600/12 text-[#1D6144] border-emerald-700/25 dark:bg-emerald-500/18 dark:text-emerald-300 dark:border-emerald-500/35";

  return (
    <div
      className="absolute top-4 right-4 w-72 bg-[var(--studio-surface-elevated)] border border-[var(--studio-border-strong)] rounded-2xl backdrop-blur-xl p-4 z-30 text-xs studio-enter text-[var(--studio-text-primary)]"
      style={{ boxShadow: "var(--studio-shadow-hover)" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-[var(--studio-border)]">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${statusDotClass}`} />
          <span className="font-mono font-semibold text-[var(--studio-text-primary)] text-sm truncate tabular-nums">
            {robot.id}
          </span>
        </div>
        <button
          type="button"
          onClick={() => setStore({ selectedRobotId: null })}
          className="p-1 rounded-lg text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)] hover:bg-stone-900/[0.06] dark:hover:bg-white/10 cursor-pointer studio-btn"
          aria-label="Close robot inspector"
        >
          <X className="w-4 h-4" strokeWidth={1.5} />
        </button>
      </div>

      <div className="space-y-3 text-[var(--studio-text-secondary)]">
        {/* State Badge */}
        <div className="flex items-center justify-between">
          <span className="text-[var(--studio-text-secondary)]">Status</span>
          <span
            className={`px-2 py-0.5 rounded-md font-mono font-medium text-[11px] border ${statusBadgeClass}`}
          >
            {formatRobotState(robot.state)}
          </span>
        </div>

        {/* Battery Telemetry */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="flex items-center gap-1.5 text-[var(--studio-text-secondary)]">
              <Battery
                className="w-3.5 h-3.5 text-[#1D6144] dark:text-emerald-300"
                strokeWidth={1.5}
              />
              <span>Battery</span>
            </span>
            <span className="font-mono font-semibold text-[var(--studio-text-primary)] tabular-nums">
              {batteryPct}%
            </span>
          </div>
          <div className="w-full h-1.5 bg-stone-900/10 dark:bg-white/10 rounded-full overflow-hidden">
            <div
              className={`w-full h-full rounded-full origin-left transform transition-transform duration-300 ease-[var(--ease-out)] ${
                batteryPct > 50
                  ? "bg-[#2E7D5B] dark:bg-emerald-500"
                  : batteryPct > 20
                    ? "bg-[#B4691E] dark:bg-amber-500"
                    : "bg-[#B93829] dark:bg-red-500"
              }`}
              style={{ transform: `scaleX(${batteryPct / 100})` }}
            />
          </div>
        </div>

        {/* Spatial Coordinates & Heading */}
        <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
          <div className="p-2.5 rounded-xl bg-[var(--studio-surface-subtle)] border border-[var(--studio-border)]">
            <div className="flex items-center gap-1 text-[var(--studio-text-muted)] font-sans text-[10.5px] mb-0.5">
              <MapPin className="w-3 h-3 text-[#A53420] dark:text-studio-coral" strokeWidth={1.5} />
              <span>Position</span>
            </div>
            <div className="font-semibold text-[var(--studio-text-primary)] tabular-nums">
              ({robot.coord?.x ?? 0}, {robot.coord?.y ?? 0})
            </div>
          </div>
          <div className="p-2.5 rounded-xl bg-[var(--studio-surface-subtle)] border border-[var(--studio-border)]">
            <div className="flex items-center gap-1 text-[var(--studio-text-muted)] font-sans text-[10.5px] mb-0.5">
              <Compass className="w-3 h-3 text-[var(--studio-text-secondary)]" strokeWidth={1.5} />
              <span>Heading</span>
            </div>
            <div className="font-semibold text-[var(--studio-text-primary)] tabular-nums">
              {Math.round(robot.heading_deg ?? 0)}°
            </div>
          </div>
        </div>

        {/* Speed */}
        <div className="p-2.5 rounded-xl bg-[var(--studio-surface-subtle)] border border-[var(--studio-border)] flex items-center justify-between font-mono text-[11px]">
          <div className="flex items-center gap-1.5 text-[var(--studio-text-muted)] font-sans">
            <Gauge className="w-3.5 h-3.5 text-[#8F4F0D] dark:text-amber-300" strokeWidth={1.5} />
            <span>Speed</span>
          </div>
          <div className="font-semibold text-[var(--studio-text-primary)] tabular-nums">
            {robot.telemetry?.current_speed_m_s
              ? robot.telemetry.current_speed_m_s.toFixed(2)
              : "0.00"}{" "}
            m/s
          </div>
        </div>

        {errorMsg && (
          <div className="p-2 rounded-xl bg-red-600/12 border border-red-700/25 text-[#9E2418] dark:text-red-300 text-[11px] font-medium">
            {errorMsg}
          </div>
        )}

        {/* Actions */}
        <div className="pt-2 border-t border-[var(--studio-border)] flex gap-2">
          <button
            type="button"
            onClick={handleStopSingle}
            disabled={submitting}
            className="flex-1 py-2 rounded-xl bg-red-600/10 hover:bg-red-600/18 dark:bg-red-500/15 dark:hover:bg-red-500/25 border border-red-700/25 dark:border-red-500/35 text-[#9E2418] dark:text-red-300 flex items-center justify-center gap-1.5 font-semibold cursor-pointer studio-btn disabled:opacity-50"
          >
            {submitting ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" strokeWidth={1.5} />
            ) : (
              <ShieldAlert className="w-3.5 h-3.5" strokeWidth={1.5} />
            )}
            <span>{submitting ? "Halting…" : "Halt AMR"}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
