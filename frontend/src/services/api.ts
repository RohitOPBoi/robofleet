import type {
  BlockCellsControlRequest,
  EmergencyStopControlRequest,
  EnvironmentDisclosure,
  RushControlRequest,
  SpeedControlRequest,
} from "../types/generated";

const API_BASE = "/api";
const DEFAULT_TOKEN = "secret-robofleet-token";

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

export async function restartSimulation(): Promise<void> {
  const res = await fetch(`${API_BASE}/control/restart`, {
    method: "POST",
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to restart simulation");
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

export async function scaleFleet(targetCount: number): Promise<void> {
  const res = await fetch(`${API_BASE}/control/fleet/scale`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify({ target_count: targetCount }),
  });
  if (!res.ok) throw new Error("Failed to scale fleet");
}

// Phase 5: AI Operations Brain API
export async function fetchBrainStatus(): Promise<any> {
  const res = await fetch(`${API_BASE}/brain/status`);
  if (!res.ok) throw new Error("Failed to fetch brain status");
  return res.json();
}

export async function setBrainMode(enabled: boolean): Promise<any> {
  const res = await fetch(`${API_BASE}/brain/mode`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) throw new Error("Failed to set brain mode");
  return res.json();
}

export async function setBrainProvider(provider: "heuristic" | "anthropic" | "replay"): Promise<any> {
  const res = await fetch(`${API_BASE}/brain/provider`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify({ provider }),
  });
  if (!res.ok) throw new Error("Failed to set brain provider");
  return res.json();
}

export async function fetchBrainDecisions(limit = 50): Promise<any[]> {
  const res = await fetch(`${API_BASE}/brain/decisions?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch brain decisions");
  return res.json();
}

export async function fetchBrainApprovals(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/brain/approvals`);
  if (!res.ok) throw new Error("Failed to fetch brain approvals");
  return res.json();
}

export async function actOnApproval(requestId: string, action: "approve" | "reject"): Promise<any> {
  const res = await fetch(`${API_BASE}/brain/approvals/${encodeURIComponent(requestId)}`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify({ action }),
  });
  if (!res.ok) throw new Error(`Failed to ${action} approval`);
  return res.json();
}

export async function sendSupervisorCommand(query: string, confirm = false): Promise<any> {
  const res = await fetch(`${API_BASE}/brain/supervisor/command`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify({ query, confirm }),
  });
  if (!res.ok) throw new Error("Failed to process supervisor command");
  return res.json();
}

// Phase 6: Chaos, Resilience, Exceptions and Audit API
export async function injectChaosFault(
  fault_type: string,
  target_id = "system",
  duration_ticks = 200,
  params: Record<string, any> = {}
): Promise<any> {
  const res = await fetch(`${API_BASE}/chaos/inject`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify({ fault_type, target_id, duration_ticks, params }),
  });
  if (!res.ok) throw new Error("Failed to inject chaos fault");
  return res.json();
}

export async function injectPerfectStorm(): Promise<any> {
  const res = await fetch(`${API_BASE}/chaos/perfect_storm`, {
    method: "POST",
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to inject perfect storm");
  return res.json();
}

export async function clearChaosFaults(): Promise<any> {
  const res = await fetch(`${API_BASE}/chaos/clear`, {
    method: "POST",
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to clear chaos faults");
  return res.json();
}

export async function fetchChaosStatus(): Promise<any> {
  const res = await fetch(`${API_BASE}/chaos/status`);
  if (!res.ok) throw new Error("Failed to fetch chaos status");
  return res.json();
}

export async function fetchChaosScenarios(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/chaos/scenarios`);
  if (!res.ok) throw new Error("Failed to fetch chaos scenarios");
  return res.json();
}

export async function loadChaosScenario(scenario_name: string): Promise<any> {
  const res = await fetch(`${API_BASE}/chaos/load_scenario`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify({ scenario_name }),
  });
  if (!res.ok) throw new Error(`Failed to load chaos scenario ${scenario_name}`);
  return res.json();
}

export async function fetchExceptions(): Promise<any> {
  const res = await fetch(`${API_BASE}/exceptions`);
  if (!res.ok) throw new Error("Failed to fetch exceptions");
  return res.json();
}

export async function resolveException(
  exceptionId: string,
  action: string,
  actor = "supervisor",
  role = "supervisor",
  reason = ""
): Promise<any> {
  const res = await fetch(`${API_BASE}/exceptions/${encodeURIComponent(exceptionId)}/resolve`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify({ action, actor, role, reason }),
  });
  if (!res.ok) throw new Error(`Failed to resolve exception: ${res.statusText}`);
  return res.json();
}

export async function fetchAuditLogs(
  role?: string,
  actor?: string,
  action?: string,
  limit = 100
): Promise<any[]> {
  const params = new URLSearchParams();
  if (role) params.set("role", role);
  if (actor) params.set("actor", actor);
  if (action) params.set("action", action);
  params.set("limit", String(limit));

  const res = await fetch(`${API_BASE}/audit/logs?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch audit logs");
  return res.json();
}

export async function fetchReslotRecommendations(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/reslot/recommendations`);
  if (!res.ok) throw new Error("Failed to fetch reslot recommendations");
  return res.json();
}

export async function approveReslotRecommendation(
  recommendationId: string,
  actor = "supervisor",
  role = "supervisor"
): Promise<any> {
  const res = await fetch(`${API_BASE}/reslot/${encodeURIComponent(recommendationId)}/approve`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify({ actor, role }),
  });
  if (!res.ok) throw new Error(`Failed to approve reslotting: ${res.statusText}`);
  return res.json();
}

// Phase 7 Replay & Timeline Scrubbing APIs (P7-A3)
export async function fetchReplayRecordings(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/replay/recordings`);
  if (!res.ok) throw new Error("Failed to fetch replay recordings");
  return res.json();
}

export async function loadReplayRecording(recordingId = "demo_golden_run"): Promise<any> {
  const res = await fetch(`${API_BASE}/replay/load`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify({ recording_id: recordingId }),
  });
  if (!res.ok) throw new Error(`Failed to load recording: ${res.statusText}`);
  return res.json();
}

export async function seekReplayRecording(tick: number): Promise<any> {
  const res = await fetch(`${API_BASE}/replay/seek`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify({ tick }),
  });
  if (!res.ok) throw new Error(`Failed to seek recording: ${res.statusText}`);
  return res.json();
}

export async function stepReplayRecording(): Promise<any> {
  const res = await fetch(`${API_BASE}/replay/step`, {
    method: "POST",
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error(`Failed to step recording: ${res.statusText}`);
  return res.json();
}

export async function exitReplayMode(): Promise<any> {
  const res = await fetch(`${API_BASE}/replay/exit`, {
    method: "POST",
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error(`Failed to exit replay: ${res.statusText}`);
  return res.json();
}

export async function fetchReplayState(): Promise<any> {
  const res = await fetch(`${API_BASE}/replay/state`);
  if (!res.ok) throw new Error("Failed to fetch replay state");
  return res.json();
}
