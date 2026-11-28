/**
 * DiagnosticsOverlay: Real-time HUD showing WebGL2 draw calls,
 * triangle count, FPS, and dynamic quality tier.
 */

import React from "react";
import { Activity } from "lucide-react";
import { useStore } from "../../store/useStore";

export const DiagnosticsOverlay: React.FC = () => {
  const { diagnostics, showDiagnostics } = useStore();

  if (!showDiagnostics) return null;

  const fpsColor =
    diagnostics.fps >= 55
      ? "text-[#176441] dark:text-emerald-300"
      : diagnostics.fps >= 35
      ? "text-[#85470D] dark:text-amber-300"
      : "text-[#B83B24] dark:text-[#E87454]";

  const withinBudget = diagnostics.drawCalls <= 200;

  return (
    <div className="absolute bottom-3 right-3 z-20 studio-card studio-enter stagger-3 rounded-2xl p-3 text-[11px] space-y-2 select-none min-w-[204px]">
      <div className="flex items-center justify-between gap-3 pb-1.5 border-b border-[var(--studio-border)]">
        <div className="flex items-center gap-1.5 font-semibold text-[12px] text-[var(--studio-text-primary)]">
          <Activity className="w-3.5 h-3.5 text-[#B83B24] dark:text-[#E87454]" strokeWidth={1.5} />
          <span>WebGL2 Telemetry</span>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded-full font-mono font-semibold bg-[#D9533B]/12 text-[#B83B24] dark:text-[#E87454] border border-[#D9533B]/25">
          {diagnostics.tier.toUpperCase()}
        </span>
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-[var(--studio-text-muted)]">Frame Rate</span>
          <span className={`font-mono font-semibold tabular-nums ${fpsColor}`}>
            {diagnostics.fps} FPS
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-[var(--studio-text-muted)]">Draw Calls</span>
          <span className="font-mono font-semibold tabular-nums text-[var(--studio-text-primary)]">
            {diagnostics.drawCalls}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-[var(--studio-text-muted)]">Triangles</span>
          <span className="font-mono font-semibold tabular-nums text-[var(--studio-text-primary)]">
            {(diagnostics.triangles / 1000).toFixed(1)}k
          </span>
        </div>
      </div>

      <div className="flex items-center justify-between text-[10px] pt-1.5 border-t border-[var(--studio-border)]">
        <span className="text-[var(--studio-text-muted)] tabular-nums">
          Budget: &le; 200 calls
        </span>
        <span
          className={`font-mono font-semibold ${
            withinBudget
              ? "text-[#176441] dark:text-emerald-300"
              : "text-[#85470D] dark:text-amber-300"
          }`}
        >
          {withinBudget ? "OPTIMAL" : "ELEVATED"}
        </span>
      </div>
    </div>
  );
};
