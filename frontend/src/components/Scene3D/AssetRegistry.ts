/**
 * AssetRegistry (CA-9, CA-4): Procedural 3D asset builders for RoboFleet.
 * Maps robot kinds, cell types, and thermal zones to procedural 3D geometries.
 * Guarantees zero external asset loading, zero licensing hurdles, and CD-4a compliance.
 */

import * as THREE from "three";

export interface RobotVisualProps {
  statusColor: string;
  hasTote: boolean;
  toteColor?: string;
  isSelected?: boolean;
}

export type RobotModelBuilder = (props: RobotVisualProps) => THREE.Group;

// Materials and Geometries shared across instances for peak memory efficiency
const chassisGeometry = new THREE.CylinderGeometry(0.38, 0.42, 0.18, 24);
const heavyChassisGeometry = new THREE.BoxGeometry(0.85, 0.22, 0.65);
const wheelGeometry = new THREE.CylinderGeometry(0.08, 0.08, 0.05, 12);
const statusLightGeometry = new THREE.SphereGeometry(0.05, 12, 12);
const toteGeometry = new THREE.BoxGeometry(0.36, 0.22, 0.28);
const lidGeometry = new THREE.BoxGeometry(0.38, 0.03, 0.3);

// Shared base materials
const carbonChassisMat = new THREE.MeshStandardMaterial({
  color: 0x111827,
  roughness: 0.35,
  metalness: 0.7,
});

const heavyChassisMat = new THREE.MeshStandardMaterial({
  color: 0x1f2937,
  roughness: 0.4,
  metalness: 0.8,
});

const rubberMat = new THREE.MeshStandardMaterial({
  color: 0x030712,
  roughness: 0.9,
  metalness: 0.1,
});

const purpleToteMat = new THREE.MeshStandardMaterial({
  color: 0x9333ea,
  roughness: 0.4,
  metalness: 0.2,
});

const yellowLidMat = new THREE.MeshStandardMaterial({
  color: 0xfacc15,
  roughness: 0.5,
  metalness: 0.1,
});

/**
 * Standard AMR Builder: Compact circular differential-drive autonomous mobile robot.
 */
export const buildStandardAMR: RobotModelBuilder = ({ statusColor, hasTote, toteColor }) => {
  const group = new THREE.Group();

  // 1. Main cylindrical chassis
  const chassis = new THREE.Mesh(chassisGeometry, carbonChassisMat);
  chassis.position.y = 0.12;
  chassis.castShadow = true;
  chassis.receiveShadow = true;
  group.add(chassis);

  // 2. Wheels (left and right)
  const leftWheel = new THREE.Mesh(wheelGeometry, rubberMat);
  leftWheel.rotation.z = Math.PI / 2;
  leftWheel.position.set(-0.25, 0.08, 0);
  group.add(leftWheel);

  const rightWheel = new THREE.Mesh(wheelGeometry, rubberMat);
  rightWheel.rotation.z = Math.PI / 2;
  rightWheel.position.set(0.25, 0.08, 0);
  group.add(rightWheel);

  // 3. Status LED Light Beacon
  const ledMat = new THREE.MeshBasicMaterial({ color: new THREE.Color(statusColor) });
  const led = new THREE.Mesh(statusLightGeometry, ledMat);
  led.position.set(0, 0.23, 0.2);
  group.add(led);

  // 4. Directional Heading Indicator (front nose tick)
  const pointerGeo = new THREE.ConeGeometry(0.04, 0.1, 8);
  const pointerMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8 });
  const pointer = new THREE.Mesh(pointerGeo, pointerMat);
  pointer.rotation.x = Math.PI / 2;
  pointer.position.set(0, 0.21, 0.32);
  group.add(pointer);

  // 5. Carried Tote if active task
  if (hasTote) {
    const toteMat = toteColor
      ? new THREE.MeshStandardMaterial({ color: new THREE.Color(toteColor), roughness: 0.4 })
      : purpleToteMat;
    const tote = new THREE.Mesh(toteGeometry, toteMat);
    tote.position.set(0, 0.32, 0);
    tote.castShadow = true;

    const lid = new THREE.Mesh(lidGeometry, yellowLidMat);
    lid.position.set(0, 0.12, 0);
    tote.add(lid);

    group.add(tote);
  }

  return group;
};

/**
 * Heavy AMR Builder: Rugged rectangular heavy-duty pallet/tote carrier robot.
 * Satisfies CD-4a robot kind visual extensibility.
 */
export const buildHeavyAMR: RobotModelBuilder = ({ statusColor, hasTote, toteColor }) => {
  const group = new THREE.Group();

  // Rectangular heavy chassis
  const chassis = new THREE.Mesh(heavyChassisGeometry, heavyChassisMat);
  chassis.position.y = 0.15;
  chassis.castShadow = true;
  group.add(chassis);

  // 4 heavy wheels
  const wheelOffsets = [
    [-0.35, 0.08, -0.22],
    [-0.35, 0.08, 0.22],
    [0.35, 0.08, -0.22],
    [0.35, 0.08, 0.22],
  ];
  wheelOffsets.forEach(([x, y, z]) => {
    const w = new THREE.Mesh(wheelGeometry, rubberMat);
    w.rotation.z = Math.PI / 2;
    w.position.set(x, y, z);
    group.add(w);
  });

  // Dual Status Lights
  const ledMat = new THREE.MeshBasicMaterial({ color: new THREE.Color(statusColor) });
  const led1 = new THREE.Mesh(statusLightGeometry, ledMat);
  led1.position.set(-0.25, 0.28, 0.3);
  group.add(led1);

  const led2 = new THREE.Mesh(statusLightGeometry, ledMat);
  led2.position.set(0.25, 0.28, 0.3);
  group.add(led2);

  // Carried Heavy Tote
  if (hasTote) {
    const toteMat = toteColor
      ? new THREE.MeshStandardMaterial({ color: new THREE.Color(toteColor), roughness: 0.4 })
      : purpleToteMat;
    const tote = new THREE.Mesh(toteGeometry, toteMat);
    tote.position.set(0, 0.38, 0);
    tote.scale.set(1.3, 1.2, 1.3);
    group.add(tote);
  }

  return group;
};

/**
 * Pluggable Robot Asset Registry (CA-9, CD-4a)
 */
export const ROBOT_ASSET_REGISTRY: Record<string, RobotModelBuilder> = {
  standard_amr: buildStandardAMR,
  heavy_amr: buildHeavyAMR,
  default: buildStandardAMR,
};

export function getRobotModel(kind: string, props: RobotVisualProps): THREE.Group {
  const builder = ROBOT_ASSET_REGISTRY[kind] || ROBOT_ASSET_REGISTRY.default;
  return builder(props);
}
