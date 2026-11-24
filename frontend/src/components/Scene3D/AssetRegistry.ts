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

// Shared base materials (High-contrast Vibrant Theme on Crisp White Floor)
const chassisBodyMat = new THREE.MeshStandardMaterial({
  color: 0xf97316, // Vibrant high-visibility safety orange
  roughness: 0.25,
  metalness: 0.2,
});

const chassisDeckMat = new THREE.MeshStandardMaterial({
  color: 0xffffff, // Crisp showroom white top deck plate
  roughness: 0.15,
  metalness: 0.1,
});

const lowerSkirtMat = new THREE.MeshStandardMaterial({
  color: 0x0f172a, // Deep slate undercarriage skirt for sharp floor contrast
  roughness: 0.7,
  metalness: 0.2,
});

const neonHaloMat = new THREE.MeshStandardMaterial({
  color: 0x00f0ff, // Vibrant electric cyan halo
  emissive: 0x00e5ff,
  emissiveIntensity: 0.6,
  roughness: 0.15,
  metalness: 0.7,
});

const shadowDiskMat = new THREE.MeshBasicMaterial({
  color: 0x0f172a,
  transparent: true,
  opacity: 0.4,
});

const lidarOpticMat = new THREE.MeshStandardMaterial({
  color: 0x0f172a, // High-contrast dark optic glass dome
  roughness: 0.1,
  metalness: 0.9,
});

const heavyChassisMat = new THREE.MeshStandardMaterial({
  color: 0x1e293b, // Industrial slate heavy-duty chassis
  roughness: 0.35,
  metalness: 0.4,
});

const heavyAccentMat = new THREE.MeshStandardMaterial({
  color: 0xf97316, // Vibrant safety orange bumper
  roughness: 0.3,
  metalness: 0.5,
});

const wheelRimMat = new THREE.MeshStandardMaterial({
  color: 0xcfd8dc, // Titanium silver wheel rim
  roughness: 0.2,
  metalness: 0.8,
});

const rubberMat = new THREE.MeshStandardMaterial({
  color: 0x1e293b, // Clean dark slate rubber tire
  roughness: 0.75,
  metalness: 0.1,
});

const purpleToteMat = new THREE.MeshStandardMaterial({
  color: 0x8b5cf6, // Vibrant electric violet
  roughness: 0.3,
  metalness: 0.2,
});

const blueToteMat = new THREE.MeshStandardMaterial({
  color: 0x0284c7, // Vibrant royal blue
  roughness: 0.3,
  metalness: 0.2,
});

const orangeToteMat = new THREE.MeshStandardMaterial({
  color: 0xf97316, // Vibrant electric orange
  roughness: 0.3,
  metalness: 0.2,
});

const yellowLidMat = new THREE.MeshStandardMaterial({
  color: 0xfacc15, // Bright canary yellow lid
  roughness: 0.35,
  metalness: 0.1,
});

/**
 * Standard AMR Builder: High-contrast vibrant robot that pops clearly against a white floor.
 */
