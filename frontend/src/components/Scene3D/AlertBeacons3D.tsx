/**
 * AlertBeacons3D: Vertical volumetric light beams and pulsing ground rings
 * rendered at active alert coordinates in the 3D dark store.
 */

import React, { useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import type { Alert } from "../../types/generated";
import { useStore } from "../../store/useStore";

const beamGeometry = new THREE.CylinderGeometry(0.08, 0.25, 5.0, 16);
const diamondGeometry = new THREE.OctahedronGeometry(0.2, 0);
const ringGeometry = new THREE.RingGeometry(0.3, 0.45, 24);

const SingleBeacon: React.FC<{ alert: Alert }> = ({ alert }) => {
  const ringRef = useRef<THREE.Mesh | null>(null);
  const diamondRef = useRef<THREE.Mesh | null>(null);

  const ax = alert.coord?.x ?? 0;
  const az = alert.coord?.y ?? 0;
  const isCritical = alert.severity === "CRITICAL";
  const beamColor = isCritical ? "#EF4444" : "#F59E0B";

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (ringRef.current) {
      const s = 1.0 + 0.35 * Math.sin(t * 5.0);
      ringRef.current.scale.set(s, s, 1);
    }
    if (diamondRef.current) {
      diamondRef.current.rotation.y = t * 2.0;
    }
  });

  return (
    <group position={[ax, 0, az]}>
      {/* Concentric Ground Pulse Ring */}
      <mesh ref={ringRef} geometry={ringGeometry} rotation-x={-Math.PI / 2} position={[0, 0.03, 0]}>
        <meshBasicMaterial color={beamColor} transparent opacity={0.7} side={THREE.DoubleSide} />
      </mesh>

      {/* Vertical Light Beam */}
      <mesh geometry={beamGeometry} position={[0, 2.5, 0]}>
        <meshBasicMaterial color={beamColor} transparent opacity={0.35} />
      </mesh>

      {/* Floating Beacon Diamond Top */}
      <mesh ref={diamondRef} geometry={diamondGeometry} position={[0, 5.2, 0]}>
        <meshBasicMaterial color={beamColor} />
      </mesh>
    </group>
  );
};

export const AlertBeacons3D: React.FC = () => {
  const { alerts, activeFaults, robots } = useStore();
  const activeAlerts = alerts.filter((a) => !a.cleared && a.coord);

  // Convert coordinate-based chaos faults into visual alert beacons
  const faultBeacons = activeFaults.flatMap((f) => {
    if (f.target_id.startsWith("cell:")) {
      const parts = f.target_id.replace("cell:", "").split(",");
      if (parts.length === 2) {
        return [
          {
            id: f.fault_id,
            coord: { x: Number(parts[0]) || 0, y: Number(parts[1]) || 0 },
            severity: "CRITICAL" as const,
            category: "CHAOS_FAULT",
            message: `Aisle Blockage: ${f.fault_type}`,
            requires_human: true,
            cleared: false,
            tick: f.injected_tick,
          },
        ];
      }
    }
    return [];
  });

  const allBeacons = [...activeAlerts, ...faultBeacons];

  return (
    <group>
      {allBeacons.map((alert) => (
        <SingleBeacon key={alert.id} alert={alert as any} />
      ))}
    </group>
  );
};
