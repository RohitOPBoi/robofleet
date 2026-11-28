/**
 * CameraHUD: Floating controls for 3D Camera Modes, Lighting Presets,
 * Diagnostics Toggle, and Path Ribbons.
 */

import React from "react";
import {
  Activity,
  Camera,
  Compass,
  Eye,
  Layers,
  MapPin,
  Moon,
  Sun,
  Sunset,
  Truck,
  Video,
  Warehouse,
} from "lucide-react";
import { setStore, useStore } from "../../store/useStore";

export const CameraHUD: React.FC = () => {
  const {
    cameraMode,
    lightingPreset,
    show3DPaths,
    showDiagnostics,
    showMiniMap,
  } = useStore();

  return (
    <div
      className="absolute top-3 left-3 z-20 studio-card studio-enter stagger-1 flex flex-wrap items-center gap-1.5 rounded-2xl p-1.5 text-xs select-none max-w-[calc(100%-1.5rem)]"
      onClick={(e) => e.stopPropagation()}
      onMouseDown={(e) => e.stopPropagation()}
    >
      {/* Camera Mode Segmented Pill */}
      <div
        className="flex flex-wrap items-center gap-0.5 rounded-[10px] p-0.5 border text-[11px] font-medium"
        style={{
          background: "var(--studio-surface-subtle)",
          borderColor: "var(--studio-border)",
        }}
      >
        <button
          type="button"
          onClick={() => setStore({ cameraMode: "orbit" })}
          aria-label="Free orbit camera"
          aria-pressed={cameraMode === "orbit"}
          className={`studio-btn px-2.5 py-1 rounded-lg cursor-pointer flex items-center gap-1.5 ${
            cameraMode === "orbit"
              ? "bg-[#D9533B] text-[#FFFBF8] font-semibold shadow-sm"
              : "text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-elevated)]"
          }`}
          title="Free Orbit Camera (Key: C to cycle)"
        >
          <Camera className="w-3.5 h-3.5" strokeWidth={1.5} />
          <span>Orbit</span>
        </button>

        <button
          type="button"
          onClick={() => setStore({ cameraMode: "isometric" })}
          aria-label="Top isometric 45 degree projection"
          aria-pressed={cameraMode === "isometric"}
          className={`studio-btn px-2.5 py-1 rounded-lg cursor-pointer flex items-center gap-1.5 ${
            cameraMode === "isometric"
              ? "bg-[#D9533B] text-[#FFFBF8] font-semibold shadow-sm"
              : "text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-elevated)]"
          }`}
          title="Top Isometric 45° Projection"
        >
          <Compass className="w-3.5 h-3.5" strokeWidth={1.5} />
          <span>Iso</span>
        </button>

        <button
          type="button"
          onClick={() => setStore({ cameraMode: "follow" })}
          aria-label="Follow selected AMR chase camera"
          aria-pressed={cameraMode === "follow"}
          className={`studio-btn px-2.5 py-1 rounded-lg cursor-pointer flex items-center gap-1.5 ${
            cameraMode === "follow"
              ? "bg-[#D9533B] text-[#FFFBF8] font-semibold shadow-sm"
              : "text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-elevated)]"
          }`}
          title="Follow Selected AMR (Smoothed Chase)"
        >
          <MapPin className="w-3.5 h-3.5" strokeWidth={1.5} />
          <span>Chase</span>
        </button>

        <button
          type="button"
          onClick={() => setStore({ cameraMode: "stations" })}
          aria-label="Focus picking stations"
          aria-pressed={cameraMode === "stations"}
          className={`studio-btn px-2.5 py-1 rounded-lg cursor-pointer flex items-center gap-1.5 ${
            cameraMode === "stations"
              ? "bg-[#D9533B] text-[#FFFBF8] font-semibold shadow-sm"
              : "text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-elevated)]"
          }`}
          title="Station Booths Focus"
        >
          <Warehouse className="w-3.5 h-3.5" strokeWidth={1.5} />
          <span>Stations</span>
        </button>

        <button
          type="button"
          onClick={() => setStore({ cameraMode: "dispatch" })}
          aria-label="Focus dispatch bay and staging"
          aria-pressed={cameraMode === "dispatch"}
          className={`studio-btn px-2.5 py-1 rounded-lg cursor-pointer flex items-center gap-1.5 ${
            cameraMode === "dispatch"
              ? "bg-[#D9533B] text-[#FFFBF8] font-semibold shadow-sm"
              : "text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-elevated)]"
          }`}
          title="Dispatch Bay & Staging"
        >
          <Truck className="w-3.5 h-3.5" strokeWidth={1.5} />
          <span>Dispatch</span>
        </button>

        <button
          type="button"
          onClick={() => setStore({ cameraMode: "cinematic" })}
          aria-label="Cinematic camera tour"
          aria-pressed={cameraMode === "cinematic"}
          className={`studio-btn px-2.5 py-1 rounded-lg cursor-pointer flex items-center gap-1.5 ${
            cameraMode === "cinematic"
              ? "bg-[#D9533B] text-[#FFFBF8] font-semibold shadow-sm"
              : "text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-elevated)]"
          }`}
          title="Cinematic Tour (Autocuts to live alerts)"
        >
          <Video className="w-3.5 h-3.5" strokeWidth={1.5} />
          <span>Tour</span>
        </button>
      </div>

      <div className="h-4 w-px bg-[var(--studio-border-strong)]" />

      {/* Lighting Preset Selector */}
      <div
        className="flex items-center gap-0.5 rounded-[10px] p-0.5 border"
        style={{
          background: "var(--studio-surface-subtle)",
          borderColor: "var(--studio-border)",
        }}
      >
        <button
          type="button"
          onClick={() => setStore({ lightingPreset: "daylight" })}
          aria-label="Daylight lighting preset"
          aria-pressed={lightingPreset === "daylight"}
          className={`studio-btn p-1.5 rounded-lg cursor-pointer ${
            lightingPreset === "daylight"
              ? "bg-[#D9533B] text-[#FFFBF8] shadow-sm"
              : "text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-elevated)]"
          }`}
          title="Daylight Lighting (Key: L)"
        >
          <Sun className="w-3.5 h-3.5" strokeWidth={1.5} />
        </button>

        <button
          type="button"
          onClick={() => setStore({ lightingPreset: "warm_evening" })}
          aria-label="Warm evening lighting preset"
          aria-pressed={lightingPreset === "warm_evening"}
          className={`studio-btn p-1.5 rounded-lg cursor-pointer ${
            lightingPreset === "warm_evening"
              ? "bg-[#D9533B] text-[#FFFBF8] shadow-sm"
              : "text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-elevated)]"
          }`}
          title="Warm Evening Lighting (Key: L)"
        >
          <Sunset className="w-3.5 h-3.5" strokeWidth={1.5} />
        </button>

        <button
          type="button"
          onClick={() => setStore({ lightingPreset: "night_ops" })}
          aria-label="Night operations lighting preset"
          aria-pressed={lightingPreset === "night_ops"}
          className={`studio-btn p-1.5 rounded-lg cursor-pointer ${
            lightingPreset === "night_ops"
              ? "bg-[#D9533B] text-[#FFFBF8] shadow-sm"
              : "text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-elevated)]"
          }`}
          title="Night Operations Lighting (Key: L)"
        >
          <Moon className="w-3.5 h-3.5" strokeWidth={1.5} />
        </button>
      </div>

      <div className="h-4 w-px bg-[var(--studio-border-strong)]" />

      {/* Path Ribbons Toggle */}
      <button
        type="button"
        onClick={() => setStore({ show3DPaths: !show3DPaths })}
        aria-label="Toggle 3D path ribbons"
        aria-pressed={show3DPaths}
        className={`studio-btn p-1.5 rounded-[10px] border cursor-pointer ${
          show3DPaths
            ? "bg-[#D9533B] text-[#FFFBF8] border-[#D9533B] shadow-sm"
            : "border-transparent text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-subtle)]"
        }`}
        title="Toggle 3D Path Ribbons"
      >
        <Eye className="w-3.5 h-3.5" strokeWidth={1.5} />
      </button>

      {/* MiniMap Toggle */}
      <button
        type="button"
        onClick={() => setStore({ showMiniMap: !showMiniMap })}
        aria-label="Toggle 2D radar mini-map"
        aria-pressed={showMiniMap}
        className={`studio-btn p-1.5 rounded-[10px] border cursor-pointer ${
          showMiniMap
            ? "bg-[#D9533B] text-[#FFFBF8] border-[#D9533B] shadow-sm"
            : "border-transparent text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-subtle)]"
        }`}
        title="Toggle 2D Picture-in-Picture Mini-Map"
      >
        <Layers className="w-3.5 h-3.5" strokeWidth={1.5} />
      </button>

      {/* Diagnostics Toggle */}
      <button
        type="button"
        onClick={() => setStore({ showDiagnostics: !showDiagnostics })}
        aria-label="Toggle performance diagnostics overlay"
        aria-pressed={showDiagnostics}
        className={`studio-btn p-1.5 rounded-[10px] border cursor-pointer ${
          showDiagnostics
            ? "bg-[#D9533B] text-[#FFFBF8] border-[#D9533B] shadow-sm"
            : "border-transparent text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-subtle)]"
        }`}
        title="Toggle Performance Diagnostics Overlay"
      >
        <Activity className="w-3.5 h-3.5" strokeWidth={1.5} />
      </button>
    </div>
  );
};
