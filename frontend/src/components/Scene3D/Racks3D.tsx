/**
 * Racks3D: True hardware-instanced procedural warehouse storage racks with level boards & bins.
 * Renders hundreds of shelf cells with <12 draw calls across the entire dark store.
 */

import React, { useMemo, useEffect, useRef } from "react";
import * as THREE from "three";
import { useStore } from "../../store/useStore";

// Geometries
const uprightGeometry = new THREE.BoxGeometry(0.06, 2.2, 0.06);
const shelfBeamGeometry = new THREE.BoxGeometry(0.88, 0.04, 0.78);
const binGeometry = new THREE.BoxGeometry(0.32, 0.22, 0.3);

// Shared materials (Light Architectural Racks with Vibrant Pop Bins)
const ambientRackMat = new THREE.MeshStandardMaterial({
  color: 0xe2e8f0, // Clean architectural aluminum off-white
  roughness: 0.25,
  metalness: 0.65,
});

const chilledRackMat = new THREE.MeshStandardMaterial({
  color: 0x93c5fd, // Light icy blue frame
  roughness: 0.25,
  metalness: 0.7,
});

const frozenRackMat = new THREE.MeshStandardMaterial({
  color: 0x67e8f9, // Electric frost cyan frame
  roughness: 0.25,
  metalness: 0.7,
});

const blueBinMat = new THREE.MeshStandardMaterial({ color: 0x0284c7, roughness: 0.3, metalness: 0.15 });
const amberBinMat = new THREE.MeshStandardMaterial({ color: 0xf97316, roughness: 0.3, metalness: 0.15 });
const emeraldBinMat = new THREE.MeshStandardMaterial({ color: 0x10b981, roughness: 0.3, metalness: 0.15 });
const grayBinMat = new THREE.MeshStandardMaterial({ color: 0x8b5cf6, roughness: 0.3, metalness: 0.15 });

const dummy = new THREE.Object3D();