export const buildStandardAMR: RobotModelBuilder = ({ statusColor, hasTote, toteColor }) => {
  const group = new THREE.Group();

  // 0. Contact ground shadow disk (grounds robot on white floor)
  const shadowGeo = new THREE.CircleGeometry(0.46, 24);
  const shadow = new THREE.Mesh(shadowGeo, shadowDiskMat);
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.y = 0.006;
  group.add(shadow);

  // 1a. Dark undercarriage protective skirt
  const skirtGeo = new THREE.CylinderGeometry(0.40, 0.42, 0.05, 24);
  const skirt = new THREE.Mesh(skirtGeo, lowerSkirtMat);
  skirt.position.y = 0.05;
  group.add(skirt);

  // 1b. Main high-visibility vibrant safety orange body
  const chassis = new THREE.Mesh(chassisGeometry, chassisBodyMat);
  chassis.position.y = 0.14;
  chassis.castShadow = true;
  chassis.receiveShadow = true;
  group.add(chassis);

  // 1c. Crisp white top deck plate
  const deckGeo = new THREE.CylinderGeometry(0.35, 0.37, 0.03, 24);
  const deck = new THREE.Mesh(deckGeo, chassisDeckMat);
  deck.position.y = 0.235;
  group.add(deck);

  // 1d. Vibrant neon cyan halo ring
  const haloGeo = new THREE.CylinderGeometry(0.395, 0.405, 0.025, 24);
  const halo = new THREE.Mesh(haloGeo, neonHaloMat);
  halo.position.y = 0.14;
  group.add(halo);

  // 1e. Top LiDAR optic dome
  const lidarGeo = new THREE.CylinderGeometry(0.09, 0.11, 0.06, 16);
  const lidar = new THREE.Mesh(lidarGeo, lidarOpticMat);
  lidar.position.set(0, 0.26, 0);
  group.add(lidar);

  // 2. Wheels (left and right with titanium rims)
  const wheelAssembly = (xPos: number) => {
    const wheelGroup = new THREE.Group();
    wheelGroup.position.set(xPos, 0.08, 0);
    const tire = new THREE.Mesh(wheelGeometry, rubberMat);
    tire.rotation.z = Math.PI / 2;
    wheelGroup.add(tire);
    const rimGeo = new THREE.CylinderGeometry(0.055, 0.055, 0.052, 12);
    const rim = new THREE.Mesh(rimGeo, wheelRimMat);
    rim.rotation.z = Math.PI / 2;
    wheelGroup.add(rim);
    return wheelGroup;
  };

  group.add(wheelAssembly(-0.25));
  group.add(wheelAssembly(0.25));

  // 3. Status LED Light Beacon (Vivid glowing)
  const ledMat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(statusColor),
    emissive: new THREE.Color(statusColor),
    emissiveIntensity: 0.9,
    roughness: 0.15,
  });
  const led = new THREE.Mesh(statusLightGeometry, ledMat);
  led.position.set(0, 0.25, 0.22);
  group.add(led);

  // 4. Directional Heading Indicator (front nose tick)
  const pointerGeo = new THREE.ConeGeometry(0.045, 0.11, 8);
  const pointerMat = new THREE.MeshBasicMaterial({ color: 0x00f0ff });
  const pointer = new THREE.Mesh(pointerGeo, pointerMat);
  pointer.rotation.x = Math.PI / 2;
  pointer.position.set(0, 0.23, 0.32);
  group.add(pointer);

  // 5. Carried Tote if active task (vibrant saturated colors)
  if (hasTote) {
    const toteMat = toteColor
      ? new THREE.MeshStandardMaterial({ color: new THREE.Color(toteColor), roughness: 0.3 })
      : blueToteMat;
    const tote = new THREE.Mesh(toteGeometry, toteMat);
    tote.position.set(0, 0.34, 0);
    tote.castShadow = true;

    const lid = new THREE.Mesh(lidGeometry, yellowLidMat);
    lid.position.set(0, 0.12, 0);
    tote.add(lid);

    group.add(tote);
  }

  return group;
};

/**
 * Heavy AMR Builder: Rugged heavy-duty pallet/tote carrier robot.
 * Satisfies CD-4a robot kind visual extensibility.
 */
export const buildHeavyAMR: RobotModelBuilder = ({ statusColor, hasTote, toteColor }) => {
  const group = new THREE.Group();

  // Contact ground shadow
  const shadowGeo = new THREE.PlaneGeometry(0.95, 0.75);
  const shadow = new THREE.Mesh(shadowGeo, shadowDiskMat);
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.y = 0.006;
  group.add(shadow);

  // Rectangular heavy chassis
  const chassis = new THREE.Mesh(heavyChassisGeometry, heavyChassisMat);
  chassis.position.y = 0.15;
  chassis.castShadow = true;
  group.add(chassis);

  // Safety orange corner bumpers
  const bumperGeo = new THREE.BoxGeometry(0.87, 0.06, 0.67);
  const bumper = new THREE.Mesh(bumperGeo, heavyAccentMat);
  bumper.position.y = 0.08;
  group.add(bumper);

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
  const ledMat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(statusColor),
    emissive: new THREE.Color(statusColor),
    emissiveIntensity: 0.9,
  });
  const led1 = new THREE.Mesh(statusLightGeometry, ledMat);
  led1.position.set(-0.25, 0.28, 0.3);
  group.add(led1);

  const led2 = new THREE.Mesh(statusLightGeometry, ledMat);
  led2.position.set(0.25, 0.28, 0.3);
  group.add(led2);

  // Carried Heavy Tote
  if (hasTote) {
    const toteMat = toteColor
      ? new THREE.MeshStandardMaterial({ color: new THREE.Color(toteColor), roughness: 0.3 })
      : orangeToteMat;
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
