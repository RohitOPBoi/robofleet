/**
 * Scene3D: Master WebGL 3D Digital Twin container for RoboFleet.
 * Integrates procedural racks, stations, AMRs, dynamic cameras, alert beacons,
 * performance diagnostics, 2D radar mini-map, and graceful WebGL2 fallback.
 */

import React, { useState, useEffect } from "react";
import { Canvas } from "@react-three/fiber";
import { AlertCircle } from "lucide-react";
import { setStore, useStore } from "../../store/useStore";
import { CameraController } from "./CameraController";
import { CameraHUD } from "./CameraHUD";
import { DiagnosticsOverlay } from "./DiagnosticsOverlay";
import { Environment3D } from "./Environment3D";
import { QualityController } from "./QualityController";
import { Racks3D } from "./Racks3D";
import { Robots3D } from "./Robots3D";
import { Stations3D } from "./Stations3D";
import { AlertBeacons3D } from "./AlertBeacons3D";
import { MiniMap2D } from "./MiniMap2D";

// WebGL2 support detection
function checkWebGL2(): boolean {
  if (typeof window === "undefined") return true;
  try {
    const canvas = document.createElement("canvas");
    return Boolean(window.WebGL2RenderingContext && canvas.getContext("webgl2"));
  } catch {
    return false;
  }
}

export const Scene3D: React.FC = () => {
  const [hasWebGL, setHasWebGL] = useState(true);
  const { staticWorld } = useStore();

  useEffect(() => {
    setHasWebGL(checkWebGL2());
  }, []);

  if (!hasWebGL) {
    return (
      <div className="flex-1 h-full w-full flex flex-col items-center justify-center bg-gray-950 p-6 text-center select-none">
        <div className="p-4 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 mb-3">
          <AlertCircle className="w-8 h-8" />
        </div>
        <h3 className="text-base font-bold text-white mb-1">WebGL2 Acceleration Unavailable</h3>
        <p className="text-xs text-gray-400 max-w-sm mb-4 leading-relaxed">
          Your browser or graphics environment does not support WebGL2 hardware acceleration.
          RoboFleet has safely preserved your session.
        </p>
        <button
          type="button"
          onClick={() => setStore({ viewMode: "2d" })}
          className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-black font-bold text-xs transition cursor-pointer"
        >
          Switch to 2D Live Map
        </button>
      </div>
    );
  }

  const width = staticWorld?.layout.width ?? 28;
  const height = staticWorld?.layout.height ?? 20;

  return (
    <div className="relative flex-1 h-full w-full bg-white overflow-hidden select-none">
      {/* Three.js R3F WebGL Canvas */}
      <Canvas
        shadows="percentage"
        camera={{ position: [width / 2 - 10, 16, height / 2 + 14], fov: 45 }}
        gl={{
          powerPreference: "high-performance",
          antialias: true,
          alpha: false,
        }}
        dpr={[1, 2]}
        onCreated={(state) => {
          state.gl.setClearColor("#FFFFFF");
        }}
      >
        <color attach="background" args={["#FFFFFF"]} />
        <Environment3D />
        <Racks3D />
        <Stations3D />
        <Robots3D />
        <AlertBeacons3D />
        <CameraController />
        <QualityController />
      </Canvas>

      {/* Camera HUD floating bar */}
      <CameraHUD />

      {/* MiniMap 2D Picture-in-Picture Radar */}
      <MiniMap2D />

      {/* Diagnostics HUD Overlay */}
      <DiagnosticsOverlay />
    </div>
  );
};

export default Scene3D;
