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
  Sparkles,
  Sun,
  Truck,
  Video,
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
      className="absolute top-4 left-4 z-20 flex items-center gap-1.5 bg-gray-950/85 border border-white/10 backdrop-blur-xl rounded-xl p-1.5 text-xs shadow-2xl select-none"
      onClick={(e) => e.stopPropagation()}
      onMouseDown={(e) => e.stopPropagation()}
    >
      {/* Camera Mode Segmented Pill */}
      <div className="flex items-center gap-0.5 bg-gray-900 border border-white/5 rounded-lg p-0.5 font-mono text-[11px]">
        <button
          type="button"
          onClick={() => setStore({ cameraMode: "orbit" })}
          className={`px-2 py-1 rounded-md transition cursor-pointer active:scale-95 flex items-center gap-1 ${
            cameraMode === "orbit"
              ? "bg-cyan-500 text-black font-extrabold shadow-sm shadow-cyan-500/40"
              : "text-gray-400 hover:text-white hover:bg-white/5"
          }`}
          title="Free Orbit Camera (Key: C to cycle)"
        >
          <Camera className="w-3.5 h-3.5" />
          <span>Orbit</span>
        </button>

        <button
          type="button"
          onClick={() => setStore({ cameraMode: "isometric" })}
          className={`px-2 py-1 rounded-md transition cursor-pointer active:scale-95 flex items-center gap-1 ${
            cameraMode === "isometric"
              ? "bg-cyan-500 text-black font-extrabold shadow-sm shadow-cyan-500/40"
              : "text-gray-400 hover:text-white hover:bg-white/5"
          }`}
          title="Top Isometric 45° Projection"
        >
          <Compass className="w-3.5 h-3.5" />
          <span>Iso</span>
        </button>

        <button
          type="button"
          onClick={() => setStore({ cameraMode: "follow" })}
          className={`px-2 py-1 rounded-md transition cursor-pointer active:scale-95 flex items-center gap-1 ${
            cameraMode === "follow"
              ? "bg-cyan-500 text-black font-extrabold shadow-sm shadow-cyan-500/40"
              : "text-gray-400 hover:text-white hover:bg-white/5"
          }`}
          title="Follow Selected AMR (Smoothed Chase)"
        >
          <MapPin className="w-3.5 h-3.5" />
          <span>Chase</span>
        </button>

        <button
          type="button"
          onClick={() => setStore({ cameraMode: "stations" })}
          className={`px-2 py-1 rounded-md transition cursor-pointer active:scale-95 ${
            cameraMode === "stations"
              ? "bg-cyan-500 text-black font-extrabold shadow-sm shadow-cyan-500/40"
              : "text-gray-400 hover:text-white hover:bg-white/5"
          }`}
          title="Station Booths Focus"
        >
          Stations
        </button>

        <button
          type="button"
          onClick={() => setStore({ cameraMode: "dispatch" })}
          className={`px-2 py-1 rounded-md transition cursor-pointer active:scale-95 flex items-center gap-1 ${
            cameraMode === "dispatch"
              ? "bg-cyan-500 text-black font-extrabold shadow-sm shadow-cyan-500/40"
              : "text-gray-400 hover:text-white hover:bg-white/5"
          }`}
          title="Dispatch Bay & Staging"
        >
          <Truck className="w-3.5 h-3.5" />
          <span>Dispatch</span>
        </button>

        <button
          type="button"
          onClick={() => setStore({ cameraMode: "cinematic" })}
          className={`px-2 py-1 rounded-md transition cursor-pointer active:scale-95 flex items-center gap-1 ${
            cameraMode === "cinematic"
              ? "bg-gradient-to-r from-purple-500 to-pink-500 text-white font-extrabold shadow-sm shadow-purple-500/40 animate-pulse"
              : "text-purple-400 hover:text-white hover:bg-white/5"
          }`}
          title="Cinematic Tour (Autocuts to live alerts)"
        >
          <Video className="w-3.5 h-3.5" />
          <span>Tour</span>
        </button>
      </div>

      <div className="h-4 w-px bg-white/10" />

      {/* Lighting Preset Selector */}
      <div className="flex items-center gap-0.5 bg-gray-900 border border-white/5 rounded-lg p-0.5 font-mono text-[11px]">
        <button
          type="button"
          onClick={() => setStore({ lightingPreset: "daylight" })}
          className={`p-1 rounded-md transition cursor-pointer ${
            lightingPreset === "daylight" ? "bg-amber-400 text-black font-bold shadow-sm" : "text-gray-400 hover:text-white"
          }`}
          title="Daylight Lighting (Key: L)"
        >
          <Sun className="w-3.5 h-3.5" />
        </button>

        <button
          type="button"
          onClick={() => setStore({ lightingPreset: "warm_evening" })}
          className={`p-1 rounded-md transition cursor-pointer ${
            lightingPreset === "warm_evening" ? "bg-amber-600 text-white font-bold shadow-sm" : "text-gray-400 hover:text-white"
          }`}
          title="Warm Evening Lighting (Key: L)"
        >
          <Sparkles className="w-3.5 h-3.5" />
        </button>

        <button
          type="button"
          onClick={() => setStore({ lightingPreset: "night_ops" })}
          className={`p-1 rounded-md transition cursor-pointer ${
            lightingPreset === "night_ops" ? "bg-blue-600 text-white font-bold shadow-sm" : "text-gray-400 hover:text-white"
          }`}
          title="Night Operations Cyber Lighting (Key: L)"
        >
          <Moon className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="h-4 w-px bg-white/10" />

      {/* Path Ribbons Toggle */}
      <button
        type="button"
        onClick={() => setStore({ show3DPaths: !show3DPaths })}
        className={`p-1.5 rounded-lg transition active:scale-95 cursor-pointer ${
          show3DPaths
            ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40"
            : "text-gray-400 hover:text-white hover:bg-white/5"
        }`}
        title="Toggle 3D Path Laser Ribbons"
      >
        <Eye className="w-3.5 h-3.5" />
      </button>

      {/* MiniMap Toggle */}
      <button
        type="button"
        onClick={() => setStore({ showMiniMap: !showMiniMap })}
        className={`p-1.5 rounded-lg transition active:scale-95 cursor-pointer ${
          showMiniMap
            ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40"
            : "text-gray-400 hover:text-white hover:bg-white/5"
        }`}
        title="Toggle 2D Picture-in-Picture Mini-Map"
      >
        <Layers className="w-3.5 h-3.5" />
      </button>

      {/* Diagnostics Toggle */}
      <button
        type="button"
        onClick={() => setStore({ showDiagnostics: !showDiagnostics })}
        className={`p-1.5 rounded-lg transition active:scale-95 cursor-pointer ${
          showDiagnostics
            ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
            : "text-gray-400 hover:text-white hover:bg-white/5"
        }`}
        title="Toggle Performance Diagnostics Overlay"
      >
        <Activity className="w-3.5 h-3.5" />
      </button>
    </div>
  );
};
