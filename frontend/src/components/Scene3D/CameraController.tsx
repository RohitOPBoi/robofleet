/**
 * CameraController: High-performance camera management for RoboFleet 3D.
 * Supports: Orbit, Top Isometric, Follow AMR, Stations Preset, Dispatch Preset,
 * and Cinematic Tour with automated alert cuts, manual interruption handling,
 * keyboard controls, and reduced-motion adaptation.
 */

import React, { useEffect, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { setStore, useStore } from "../../store/useStore";

interface Waypoint {
  pos: THREE.Vector3;
  target: THREE.Vector3;
  duration: number; // seconds
}

const CAMERA_MODES: Array<"orbit" | "isometric" | "follow" | "stations" | "dispatch" | "cinematic"> = [
  "orbit",
  "isometric",
  "follow",
  "stations",
  "dispatch",
  "cinematic",
];

const LIGHTING_PRESETS: Array<"daylight" | "warm_evening" | "night_ops"> = [
  "daylight",
  "warm_evening",
  "night_ops",
];

export const CameraController: React.FC = () => {
  const { camera } = useThree();
  const controlsRef = useRef<any>(null);

  const {
    cameraMode,
    lightingPreset,
    selectedRobotId,
    robots,
    alerts,
    staticWorld,
  } = useStore();

  const layout = staticWorld?.layout;
  const storeWidth = layout?.width ?? 28;
  const storeHeight = layout?.height ?? 20;
  const centerX = storeWidth / 2;
  const centerZ = storeHeight / 2;

  // Waypoints for Cinematic Tour
  const waypoints = useRef<Waypoint[]>([
    {
      pos: new THREE.Vector3(centerX - 10, 14, centerZ + 12),
      target: new THREE.Vector3(centerX, 0, centerZ),
      duration: 6,
    },
    {
      pos: new THREE.Vector3(12, 4.5, 4),
      target: new THREE.Vector3(12, 0.5, 12),
      duration: 7,
    },
    {
      pos: new THREE.Vector3(10, 6, 22),
      target: new THREE.Vector3(10, 0.5, 18),
      duration: 6,
    },
    {
      pos: new THREE.Vector3(23, 4.5, 1),
      target: new THREE.Vector3(26, 0.5, 6),
      duration: 6,
    },
  ]);

  const tourIndex = useRef(0);
  const tourProgress = useRef(0);
  const alertCutTimer = useRef<number | null>(null);
  const lastHandledAlertId = useRef<string | null>(null);

  // Smooth lerp targets
  const currentLookAt = useRef(new THREE.Vector3(centerX, 0, centerZ));

  // Initialize camera position on mode change
  useEffect(() => {
    const prefersReducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (cameraMode === "isometric") {
      const pos = new THREE.Vector3(centerX - 12, 16, centerZ + 12);
      const target = new THREE.Vector3(centerX, 0, centerZ);
      camera.position.copy(pos);
      currentLookAt.current.copy(target);
      camera.lookAt(target);
      if (controlsRef.current) controlsRef.current.target.copy(target);
    } else if (cameraMode === "stations") {
      const pos = new THREE.Vector3(10, 6.5, 23);
      const target = new THREE.Vector3(10, 0.5, 18);
      camera.position.copy(pos);
      currentLookAt.current.copy(target);
      camera.lookAt(target);
      if (controlsRef.current) controlsRef.current.target.copy(target);
    } else if (cameraMode === "dispatch") {
      const pos = new THREE.Vector3(4, 5, 22);
      const target = new THREE.Vector3(4, 0.5, 18);
      camera.position.copy(pos);
      currentLookAt.current.copy(target);
      camera.lookAt(target);
      if (controlsRef.current) controlsRef.current.target.copy(target);
    } else if (cameraMode === "orbit") {
      if (controlsRef.current) {
        controlsRef.current.target.set(centerX, 0, centerZ);
      }
    }
  }, [cameraMode, centerX, centerZ, camera]);

  // Global Keyboard camera controls (C: cycle cameras, L: cycle lighting, R: reset, Arrows: pan)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      if (e.code === "KeyC") {
        e.preventDefault();
        const nextIdx = (CAMERA_MODES.indexOf(cameraMode) + 1) % CAMERA_MODES.length;
        setStore({ cameraMode: CAMERA_MODES[nextIdx] });
      } else if (e.code === "KeyL") {
        e.preventDefault();
        const nextIdx = (LIGHTING_PRESETS.indexOf(lightingPreset) + 1) % LIGHTING_PRESETS.length;
        setStore({ lightingPreset: LIGHTING_PRESETS[nextIdx] });
      } else if (e.code === "KeyR") {
        e.preventDefault();
        camera.position.set(centerX - 10, 16, centerZ + 14);
        currentLookAt.current.set(centerX, 0, centerZ);
        camera.lookAt(currentLookAt.current);
        if (controlsRef.current) {
          controlsRef.current.target.set(centerX, 0, centerZ);
        }
        setStore({ cameraMode: "orbit" });
      } else if (cameraMode === "orbit" && controlsRef.current) {
        const panStep = 1.0;
        if (e.key === "ArrowLeft") {
          camera.position.x -= panStep;
          controlsRef.current.target.x -= panStep;
        } else if (e.key === "ArrowRight") {
          camera.position.x += panStep;
          controlsRef.current.target.x += panStep;
        } else if (e.key === "ArrowUp") {
          camera.position.z -= panStep;
          controlsRef.current.target.z -= panStep;
        } else if (e.key === "ArrowDown") {
          camera.position.z += panStep;
          controlsRef.current.target.z += panStep;
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [cameraMode, lightingPreset, centerX, centerZ, camera]);

  // Frame loop camera update
  useFrame((_, delta) => {
    const prefersReducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // 1. Follow Selected Robot Camera Mode
    if (cameraMode === "follow" && selectedRobotId && robots[selectedRobotId]) {
      const r = robots[selectedRobotId];
      let rx = r.coord?.x ?? 0;
      let rz = r.coord?.y ?? 0;
      if (r.motion?.from_coord && r.motion?.to_coord) {
        const prog = Math.max(0, Math.min(1, r.motion.progress ?? 0));
        rx = r.motion.from_coord.x + (r.motion.to_coord.x - r.motion.from_coord.x) * prog;
        rz = r.motion.from_coord.y + (r.motion.to_coord.y - r.motion.from_coord.y) * prog;
      }

      const headingRad = ((r.heading_deg ?? 0) * Math.PI) / 180;
      const targetPos = new THREE.Vector3(
        rx - Math.cos(headingRad) * 2.8,
        2.2,
        rz - Math.sin(headingRad) * 2.8
      );
      const targetLookAt = new THREE.Vector3(rx, 0.4, rz);

      if (prefersReducedMotion) {
        camera.position.copy(targetPos);
        currentLookAt.current.copy(targetLookAt);
      } else {
        camera.position.lerp(targetPos, delta * 3.5);
        currentLookAt.current.lerp(targetLookAt, delta * 4.0);
      }
      camera.lookAt(currentLookAt.current);

      if (controlsRef.current) {
        controlsRef.current.target.copy(currentLookAt.current);
      }
      return;
    }

    // 2. Cinematic Tour Camera Mode
    if (cameraMode === "cinematic") {
      // Check for incoming uncleared critical or warn alerts
      const activeAlert = alerts.find((a) => !a.cleared && a.coord);
      if (activeAlert && activeAlert.id !== lastHandledAlertId.current && alertCutTimer.current === null) {
        lastHandledAlertId.current = activeAlert.id;
        alertCutTimer.current = 4.0; // dwell for 4 seconds on alert
      }

      if (alertCutTimer.current !== null && alertCutTimer.current > 0) {
        alertCutTimer.current -= delta;
        if (activeAlert?.coord) {
          const ax = activeAlert.coord.x;
          const az = activeAlert.coord.y;
          const alertCamPos = new THREE.Vector3(ax - 2.5, 4.0, az + 3.0);
          const alertTarget = new THREE.Vector3(ax, 0.5, az);

          if (prefersReducedMotion) {
            camera.position.copy(alertCamPos);
            currentLookAt.current.copy(alertTarget);
          } else {
            camera.position.lerp(alertCamPos, delta * 2.5);
            currentLookAt.current.lerp(alertTarget, delta * 3.0);
          }
          camera.lookAt(currentLookAt.current);
          return;
        }
      } else {
        alertCutTimer.current = null;
      }

      // Loop through waypoints
      const pts = waypoints.current;
      const curr = pts[tourIndex.current];
      const next = pts[(tourIndex.current + 1) % pts.length];

      tourProgress.current += delta / curr.duration;
      if (tourProgress.current >= 1.0) {
        tourProgress.current = 0;
        tourIndex.current = (tourIndex.current + 1) % pts.length;
      }

      // Smooth cosine easing
      const t = 0.5 - 0.5 * Math.cos(tourProgress.current * Math.PI);
      const interpolatedPos = new THREE.Vector3().lerpVectors(curr.pos, next.pos, t);
      const interpolatedTarget = new THREE.Vector3().lerpVectors(curr.target, next.target, t);

      if (prefersReducedMotion) {
        camera.position.copy(interpolatedPos);
        currentLookAt.current.copy(interpolatedTarget);
      } else {
        camera.position.lerp(interpolatedPos, delta * 2.0);
        currentLookAt.current.lerp(interpolatedTarget, delta * 2.5);
      }
      camera.lookAt(currentLookAt.current);

      if (controlsRef.current) {
        controlsRef.current.target.copy(currentLookAt.current);
      }
    }
  });

  // Manual drag in cinematic mode or chase mode switches back to orbit
  const handleStartInteraction = () => {
    if (cameraMode === "cinematic" || cameraMode === "follow") {
      setStore({ cameraMode: "orbit" });
    }
  };

  return (
    <OrbitControls
      ref={controlsRef}
      makeDefault
      enableDamping
      dampingFactor={0.08}
      minDistance={3}
      maxDistance={45}
      maxPolarAngle={Math.PI / 2.05} // Do not dip below ground plane
      onStart={handleStartInteraction}
    />
  );
};
