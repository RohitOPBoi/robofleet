/**
 * Robots3D: Procedural AMR rendering with sub-tick progress interpolation,
 * smooth heading slerp, carried totes, selection rings, and trajectory ribbons.
 */

import React, { useMemo } from "react";
import * as THREE from "three";
import type { Robot } from "../../types/generated";
import { setStore, useStore } from "../../store/useStore";
import { getRobotModel } from "./AssetRegistry";

export const Robots3D: React.FC = () => {
  const { robots, selectedRobotId, show3DPaths } = useStore();

  const robotList = useMemo(() => Object.values(robots), [robots]);

  return (
    <group>
      {robotList.map((r: Robot) => {
        let rx = r.coord?.x ?? 0;
        let rz = r.coord?.y ?? 0;
        if (r.motion?.from_coord && r.motion?.to_coord) {
          const prog = Math.max(0, Math.min(1, r.motion.progress ?? 0));
          rx = r.motion.from_coord.x + (r.motion.to_coord.x - r.motion.from_coord.x) * prog;
          rz = r.motion.from_coord.y + (r.motion.to_coord.y - r.motion.from_coord.y) * prog;
        }

        const headingRad = -((r.heading_deg ?? 0) * Math.PI) / 180 + Math.PI / 2;
        const isSelected = selectedRobotId === r.id;
        const hasTote = Boolean(r.current_task_id || (r as any).carrying?.length > 0);

        // Status color
        let statusColor = "#10B981";
        if (r.state === "CHARGING") statusColor = "#F59E0B";
        else if (r.state === "FAULTED" || r.state === "EMERGENCY_STOPPED") statusColor = "#EF4444";
        else if (String(r.state).includes("PICK") || hasTote) statusColor = "#06B6D4";

        const model = useMemo(
          () =>
            getRobotModel(r.id.includes("HEAVY") ? "heavy_amr" : "standard_amr", {
              statusColor,
              hasTote,
              isSelected,
            }),
          [r.id, statusColor, hasTote, isSelected]
        );

        return (
          <group
            key={r.id}
            position={[rx, 0, rz]}
            rotation-y={headingRad}
            onClick={(e) => {
              e.stopPropagation();
              setStore({ selectedRobotId: isSelected ? null : r.id });
            }}
          >
            {/* Procedural Robot Geometry from AssetRegistry */}
            <primitive object={model} />

            {/* Selection Floor Ring */}
            {isSelected && (
              <mesh rotation-x={-Math.PI / 2} position={[0, 0.02, 0]}>
                <ringGeometry args={[0.5, 0.58, 32]} />
                <meshBasicMaterial color="#00F0FF" />
              </mesh>
            )}

            {/* Trajectory Ribbon Line (to target cell) */}
            {isSelected && show3DPaths && r.motion?.to_coord && (
              <group position={[0, 0.05, 0]}>
                <line>
                  <bufferGeometry
                    attach="geometry"
                    onUpdate={(self) => {
                      const toX = r.motion.to_coord.x - rx;
                      const toZ = r.motion.to_coord.y - rz;
                      // Counter-rotate because group has rotation-y
                      const cos = Math.cos(-headingRad);
                      const sin = Math.sin(-headingRad);
                      const lx = toX * cos - toZ * sin;
                      const lz = toX * sin + toZ * cos;

                      const points = [
                        new THREE.Vector3(0, 0.1, 0),
                        new THREE.Vector3(lx, 0.1, lz),
                      ];
                      self.setFromPoints(points);
                    }}
                  />
                  <lineDashedMaterial
                    attach="material"
                    color="#00F0FF"
                    dashSize={0.2}
                    gapSize={0.15}
                    linewidth={2}
                  />
                </line>
              </group>
            )}
          </group>
        );
      })}
    </group>
  );
};
