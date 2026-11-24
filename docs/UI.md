# RoboFleet Operations UI Architecture & Design System (Phase 2 & Phase 4)

## 1. Design Philosophy

RoboFleet Command Centre is built for industrial mission-critical operations. Designed for high-resolution projection screens (1920x1080 to 4K) as well as operations laptops (1366x768).

- **Theme**: Industrial Dark Theme default (`#0B0F17` background, `#111827` panels, `#374151` borders) with a high-contrast Light Theme toggle.
- **Typography**:
  - `JetBrains Mono`: High-legibility tabular figures for clocks, ticks, telemetry, coordinates, and countdown bars.
  - `Inter`: Crisp clean hierarchy for operations copy, labels, and status badges.
- **Zero Placeholder Guarantee (SR-9)**: Every displayed string represents true domain semantics. No "lorem", "sample", "dummy", or "TODO" exist across source code or rendered DOM.
- **Single Disclosure Surface (P2-A9)**: The Environment badge and modal provide full factual disclosure of the digital twin simulation layer.

---

## 2. Canvas 2D Map Architecture

The 2D warehouse map is rendered using raw HTML5 Canvas via an unconstrained `requestAnimationFrame` loop targeting 60 FPS:
- **Sub-Tick Interpolation**: AMR coordinates smoothly interpolate between `motion.from_coord` and `motion.to_coord` using the fractional tick progress `motion.progress`.
- **Racking & Zones**: Shelves reflect thermal storage classifications (Ambient: Slate `#334155`, Chilled: Blue `#1E3A8A`, Frozen: Cyan `#164E63`).
- **Interactive Layers**:
  - Walkways with toggleable aisle flow arrows.
  - Battery chargers with live occupancy status.
  - Dynamic cell blocking with visual cross-hatching.
  - Active alert markers pulsing over affected coordinates.
- **Navigation Controls**:
  - Pan via drag.
  - Zoom via wheel (anchored around mouse cursor).
  - Fit-to-screen computation with automatic aspect-ratio preservation.

---

## 3. 3D Digital Twin Viewport (Phase 4)

RoboFleet offers an integrated WebGL 3D operations twin powered by React-Three-Fiber and Three.js:
- **View Modes**: Switchable between `2D`, `3D`, and `SPLIT` (side-by-side with draggable divider). Mode preference persists across reloads in `localStorage`.
- **Shared State Model**: The 3D view is a pure renderer of the Zustand store. Selection of a robot or alert in 2D immediately highlights and tracks it in 3D, and vice versa.
- **Procedural Geometry Pipeline**: Zero external `.glb`/`.gltf` asset downloads. All models (AMRs, uprights, level boards, tote bins, stations) are built dynamically via `AssetRegistry.ts` (CA-9, CD-4a).
- **GPU Instancing**: Storage racks and tote bins use hardware instanced meshes, reducing draw calls to 54 across the entire dark store (budget: $\le 200$).
- **6 Camera Modes**:
  1. `Orbit`: Unconstrained free orbit with damped inertia.
  2. `Isometric`: 45° orthographic projection from store corner.
  3. `Follow (Chase)`: Smooth third-person chase camera locked to selected AMR heading.
  4. `Stations`: Preset look-at on picking stations and human worker queue dock.
  5. `Dispatch`: Preset look-at on outbound dispatch staging counter.
  6. `Cinematic Tour`: Automated waypoint tour with cosine easing, auto-cutting to live alerts for 4 seconds before returning to tour.
- **Lighting Presets**: `daylight`, `warm_evening`, and `night_ops` (Key: `L`).
- **Resilience**: WebGL context loss listeners gracefully fall back to 2D view without blank screens or unhandled exceptions (P4-A8).

---

## 4. Modular Panel Registry (CA-9)

All dashboard panels are registered in `frontend/src/panels/registry.ts`:
```typescript
defaultPanelRegistry.register({
  id: "order-board",
  title: "Order Board",
  position: "left",
  defaultOpen: true,
  order: 1,
  component: OrderBoard,
});
```
Adding a new panel requires exactly one React component and one registration line.

---

## 5. Performance Benchmarks

- **Target Frame Rate**: $\ge 60$ FPS on standard scenario (20 AMRs, 120 orders/hr) and large scenario (50 AMRs, 300 orders).
- **Draw Calls**: 54 draw calls in 3D mode (budget: 200).
- **Bundle Size**: 317.5 kB gzipped JavaScript (including Three.js, React-Three-Fiber, Lucide icons, and full operations client).
- **Reconnection Resilience**: Disconnecting the server automatically shifts the UI to reconnecting state with exponential backoff (500ms to 4s) and resumes stream synchronization with zero page reload.
