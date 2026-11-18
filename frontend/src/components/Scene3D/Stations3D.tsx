/**
 * Stations3D: Picking station booths, charging hubs, dispatch staging bays,
 * and supervisor desk with computer terminal glow.
 */

import React, { useMemo } from "react";
import * as THREE from "three";
import { useStore } from "../../store/useStore";

const getPos = (obj: any): { x: number; y: number } => {
  if (!obj) return { x: 0, y: 0 };
  if (obj.pos) return { x: Number(obj.pos.x) || 0, y: Number(obj.pos.y) || 0 };
  if (obj.coord) return { x: Number(obj.coord.x) || 0, y: Number(obj.coord.y) || 0 };
  return { x: Number(obj.x) || 0, y: Number(obj.y) || 0 };
};

// Geometries
const deskGeometry = new THREE.BoxGeometry(0.85, 0.8, 0.85);
const monitorGeometry = new THREE.BoxGeometry(0.4, 0.28, 0.05);
const standGeometry = new THREE.CylinderGeometry(0.02, 0.04, 0.15, 8);
const chargerPadGeometry = new THREE.CylinderGeometry(0.42, 0.44, 0.06, 16);
const chargerPillarGeometry = new THREE.BoxGeometry(0.18, 0.9, 0.18);
const humanTorsoGeometry = new THREE.CylinderGeometry(0.14, 0.16, 0.45, 12);
const humanHeadGeometry = new THREE.SphereGeometry(0.1, 12, 12);

// Materials
const stationDeskMat = new THREE.MeshStandardMaterial({
  color: 0x064e3b,
  roughness: 0.4,
  metalness: 0.4,
});

const monitorBezelMat = new THREE.MeshStandardMaterial({ color: 0x111827, roughness: 0.3 });
const monitorScreenMat = new THREE.MeshBasicMaterial({ color: 0x10b981 });
const supervisorScreenMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8 });

const chargerBaseMat = new THREE.MeshStandardMaterial({
  color: 0x78350f,
  roughness: 0.3,
  metalness: 0.6,
});
const chargerGlowMat = new THREE.MeshBasicMaterial({ color: 0xf59e0b });

const dispatchCounterMat = new THREE.MeshStandardMaterial({
  color: 0x4c1d95,
  roughness: 0.4,
  metalness: 0.3,
});

const supervisorDeskMat = new THREE.MeshStandardMaterial({
  color: 0x1e293b,
  roughness: 0.5,
  metalness: 0.5,
});

const workerClothingMat = new THREE.MeshStandardMaterial({ color: 0x0284c7, roughness: 0.7 });
const supervisorClothingMat = new THREE.MeshStandardMaterial({ color: 0x64748b, roughness: 0.6 });

