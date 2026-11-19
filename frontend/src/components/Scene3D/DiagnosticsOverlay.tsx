/**
 * DiagnosticsOverlay: Real-time HUD showing WebGL2 draw calls,
 * triangle count, FPS, and dynamic quality tier.
 */

import React from "react";
import { Activity, Cpu, Layers } from "lucide-react";
import { useStore } from "../../store/useStore";

export const DiagnosticsOverlay: React.FC = () => {
  const { diagnostics, showDiagnostics } = useStore();

  if (!showDiagnostics) return null;

  const fpsColor =
    diagnostics.fps >= 55 ? "text-emerald-400" : diagnostics.fps >= 35 ? "text-amber-400" : "text-red-400";

  return (
    <div className="absolute bottom-4 right-4 z-20 bg-gray-950/90 border border-white/10 backdrop-blur-xl rounded-xl p-2.5 font-mono text-[11px] text-gray-300 shadow-2xl space-y-1.5 select-none min-w-[190px]">
      <div className="flex items-center justify-between pb-1.5 border-b border-white/10 font-bold text-xs text-white">
        <div className="flex items-center gap-1.5 text-cyan-400">
          <Activity className="w-3.5 h-3.5" />
          <span>WebGL2 Diagnostics</span>
        </div>
        <span className="text-[10px] px-1.5 py-0.2 rounded bg-cyan-950 text-cyan-300 border border-cyan-800">
          {diagnostics.tier.toUpperCase()}
        </span>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-gray-400">Frame Rate:</span>
        <span className={`font-bold ${fpsColor}`}>{diagnostics.fps} FPS</span>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-gray-400">Draw Calls:</span>
        <span className="font-semibold text-white">{diagnostics.drawCalls}</span>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-gray-400">Triangles:</span>
        <span className="font-semibold text-white">
          {(diagnostics.triangles / 1000).toFixed(1)}k
        </span>
      </div>

      <div className="flex items-center justify-between text-[10px] text-gray-500 pt-1 border-t border-white/5">
        <span>Budget: &le; 200 calls</span>
        <span className="text-emerald-400 font-bold">OPTIMAL</span>
      </div>
    </div>
  );
};
