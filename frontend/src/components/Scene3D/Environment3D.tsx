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

  // 1. Lighting Presets Configuration
  const lights = useMemo(() => {
    switch (lightingPreset) {
      case "daylight":
        return {
          ambientColor: "#E0E7FF",
          ambientIntensity: 0.6,
          sunColor: "#FFFFFF",
          sunIntensity: 2.0,
          sunPos: [width / 2, 18, height / 2 + 10] as [number, number, number],
          shadowBias: -0.0005,
        };
      case "warm_evening":
        return {
          ambientColor: "#312E81",
          ambientIntensity: 0.5,
          sunColor: "#FDE68A",
          sunIntensity: 1.8,
          sunPos: [width - 5, 14, height + 8] as [number, number, number],
          shadowBias: -0.0005,
        };
      case "night_ops":
      default:
        return {
          ambientColor: "#0F172A",
          ambientIntensity: 0.35,
          sunColor: "#38BDF8",
          sunIntensity: 1.2,
          sunPos: [width / 2, 12, height / 2] as [number, number, number],
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
        args={[lights.sunColor, "#090D16", 0.4]}
      />

      {/* Main Ground Concrete Slab */}
      <mesh
        rotation-x={-Math.PI / 2}
        position={[width / 2 - 0.5, -0.01, height / 2 - 0.5]}
        receiveShadow
      >
        <planeGeometry args={[width + 4, height + 4]} />
        <meshStandardMaterial color="#0B0F17" roughness={0.8} metalness={0.2} />
      </mesh>

      {/* Grid Floor Mesh */}
      <gridHelper
        args={[Math.max(width, height) * 1.5, Math.max(width, height) * 1.5, 0x1e293b, 0x0f172a]}
        position={[width / 2 - 0.5, 0.001, height / 2 - 0.5]}
      />

      {/* Perimeter Boundary Walls */}
      <group>
        {/* North Wall */}
        <mesh position={[width / 2 - 0.5, 1.2, -1]} castShadow receiveShadow>
          <boxGeometry args={[width + 2, 2.4, 0.4]} />
          <meshStandardMaterial color="#111827" roughness={0.7} metalness={0.4} />
        </mesh>
        {/* South Wall */}
        <mesh position={[width / 2 - 0.5, 1.2, height]} castShadow receiveShadow>
          <boxGeometry args={[width + 2, 2.4, 0.4]} />
          <meshStandardMaterial color="#111827" roughness={0.7} metalness={0.4} />
        </mesh>
        {/* West Wall */}
        <mesh position={[-1, 1.2, height / 2 - 0.5]} castShadow receiveShadow>
          <boxGeometry args={[0.4, 2.4, height + 2]} />
          <meshStandardMaterial color="#111827" roughness={0.7} metalness={0.4} />
        </mesh>
        {/* East Wall */}
        <mesh position={[width, 1.2, height / 2 - 0.5]} castShadow receiveShadow>
          <boxGeometry args={[0.4, 2.4, height + 2]} />
          <meshStandardMaterial color="#111827" roughness={0.7} metalness={0.4} />
        </mesh>
      </group>

      {/* Thermal Zone Floor Slabs */}
      {zoneSlabs.map((slab, i) => (
        <mesh
          key={i}
          rotation-x={-Math.PI / 2}
          position={[slab.x, 0.005, slab.z]}
        >
          <planeGeometry args={[0.96, 0.96]} />
          <meshBasicMaterial
            color={slab.type === "CHILLED" ? "#3B82F6" : "#06B6D4"}
            transparent
            opacity={slab.type === "CHILLED" ? 0.12 : 0.18}
          />
        </mesh>
      ))}
    </group>
  );
};