export const Stations3D: React.FC = () => {
  const { staticWorld } = useStore();
  const layout = staticWorld?.layout;

  // Picking Stations
  const stations = useMemo(() => {
    const list = Array.isArray((layout as any)?.stations)
      ? (layout as any).stations
      : Array.isArray((layout as any)?.pick_stations)
      ? (layout as any).pick_stations
      : [];
    return list.map(getPos);
  }, [layout]);

  // Chargers
  const chargers = useMemo(() => {
    const list = Array.isArray((layout as any)?.chargers) ? (layout as any).chargers : [];
    return list.map(getPos);
  }, [layout]);

  // Dispatch Bay Cells
  const dispatchCells = useMemo(() => {
    const list = Array.isArray((layout as any)?.dispatch_cells) ? (layout as any).dispatch_cells : [];
    return list.map(getPos);
  }, [layout]);

  // Supervisor Cells
  const supervisorCells = useMemo(() => {
    const list = Array.isArray((layout as any)?.supervisor_cells) ? (layout as any).supervisor_cells : [];
    return list.map(getPos);
  }, [layout]);

  return (
    <group>
      {/* 1. Picking Stations */}
      {stations.map((pos: { x: number; y: number }, i: number) => (
        <group key={`station-${i}`} position={[pos.x, 0, pos.y]}>
          {/* Station Desk Counter */}
          <mesh geometry={deskGeometry} material={stationDeskMat} position={[0, 0.4, 0]} castShadow receiveShadow />

          {/* Computer Monitor */}
          <mesh geometry={standGeometry} material={monitorBezelMat} position={[0, 0.88, -0.1]} />
          <mesh geometry={monitorGeometry} material={monitorBezelMat} position={[0, 1.05, -0.1]} castShadow>
            <mesh geometry={monitorGeometry} material={monitorScreenMat} position={[0, 0, 0.03]} scale={[0.9, 0.85, 0.2]} />
          </mesh>

          {/* Simulated Worker Figure */}
          <group position={[0, 0.8, -0.45]}>
            <mesh geometry={humanTorsoGeometry} material={workerClothingMat} position={[0, 0.4, 0]} castShadow />
            <mesh geometry={humanHeadGeometry} material={workerClothingMat} position={[0, 0.72, 0]} castShadow />
          </group>

          {/* Queue Dock Indicator Ring */}
          <mesh rotation-x={-Math.PI / 2} position={[0, 0.01, 0.8]}>
            <ringGeometry args={[0.3, 0.38, 16]} />
            <meshBasicMaterial color="#10B981" transparent opacity={0.6} />
          </mesh>
        </group>
      ))}

      {/* 2. Charging Bank */}
      {chargers.map((pos: { x: number; y: number }, i: number) => (
        <group key={`charger-${i}`} position={[pos.x, 0, pos.y]}>
          {/* Charging Floor Pad */}
          <mesh geometry={chargerPadGeometry} material={chargerBaseMat} position={[0, 0.03, 0]} receiveShadow />
          <mesh rotation-x={-Math.PI / 2} position={[0, 0.065, 0]}>
            <ringGeometry args={[0.2, 0.35, 16]} />
            <meshBasicMaterial color="#F59E0B" />
          </mesh>

          {/* Power Pillar */}
          <mesh geometry={chargerPillarGeometry} material={chargerBaseMat} position={[0, 0.48, -0.3]} castShadow>
            <mesh position={[0, 0.3, 0.1]}>
              <sphereGeometry args={[0.04, 8, 8]} />
              <meshBasicMaterial color="#F59E0B" />
            </mesh>
          </mesh>
        </group>
      ))}

      {/* 3. Dispatch Bay Counter */}
      {dispatchCells.map((pos: { x: number; y: number }, i: number) => (
        <group key={`dispatch-${i}`} position={[pos.x, 0, pos.y]}>
          <mesh geometry={deskGeometry} material={dispatchCounterMat} position={[0, 0.4, 0]} castShadow receiveShadow />
          <mesh rotation-x={-Math.PI / 2} position={[0, 0.01, 0]}>
            <planeGeometry args={[0.9, 0.9]} />
            <meshBasicMaterial color="#8B5CF6" transparent opacity={0.2} />
          </mesh>
        </group>
      ))}

      {/* 4. Supervisor Desk & Figure */}
      {supervisorCells.map((pos: { x: number; y: number }, i: number) => (
        <group key={`supervisor-${i}`} position={[pos.x, 0, pos.y]}>
          <mesh geometry={deskGeometry} material={supervisorDeskMat} position={[0, 0.4, 0]} castShadow receiveShadow />

          {/* Dual Monitors */}
          <group position={[-0.15, 0.95, -0.05]} rotation-y={0.2}>
            <mesh geometry={monitorGeometry} material={monitorBezelMat}>
              <mesh geometry={monitorGeometry} material={supervisorScreenMat} position={[0, 0, 0.03]} scale={[0.9, 0.85, 0.2]} />
            </mesh>
          </group>
          <group position={[0.18, 0.95, -0.05]} rotation-y={-0.2}>
            <mesh geometry={monitorGeometry} material={monitorBezelMat}>
              <mesh geometry={monitorGeometry} material={supervisorScreenMat} position={[0, 0, 0.03]} scale={[0.9, 0.85, 0.2]} />
            </mesh>
          </group>

          {/* Supervisor Figure */}
          <group position={[0, 0.8, -0.45]}>
            <mesh geometry={humanTorsoGeometry} material={supervisorClothingMat} position={[0, 0.4, 0]} castShadow />
            <mesh geometry={humanHeadGeometry} material={supervisorClothingMat} position={[0, 0.72, 0]} castShadow />
          </group>
        </group>
      ))}
    </group>
  );
};