export const Racks3D: React.FC = () => {
  const { staticWorld } = useStore();
  const layout = staticWorld?.layout;

  // Shelf coordinates grouped by zone
  const { ambientRacks, chilledRacks, frozenRacks, allRacks } = useMemo(() => {
    const ambient: { x: number; z: number }[] = [];
    const chilled: { x: number; z: number }[] = [];
    const frozen: { x: number; z: number }[] = [];
    const all: { x: number; z: number }[] = [];

    const cells = Array.isArray((layout as any)?.cells) ? (layout as any).cells : [];
    cells.forEach((cell: any) => {
      if (cell.cell_type === "SHELF") {
        const p = cell.pos || cell.coord || { x: 0, y: 0 };
        const coord = { x: p.x, z: p.y };
        all.push(coord);
        if (cell.zone === "CHILLED") chilled.push(coord);
        else if (cell.zone === "FROZEN") frozen.push(coord);
        else ambient.push(coord);
      }
    });

    return { ambientRacks: ambient, chilledRacks: chilled, frozenRacks: frozen, allRacks: all };
  }, [layout]);

  // Mesh refs
  const ambientUprightsRef = useRef<THREE.InstancedMesh>(null);
  const ambientDecksRef = useRef<THREE.InstancedMesh>(null);
  const chilledUprightsRef = useRef<THREE.InstancedMesh>(null);
  const chilledDecksRef = useRef<THREE.InstancedMesh>(null);
  const frozenUprightsRef = useRef<THREE.InstancedMesh>(null);
  const frozenDecksRef = useRef<THREE.InstancedMesh>(null);

  const blueBinsRef = useRef<THREE.InstancedMesh>(null);
  const amberBinsRef = useRef<THREE.InstancedMesh>(null);
  const emeraldBinsRef = useRef<THREE.InstancedMesh>(null);
  const grayBinsRef = useRef<THREE.InstancedMesh>(null);

  // Helper to populate uprights & decks
  const updateRackInstances = (
    racks: { x: number; z: number }[],
    uprightsMesh: THREE.InstancedMesh | null,
    decksMesh: THREE.InstancedMesh | null
  ) => {
    if (!uprightsMesh || !decksMesh) return;
    let upIdx = 0;
    let deckIdx = 0;

    const uprightOffsets = [
      [-0.4, 1.1, -0.35],
      [0.4, 1.1, -0.35],
      [-0.4, 1.1, 0.35],
      [0.4, 1.1, 0.35],
    ];

    const deckHeights = [0.2, 0.9, 1.6];

    racks.forEach((r) => {
      // 4 uprights
      uprightOffsets.forEach(([ox, oy, oz]) => {
        dummy.position.set(r.x + ox, oy, r.z + oz);
        dummy.rotation.set(0, 0, 0);
        dummy.scale.set(1, 1, 1);
        dummy.updateMatrix();
        uprightsMesh.setMatrixAt(upIdx++, dummy.matrix);
      });

      // 3 decks
      deckHeights.forEach((dh) => {
        dummy.position.set(r.x, dh, r.z);
        dummy.rotation.set(0, 0, 0);
        dummy.scale.set(1, 1, 1);
        dummy.updateMatrix();
        decksMesh.setMatrixAt(deckIdx++, dummy.matrix);
      });
    });

    uprightsMesh.instanceMatrix.needsUpdate = true;
    decksMesh.instanceMatrix.needsUpdate = true;
  };

  useEffect(() => {
    updateRackInstances(ambientRacks, ambientUprightsRef.current, ambientDecksRef.current);
  }, [ambientRacks]);

  useEffect(() => {
    updateRackInstances(chilledRacks, chilledUprightsRef.current, chilledDecksRef.current);
  }, [chilledRacks]);

  useEffect(() => {
    updateRackInstances(frozenRacks, frozenUprightsRef.current, frozenDecksRef.current);
  }, [frozenRacks]);

  // Populate Bins across all racks
  useEffect(() => {
    const blue = blueBinsRef.current;
    const amber = amberBinsRef.current;
    const emerald = emeraldBinsRef.current;
    const gray = grayBinsRef.current;

    if (!blue || !amber || !emerald || !gray) return;

    let blueIdx = 0;
    let amberIdx = 0;
    let emeraldIdx = 0;
    let grayIdx = 0;

    allRacks.forEach((r) => {
      // Level 1: Blue (-0.2) + Amber (+0.2)
      dummy.position.set(r.x - 0.2, 0.34, r.z);
      dummy.updateMatrix();
      blue.setMatrixAt(blueIdx++, dummy.matrix);

      dummy.position.set(r.x + 0.2, 0.34, r.z);
      dummy.updateMatrix();
      amber.setMatrixAt(amberIdx++, dummy.matrix);

      // Level 2: Emerald (-0.2) + Gray (+0.2)
      dummy.position.set(r.x - 0.2, 1.04, r.z);
      dummy.updateMatrix();
      emerald.setMatrixAt(emeraldIdx++, dummy.matrix);

      dummy.position.set(r.x + 0.2, 1.04, r.z);
      dummy.updateMatrix();
      gray.setMatrixAt(grayIdx++, dummy.matrix);

      // Level 3: Blue (0)
      dummy.position.set(r.x, 1.74, r.z);
      dummy.updateMatrix();
      blue.setMatrixAt(blueIdx++, dummy.matrix);
    });

    blue.instanceMatrix.needsUpdate = true;
    amber.instanceMatrix.needsUpdate = true;
    emerald.instanceMatrix.needsUpdate = true;
    gray.instanceMatrix.needsUpdate = true;
  }, [allRacks]);

  return (
    <group>
      {/* Ambient Zone Instanced Meshes */}
      {ambientRacks.length > 0 && (
        <>
          <instancedMesh
            ref={ambientUprightsRef}
            args={[uprightGeometry, ambientRackMat, ambientRacks.length * 4]}
            castShadow
            frustumCulled={false}
          />
          <instancedMesh
            ref={ambientDecksRef}
            args={[shelfBeamGeometry, ambientRackMat, ambientRacks.length * 3]}
            receiveShadow
            frustumCulled={false}
          />
        </>
      )}

      {/* Chilled Zone Instanced Meshes */}
      {chilledRacks.length > 0 && (
        <>
          <instancedMesh
            ref={chilledUprightsRef}
            args={[uprightGeometry, chilledRackMat, chilledRacks.length * 4]}
            castShadow
            frustumCulled={false}
          />
          <instancedMesh
            ref={chilledDecksRef}
            args={[shelfBeamGeometry, chilledRackMat, chilledRacks.length * 3]}
            receiveShadow
            frustumCulled={false}
          />
        </>
      )}

      {/* Frozen Zone Instanced Meshes */}
      {frozenRacks.length > 0 && (
        <>
          <instancedMesh
            ref={frozenUprightsRef}
            args={[uprightGeometry, frozenRackMat, frozenRacks.length * 4]}
            castShadow
            frustumCulled={false}
          />
          <instancedMesh
            ref={frozenDecksRef}
            args={[shelfBeamGeometry, frozenRackMat, frozenRacks.length * 3]}
            receiveShadow
            frustumCulled={false}
          />
        </>
      )}

      {/* Inventory Bins (Shared across all zones) */}
      {allRacks.length > 0 && (
        <>
          <instancedMesh
            ref={blueBinsRef}
            args={[binGeometry, blueBinMat, allRacks.length * 2]}
            castShadow
            frustumCulled={false}
          />
          <instancedMesh
            ref={amberBinsRef}
            args={[binGeometry, amberBinMat, allRacks.length]}
            castShadow
            frustumCulled={false}
          />
          <instancedMesh
            ref={emeraldBinsRef}
            args={[binGeometry, emeraldBinMat, allRacks.length]}
            castShadow
            frustumCulled={false}
          />
          <instancedMesh
            ref={grayBinsRef}
            args={[binGeometry, grayBinMat, allRacks.length]}
            castShadow
            frustumCulled={false}
          />
        </>
      )}
    </group>
  );
};
