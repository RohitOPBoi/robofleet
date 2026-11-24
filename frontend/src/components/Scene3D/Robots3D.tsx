/**
 * Robots3D: Procedural AMR rendering with sub-tick progress interpolation,
 * smooth heading slerp, carried totes, selection rings, and trajectory ribbons.
 */

import React, { useMemo } from "react";
import * as THREE from "three";
import type { Robot } from "../../types/generated";
import { setStore, useStore } from "../../store/useStore";
import { getRobotModel } from "./AssetRegistry";

interface SingleRobotProps {
  r: Robot;
  isSelected: boolean;
  hasAlert: boolean;
  alertSeverity?: "CRITICAL" | "WARN" | "INFO";
  show3DPaths: boolean;
}

const SingleRobot3D: React.FC<SingleRobotProps> = ({ r, isSelected, hasAlert, alertSeverity, show3DPaths }) => {
  let rx = r.coord?.x ?? 0;
  let rz = r.coord?.y ?? 0;
  if (r.motion?.from_coord && r.motion?.to_coord) {
    const prog = Math.max(0, Math.min(1, r.motion.progress ?? 0));
    rx = r.motion.from_coord.x + (r.motion.to_coord.x - r.motion.from_coord.x) * prog;
    rz = r.motion.from_coord.y + (r.motion.to_coord.y - r.motion.from_coord.y) * prog;
  }

  const headingRad = -((r.heading_deg ?? 0) * Math.PI) / 180 + Math.PI / 2;
  const hasTote = Boolean(r.current_task_id || (r as any).carrying?.length > 0);

  // Status color
  const isFaulted = r.state === "FAULTED" || r.state === "EMERGENCY_STOPPED" || Boolean(r.fault_code) || hasAlert;
  let statusColor = "#10B981";
  if (r.state === "CHARGING") statusColor = "#F59E0B";
  else if (isFaulted) statusColor = alertSeverity === "CRITICAL" || !hasAlert ? "#EF4444" : "#F59E0B";
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
      position={[rx, 0, rz]}
      rotation-y={headingRad}
      onClick={(e) => {
        e.stopPropagation();
        setStore({ selectedRobotId: isSelected ? null : r.id });
      }}
    >
      {/* Procedural Robot Geometry from AssetRegistry */}
      <primitive object={model} />

      {/* Fault / Alert Warning Strobe Light */}
      {(isFaulted || hasAlert) && (
        <group position={[0, 0.72, 0]}>
          <mesh>
            <sphereGeometry args={[0.08, 16, 16]} />
            <meshBasicMaterial color={alertSeverity === "CRITICAL" || !hasAlert ? "#EF4444" : "#F59E0B"} />
          </mesh>
          <pointLight color={alertSeverity === "CRITICAL" || !hasAlert ? "#EF4444" : "#F59E0B"} intensity={4.0} distance={3.5} />
        </group>
      )}

      {/* Alert / Highlight Ground Beacon Ring */}
      {(hasAlert || isFaulted) && (
        <mesh rotation-x={-Math.PI / 2} position={[0, 0.025, 0]}>
          <ringGeometry args={[0.55, 0.68, 32]} />
          <meshBasicMaterial
            color={alertSeverity === "CRITICAL" || !hasAlert ? "#EF4444" : "#F59E0B"}
            transparent
            opacity={0.85}
            side={THREE.DoubleSide}
          />
        </mesh>
      )}

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
};

export const Robots3D: React.FC = () => {
  const { robots, selectedRobotId, show3DPaths, alerts, activeFaults } = useStore();
  const robotList = useMemo(() => Object.values(robots), [robots]);

  const alertMap = useMemo(() => {
    const map = new Map<string, "CRITICAL" | "WARN" | "INFO">();
    alerts.forEach((a) => {
      if (!a.cleared && a.entity_id) {
        map.set(a.entity_id, a.severity || "WARN");
      }
    });
    activeFaults.forEach((f) => {
      if (f.target_id) {
        map.set(f.target_id, "CRITICAL");
      }
    });
    return map;
  }, [alerts, activeFaults]);

  return (
    <group>
      {robotList.map((r: Robot) => {
        const severity = alertMap.get(r.id);
        const hasAlert = severity !== undefined;
        return (
          <SingleRobot3D
            key={r.id}
            r={r}
            isSelected={selectedRobotId === r.id}
            hasAlert={hasAlert}
            alertSeverity={severity}
            show3DPaths={show3DPaths}
          />
        );
      })}
    </group>
  );
};
