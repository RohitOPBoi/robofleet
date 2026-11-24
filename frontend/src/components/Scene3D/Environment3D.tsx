/**
 * Environment3D: Procedural dark store environment with lighting presets,
 * instanced floor tiles, thermal zone overlays, and boundary walls.
 */

import React, { useMemo } from "react";
import * as THREE from "three";
import { useStore } from "../../store/useStore";

export const Environment3D: React.FC = () => {
  const { staticWorld, lightingPreset, activeOverlays } = useStore();
  const layout = staticWorld?.layout;

  const width = layout?.width ?? 28;
  const height = layout?.height ?? 20;

  // 1. Lighting Presets Configuration (Crisp Light Theme default)
  const lights = useMemo(() => {
    switch (lightingPreset) {
      case "warm_evening":
        return {
          ambientColor: "#FEF3C7",
          ambientIntensity: 0.75,
          sunColor: "#FDE68A",
          sunIntensity: 1.6,
          sunPos: [width - 5, 18, height + 8] as [number, number, number],
          shadowBias: -0.0005,
        };
      case "night_ops":
        return {
          ambientColor: "#1E293B",
          ambientIntensity: 0.45,
          sunColor: "#38BDF8",
          sunIntensity: 1.3,
          sunPos: [width / 2, 14, height / 2] as [number, number, number],
          shadowBias: -0.0005,
        };
      case "daylight":
      default:
        return {
          ambientColor: "#FFFFFF",
          ambientIntensity: 0.85,
          sunColor: "#FFFFFF",
          sunIntensity: 1.8,
          sunPos: [width / 2, 22, height / 2 + 10] as [number, number, number],
          shadowBias: -0.0005,
        };
    }
  }, [lightingPreset, width, height]);

  // 2. Thermal Zone Floor Slabs
  const zoneSlabs = useMemo(() => {
    const cells = (layout as any)?.cells;
    if (!activeOverlays.showZones || !Array.isArray(cells)) return [];
    const list: { x: number; z: number; type: string }[] = [];

    cells.forEach((cell: any) => {
      if (cell.zone === "CHILLED" || cell.zone === "FROZEN") {
        const pos = cell.pos || cell.coord || { x: 0, y: 0 };
        list.push({ x: pos.x, z: pos.y, type: cell.zone });
      }
    });
    return list;
  }, [activeOverlays.showZones, layout]);

  // 3. Parking Bay Floor Markings
  const parkingBays: { x: number; z: number }[] = useMemo(() => {
    const list = Array.isArray((layout as any)?.parking_cells) ? (layout as any).parking_cells : [];
    return list.map((c: any) => ({
      x: Number(c.x ?? c.pos?.x ?? 0),
      z: Number(c.y ?? c.pos?.y ?? 0),
    }));
  }, [layout]);

  return (
    <group>
      {/* Lighting Rig */}
      <ambientLight color={lights.ambientColor} intensity={lights.ambientIntensity} />
      <directionalLight
        position={lights.sunPos}
        color={lights.sunColor}
        intensity={lights.sunIntensity}
        castShadow
        shadow-mapSize={[1024, 1024]}
        shadow-camera-near={0.5}
        shadow-camera-far={60}
        shadow-camera-left={-width}
        shadow-camera-right={width}
        shadow-camera-top={height}
        shadow-camera-bottom={-height}
        shadow-bias={lights.shadowBias}
      />
      <hemisphereLight
        args={[lights.sunColor, "#E2E8F0", 0.5]}
      />

      {/* Main Ground Cleanroom Epoxy White Slab */}
      <mesh
        rotation-x={-Math.PI / 2}
        position={[width / 2 - 0.5, -0.01, height / 2 - 0.5]}
      >
        <planeGeometry args={[500, 500]} />
        <meshBasicMaterial color="#FFFFFF" />
      </mesh>

      {/* Warehouse Interior Polished White Epoxy Deck */}
      <mesh
        rotation-x={-Math.PI / 2}
        position={[width / 2 - 0.5, 0.001, height / 2 - 0.5]}
      >
        <planeGeometry args={[width + 0.2, height + 0.2]} />
        <meshBasicMaterial color="#FFFFFF" />
      </mesh>

      {/* Crisp Subtle Light Gray Architectural Floor Grid */}
      <gridHelper
        args={[Math.max(width, height) * 2, Math.max(width, height) * 2, 0xcbd5e1, 0xf1f5f9]}
        position={[width / 2 - 0.5, 0.002, height / 2 - 0.5]}
      />

      {/* Cross-Aisle Safety Demarcation Lines (High-Visibility Crisp Amber/Cyan) */}
      <mesh position={[width / 2 - 0.5, 0.003, 3]} rotation-x={-Math.PI / 2}>
        <planeGeometry args={[width - 2, 0.08]} />
        <meshBasicMaterial color="#F59E0B" />
      </mesh>
      <mesh position={[width / 2 - 0.5, 0.003, height - 3]} rotation-x={-Math.PI / 2}>
        <planeGeometry args={[width - 2, 0.08]} />
        <meshBasicMaterial color="#06B6D4" />
      </mesh>

      {/* Perimeter Boundary Walls (Clean Modern White with Vibrant Cyan Trim) */}
      <group>
        {/* North Wall */}
        <mesh position={[width / 2 - 0.5, 1.2, -1]} castShadow receiveShadow>
          <boxGeometry args={[width + 2, 2.4, 0.4]} />
          <meshStandardMaterial color="#F8FAFC" roughness={0.3} metalness={0.1} />
        </mesh>
        <mesh position={[width / 2 - 0.5, 0.1, -0.78]}>
          <boxGeometry args={[width + 2, 0.2, 0.04]} />
          <meshBasicMaterial color="#06B6D4" />
        </mesh>

        {/* South Wall */}
        <mesh position={[width / 2 - 0.5, 1.2, height]} castShadow receiveShadow>
          <boxGeometry args={[width + 2, 2.4, 0.4]} />
          <meshStandardMaterial color="#F8FAFC" roughness={0.3} metalness={0.1} />
        </mesh>
        <mesh position={[width / 2 - 0.5, 0.1, height - 0.22]}>
          <boxGeometry args={[width + 2, 0.2, 0.04]} />
          <meshBasicMaterial color="#06B6D4" />
        </mesh>

        {/* West Wall */}
        <mesh position={[-1, 1.2, height / 2 - 0.5]} castShadow receiveShadow>
          <boxGeometry args={[0.4, 2.4, height + 2]} />
          <meshStandardMaterial color="#F8FAFC" roughness={0.3} metalness={0.1} />
        </mesh>
        <mesh position={[-0.78, 0.1, height / 2 - 0.5]}>
          <boxGeometry args={[0.04, 0.2, height + 2]} />
          <meshBasicMaterial color="#06B6D4" />
        </mesh>

        {/* East Wall */}
        <mesh position={[width, 1.2, height / 2 - 0.5]} castShadow receiveShadow>
          <boxGeometry args={[0.4, 2.4, height + 2]} />
          <meshStandardMaterial color="#F8FAFC" roughness={0.3} metalness={0.1} />
        </mesh>
        <mesh position={[width - 0.22, 0.1, height / 2 - 0.5]}>
          <boxGeometry args={[0.04, 0.2, height + 2]} />
          <meshBasicMaterial color="#06B6D4" />
        </mesh>
      </group>

      {/* Thermal Zone Floor Slabs (Vibrant Saturated Overlays) */}
      {zoneSlabs.map((slab, i) => (
        <mesh
          key={i}
          rotation-x={-Math.PI / 2}
          position={[slab.x, 0.005, slab.z]}
        >
          <planeGeometry args={[0.96, 0.96]} />
          <meshBasicMaterial
            color={slab.type === "CHILLED" ? "#2563EB" : "#06B6D4"}
            transparent
            opacity={slab.type === "CHILLED" ? 0.22 : 0.26}
          />
        </mesh>
      ))}

      {/* Dedicated AMR Home Parking Bay Floor Stalls */}
      {parkingBays.map((bay: { x: number; z: number }, i: number) => (
        <group key={`park-${i}`} position={[bay.x, 0.004, bay.z]}>
          <mesh rotation-x={-Math.PI / 2}>
            <planeGeometry args={[0.88, 0.88]} />
            <meshBasicMaterial color="#10B981" transparent opacity={0.25} />
          </mesh>
          {/* High-Visibility Parking Stall Border */}
          <lineSegments rotation-x={-Math.PI / 2}>
            <edgesGeometry args={[new THREE.PlaneGeometry(0.88, 0.88)]} />
            <lineBasicMaterial color="#059669" />
          </lineSegments>
        </group>
      ))}
    </group>
  );
};
