import type {
  BlockCellsControlRequest,
  EmergencyStopControlRequest,
  EnvironmentDisclosure,
  RushControlRequest,
  SpeedControlRequest,
} from "../types/generated";

const API_BASE = "/api";
const DEFAULT_TOKEN = "test-secret-token";

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem("ROBOFLEET_TOKEN") || DEFAULT_TOKEN;
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

export async function fetchEnvironment(): Promise<EnvironmentDisclosure> {
  const res = await fetch(`${API_BASE}/environment`);
  if (!res.ok) throw new Error(`Failed to fetch environment disclosure: ${res.statusText}`);
  return res.json();
}

export async function pauseSimulation(): Promise<void> {
  const res = await fetch(`${API_BASE}/control/pause`, {
    method: "POST",
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to pause simulation");
}

export async function resumeSimulation(): Promise<void> {
  const res = await fetch(`${API_BASE}/control/resume`, {
    method: "POST",
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to resume simulation");
}

export async function setSimulationSpeed(multiplier: number): Promise<void> {
  const payload: SpeedControlRequest = { multiplier };
  const res = await fetch(`${API_BASE}/control/speed`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to set simulation speed");
}

export async function stepSimulation(): Promise<void> {
  const res = await fetch(`${API_BASE}/control/step`, {
    method: "POST",
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to step simulation");
}

export async function triggerRush(multiplier = 2.5, duration_s = 300): Promise<void> {
  const payload: RushControlRequest = { multiplier, duration_s };
  const res = await fetch(`${API_BASE}/control/rush`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to trigger rush");
}

export async function emergencyStop(scope: "all" | "robot" | "zone", target_id?: string | null): Promise<void> {
  const payload: EmergencyStopControlRequest = { scope, target_id };
  const res = await fetch(`${API_BASE}/control/emergency_stop`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to trigger emergency stop");
}

export async function resumeEmergency(scope: "all" | "robot" | "zone", target_id?: string | null): Promise<void> {
  const payload: EmergencyStopControlRequest = { scope, target_id };
  const res = await fetch(`${API_BASE}/control/resume_emergency`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to resume emergency");
}

export async function blockCells(cells: { x: number; y: number }[]): Promise<void> {
  const payload: BlockCellsControlRequest = { cells };
  const res = await fetch(`${API_BASE}/control/block_cells`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to block cells");
}

export async function unblockCells(cells: { x: number; y: number }[]): Promise<void> {
  const payload: BlockCellsControlRequest = { cells };
  const res = await fetch(`${API_BASE}/control/unblock_cells`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to unblock cells");
}
