import React, { useEffect, useState } from "react";
import {
  CheckCircle2,
  Cloud,
  Cpu,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  RefreshCw,
  Server,
  ShieldAlert,
  Sparkles,
  Trash2,
  X,
  XCircle,
} from "lucide-react";
import {
  fetchBrainConfig,
  fetchLocalLLMStatus,
  setBrainProvider,
  testAICloudConnection,
  testLocalLLMConnection,
  updateAICloudConfig,
  updateLocalLLMConfig,
} from "../../services/api";
import { setStore, useStore } from "../../store/useStore";
import type { BrainConfigPayload, BrainMode, ProviderPresetInfo } from "../../types/generated";

export const AISettingsModal: React.FC = () => {
  const store = useStore();
  const { isAISettingsOpen } = store;

  const [activeTab, setActiveTab] = useState<"ai" | "local_llm">("ai");
  const [configData, setConfigData] = useState<BrainConfigPayload | null>(null);
  const [loading, setLoading] = useState(false);

  // Cloud AI Mode Form State (API Key held only in transient React state, never localStorage)
  const [presetId, setPresetId] = useState("openai");
  const [providerType, setProviderType] = useState("openai_compatible");
  const [providerLabel, setProviderLabel] = useState("OpenAI");
  const [apiCompatibility, setApiCompatibility] = useState<
    "openai_chat" | "openai_responses" | "anthropic_messages"
  >("openai_chat");
  const [baseUrl, setBaseUrl] = useState("https://api.openai.com/v1");
  const [modelName, setModelName] = useState("gpt-4o-mini");
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [orgId, setOrgId] = useState("");
  const [projectId, setProjectId] = useState("");
  const [cloudTimeout, setCloudTimeout] = useState(12);
  const [cloudTemp, setCloudTemp] = useState(0.15);
  const [cloudMaxTokens, setCloudMaxTokens] = useState(900);
  const [cloudFallback, setCloudFallback] = useState<"heuristic" | "safe_wait">("heuristic");
  const [cloudTestResult, setCloudTestResult] = useState<{
    ok: boolean;
    message: string;
    latency_ms?: number;
    available_models?: string[];
  } | null>(null);
  const [testingCloud, setTestingCloud] = useState(false);
  const [savingCloud, setSavingCloud] = useState(false);

  // Local LLM Mode (Ollama) Form State
  const [localUrl, setLocalUrl] = useState("http://localhost:11434");
  const [localModel, setLocalModel] = useState("qwen3.5:4b");
  const [localCtx, setLocalCtx] = useState(4096);
  const [localTimeout, setLocalTimeout] = useState(15);
  const [localTemp, setLocalTemp] = useState(0.15);
  const [localMaxTokens, setLocalMaxTokens] = useState(512);
  const [localFallback, setLocalFallback] = useState<"heuristic" | "safe_wait">("heuristic");
  const [installedModels, setInstalledModels] = useState<string[]>([]);
  const [localTestResult, setLocalTestResult] = useState<{
    ok: boolean;
    status: string;
    message: string;
    latency_ms?: number;
    recommended_model_installed?: boolean;
  } | null>(null);
  const [testingLocal, setTestingLocal] = useState(false);
  const [savingLocal, setSavingLocal] = useState(false);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const cfg: BrainConfigPayload = await fetchBrainConfig();
      setConfigData(cfg);
      const c = cfg.ai_cloud;
      const matchedPreset =
        cfg.presets.find((p) => p.label.toLowerCase() === c.provider_label.toLowerCase()) ||
        cfg.presets.find((p) => p.provider_type === c.provider_type);
      setPresetId(matchedPreset?.id || "openai");
      setProviderType(c.provider_type);
      setProviderLabel(c.provider_label);
      setApiCompatibility(c.api_compatibility);
      setBaseUrl(c.base_url);
      setModelName(c.model);
      setCloudTimeout(c.timeout_s);
      setCloudTemp(c.temperature);
      setCloudMaxTokens(c.max_tokens);
      setCloudFallback(c.fallback_policy);

      const l = cfg.local_llm;
      setLocalUrl(l.base_url);
      setLocalModel(l.model || "qwen3.5:4b");
      setLocalCtx(l.context_length);
      setLocalTimeout(l.timeout_s);
      setLocalTemp(l.temperature);
      setLocalMaxTokens(l.max_tokens);
      setLocalFallback(l.fallback_policy);

      if (cfg.operating_mode === "local_llm") {
        setActiveTab("local_llm");
      } else if (cfg.operating_mode === "ai") {
        setActiveTab("ai");
      }

      try {
        const localStat = await fetchLocalLLMStatus();
        setInstalledModels(localStat.installed_models || []);
        setLocalTestResult({
          ok: Boolean(localStat.ok),
          status: localStat.status,
          message: localStat.message,
          latency_ms: localStat.latency_ms,
          recommended_model_installed: localStat.recommended_model_installed,
        });
      } catch {
        // Handled cleanly in banner
      }
    } catch (err) {
      console.error("Failed loading AI settings:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAISettingsOpen) {
      setCloudTestResult(null);
      setApiKeyInput("");
      loadConfig();
    }
  }, [isAISettingsOpen]);

  if (!isAISettingsOpen) return null;

  const presets: ProviderPresetInfo[] = configData?.presets || [];
  const activePreset = presets.find((p) => p.id === presetId);

  const handleSelectPreset = (selectedId: string) => {
    setPresetId(selectedId);
    const preset = presets.find((p) => p.id === selectedId);
    if (preset) {
      setProviderType(preset.provider_type);
      setProviderLabel(preset.label);
      setApiCompatibility(preset.api_compatibility);
      setBaseUrl(preset.default_base_url);
      setModelName(preset.default_model);
    }
    setCloudTestResult(null);
  };

  const applyStatusToStore = (st: any) => {
    if (!st) return;
    setStore({
      aiMode: (st.mode || st.operating_mode || "heuristic") as BrainMode,
      brainProvider: st.provider || "heuristic",
      brainConnectionState: st.connection_state || "",
      brainModelName: st.model_name || "",
      circuitBreakerTripped: Boolean(st.circuit_tripped || st.circuit_breaker_tripped),
    });
  };

  const handleSwitchMode = async (mode: "baseline" | "heuristic" | "ai" | "local_llm") => {
    try {
      const res = await setBrainProvider(mode);
      applyStatusToStore(res);
      if (mode === "ai" || mode === "local_llm") {
        setActiveTab(mode);
      }
      await loadConfig();
    } catch (err) {
      console.error("Failed switching operating mode:", err);
    }
  };

  const handleTestCloud = async () => {
    setTestingCloud(true);
    setCloudTestResult(null);
    try {
      const res = await testAICloudConnection({
        provider_type: providerType,
        provider_label: providerLabel,
        api_compatibility: apiCompatibility,
        base_url: baseUrl.trim(),
        model: modelName.trim(),
        timeout_s: cloudTimeout,
        temperature: cloudTemp,
        max_tokens: cloudMaxTokens,
        fallback_policy: cloudFallback,
        organization_id: orgId.trim() || undefined,
        project_id: projectId.trim() || undefined,
        api_key: apiKeyInput.trim() || undefined,
      });
      setCloudTestResult({
        ok: Boolean(res.ok),
        message: res.message || (res.ok ? "Connection verified" : "Connection failed"),
        latency_ms: res.latency_ms,
        available_models: res.available_models || [],
      });
    } catch (err: any) {
      setCloudTestResult({
        ok: false,
        message: err?.message || "Connection test failed",
      });
    } finally {
      setTestingCloud(false);
    }
  };

  const handleSaveCloud = async (activate: boolean) => {
    setSavingCloud(true);
    try {
      const res = await updateAICloudConfig({
        provider_type: providerType,
        provider_label: providerLabel,
        api_compatibility: apiCompatibility,
        base_url: baseUrl.trim(),
        model: modelName.trim(),
        timeout_s: cloudTimeout,
        temperature: cloudTemp,
        max_tokens: cloudMaxTokens,
        fallback_policy: cloudFallback,
        organization_id: orgId.trim() || undefined,
        project_id: projectId.trim() || undefined,
        api_key: apiKeyInput.trim() || undefined,
        activate,
      });
      setApiKeyInput("");
      applyStatusToStore(res.brain_status);
      setCloudTestResult({
        ok: true,
        message: activate
          ? `Saved credentials & activated AI Mode (${providerLabel} · ${modelName}).`
          : "Saved Cloud AI configuration.",
      });
      await loadConfig();
    } catch (err: any) {
      setCloudTestResult({
        ok: false,
        message: err?.message || "Failed saving configuration",
      });
    } finally {
      setSavingCloud(false);
    }
  };

  const handleClearKey = async () => {
    setSavingCloud(true);
    try {
      const res = await updateAICloudConfig({
        provider_type: providerType,
        clear_api_key: true,
      });
      setApiKeyInput("");
      applyStatusToStore(res.brain_status);
      setCloudTestResult({ ok: true, message: "Cleared stored API key from server memory." });
      await loadConfig();
    } finally {
      setSavingCloud(false);
    }
  };

  const handleTestLocal = async () => {
    setTestingLocal(true);
    try {
      const res = await testLocalLLMConnection({
        base_url: localUrl.trim(),
        model: localModel.trim(),
        context_length: localCtx,
        timeout_s: localTimeout,
        temperature: localTemp,
        max_tokens: localMaxTokens,
        fallback_policy: localFallback,
      });
      setInstalledModels(res.available_models || []);
      setLocalTestResult({
        ok: Boolean(res.ok),
        status: res.status || (res.ok ? "connected" : "offline"),
        message: res.message || "Ollama check completed",
        latency_ms: res.latency_ms,
        recommended_model_installed: res.recommended_model_installed,
      });
    } catch (err: any) {
      setLocalTestResult({
        ok: false,
        status: "error",
        message: err?.message || "Failed to connect to Ollama",
      });
    } finally {
      setTestingLocal(false);
    }
  };

  const handleSaveLocal = async (activate: boolean) => {
    setSavingLocal(true);
    try {
      const res = await updateLocalLLMConfig({
        base_url: localUrl.trim(),
        model: localModel.trim() || "qwen3.5:4b",
        context_length: localCtx,
        timeout_s: localTimeout,
        temperature: localTemp,
        max_tokens: localMaxTokens,
        fallback_policy: localFallback,
        activate,
      });
      applyStatusToStore(res.brain_status);
      setLocalTestResult({
        ok: true,
        status: "saved",
        message: activate
          ? `Activated Local LLM Mode (Ollama · ${localModel.trim() || "qwen3.5:4b"}).`
          : "Saved Local LLM configuration.",
      });
      await loadConfig();
    } catch (err: any) {
      setLocalTestResult({
        ok: false,
        status: "error",
        message: err?.message || "Failed saving Local LLM config",
      });
    } finally {
      setSavingLocal(false);
    }
  };

  const discoveredModels = cloudTestResult?.available_models || [];
  const suggestedModels = Array.from(
    new Set([...(activePreset?.suggested_models || []), ...discoveredModels])
  );

  const inputCls =
    "w-full px-3 py-2 rounded-xl bg-[var(--studio-surface-subtle)] border border-[var(--studio-border-strong)] text-[var(--studio-text-primary)] placeholder-[var(--studio-text-muted)] focus:outline-none focus:border-studio-terracotta text-xs";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 backdrop-blur-sm p-4">
      <div className="studio-card-modal studio-drawer-enter w-full max-w-4xl rounded-2xl flex flex-col max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--studio-border)] bg-[var(--studio-surface-subtle)]">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-studio-terracotta/14 text-studio-terracotta border border-studio-terracotta/25">
              <Sparkles className="w-5 h-5" strokeWidth={1.5} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-[var(--studio-text-primary)]">
                AI Operations &amp; Local LLM Configuration
              </h2>
              <p className="text-xs text-[var(--studio-text-muted)]">
                Active state:{" "}
                <span className="text-studio-terracotta font-medium">
                  {store.brainConnectionState || store.aiMode}
                </span>
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setStore({ isAISettingsOpen: false })}
            className="studio-btn p-1.5 rounded-xl text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)] hover:bg-black/5 dark:hover:bg-white/10 cursor-pointer"
            aria-label="Close AI Settings"
          >
            <X className="w-5 h-5" strokeWidth={1.5} />
          </button>
        </div>

        {/* Mode Switcher Cards */}
        <div className="px-6 pt-4 pb-3 border-b border-[var(--studio-border)]">
          <div className="text-[11px] font-medium text-[var(--studio-text-muted)] mb-2">
            Operating mode
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {[
              { id: "baseline" as const, title: "Baseline", desc: "Fixed dispatcher without Brain actions" },
              { id: "heuristic" as const, title: "Heuristic", desc: "Fast deterministic specialist rules" },
              { id: "ai" as const, title: "AI Mode (Cloud)", desc: "User API key & custom endpoint" },
              { id: "local_llm" as const, title: "Local LLM (Ollama)", desc: "On-device Qwen 3.5 4B inference" },
            ].map((m) => {
              const active = store.aiMode === m.id;
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => handleSwitchMode(m.id)}
                  className={`studio-tile-interactive text-left p-2.5 rounded-xl border cursor-pointer ${
                    active
                      ? "bg-studio-terracotta/12 border-studio-terracotta/50 text-[var(--studio-text-primary)] shadow-sm"
                      : "bg-[var(--studio-surface-subtle)] border-[var(--studio-border)] text-[var(--studio-text-secondary)]"
                  }`}
                >
                  <div className="text-xs font-semibold flex items-center justify-between">
                    <span>{m.title}</span>
                    {active && <span className="w-2 h-2 rounded-full bg-studio-terracotta" />}
                  </div>
                  <div className="text-[10.5px] text-[var(--studio-text-muted)] mt-0.5 leading-snug">
                    {m.desc}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-[var(--studio-border)] px-6 bg-[var(--studio-surface-subtle)]">
          <button
            type="button"
            onClick={() => setActiveTab("ai")}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 flex items-center gap-1.5 transition-colors duration-150 cursor-pointer ${
              activeTab === "ai"
                ? "border-studio-terracotta text-studio-terracotta"
                : "border-transparent text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)]"
            }`}
          >
            <Cloud className="w-3.5 h-3.5" strokeWidth={1.5} />
            <span>AI Mode (Cloud API)</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("local_llm")}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 flex items-center gap-1.5 transition-colors duration-150 cursor-pointer ${
              activeTab === "local_llm"
                ? "border-studio-sage text-[#1D6144] dark:text-emerald-300"
                : "border-transparent text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)]"
            }`}
          >
            <Cpu className="w-3.5 h-3.5" strokeWidth={1.5} />
            <span>Local LLM Mode (Ollama · qwen3.5:4b)</span>
          </button>
        </div>

        {/* Form Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5 text-xs">
          {loading && !configData ? (
            <div className="py-10 flex items-center justify-center text-[var(--studio-text-muted)] gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading AI configuration...
            </div>
          ) : activeTab === "ai" ? (
            <div className="space-y-4">
              <div className="flex items-start gap-2.5 p-3 rounded-xl bg-amber-600/10 border border-amber-700/25 text-[var(--studio-text-secondary)]">
                <KeyRound className="w-4 h-4 text-[#B4691E] dark:text-amber-300 shrink-0 mt-0.5" strokeWidth={1.5} />
                <div>
                  <span className="font-semibold text-[var(--studio-text-primary)]">Credential Isolation:</span> API keys entered here are kept exclusively in backend process memory for outbound model requests. Keys are never written to browser localStorage, logged, returned in responses, or sent in prompts.
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-[var(--studio-text-secondary)] font-semibold mb-1">
                    Provider Preset
                  </label>
                  <select
                    value={presetId}
                    onChange={(e) => handleSelectPreset(e.target.value)}
                    className={inputCls}
                  >
                    {presets.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-[var(--studio-text-secondary)] font-semibold mb-1">
                    API Compatibility Protocol
                  </label>
                  <select
                    value={apiCompatibility}
                    onChange={(e) => setApiCompatibility(e.target.value as any)}
                    className={inputCls}
                  >
                    <option value="openai_chat">OpenAI Chat Completions (/chat/completions)</option>
                    <option value="openai_responses">OpenAI Responses API (/responses)</option>
                    <option value="anthropic_messages">Anthropic Messages API (/v1/messages)</option>
                  </select>
                </div>

                <div className="md:col-span-2">
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-[var(--studio-text-secondary)] font-semibold">API Key</label>
                    {configData?.ai_cloud.has_api_key ? (
                      <span className="text-[11px] text-[#1D6144] dark:text-emerald-300 font-mono flex items-center gap-1.5 tabular-nums">
                        Configured ({configData.ai_cloud.masked_api_key} · {configData.ai_cloud.key_source})
                        <button
                          type="button"
                          onClick={handleClearKey}
                          className="text-studio-crimson hover:underline ml-2 flex items-center gap-0.5 cursor-pointer"
                        >
                          <Trash2 className="w-3 h-3" strokeWidth={1.5} /> Clear
                        </button>
                      </span>
                    ) : (
                      <span className="text-[11px] text-[#B4691E] dark:text-amber-300">No key configured yet</span>
                    )}
                  </div>
                  <div className="relative">
                    <input
                      type={showApiKey ? "text" : "password"}
                      autoComplete="off"
                      value={apiKeyInput}
                      onChange={(e) => setApiKeyInput(e.target.value)}
                      placeholder={
                        configData?.ai_cloud.has_api_key
                          ? "Leave blank to keep existing key, or paste new key to replace"
                          : "Paste API key (stored securely in backend memory only)"
                      }
                      className={`${inputCls} font-mono pr-10`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowApiKey(!showApiKey)}
                      className="absolute right-2.5 top-2 text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)] cursor-pointer"
                    >
                      {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-[var(--studio-text-secondary)] font-semibold mb-1">
                    Base Endpoint URL
                  </label>
                  <input
                    type="text"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    placeholder="https://api.openai.com/v1"
                    className={`${inputCls} font-mono`}
                  />
                </div>

                <div>
                  <label className="block text-[var(--studio-text-secondary)] font-semibold mb-1">
                    Model Name
                  </label>
                  <input
                    type="text"
                    value={modelName}
                    onChange={(e) => setModelName(e.target.value)}
                    placeholder="gpt-4o-mini or custom model slug"
                    className={`${inputCls} font-mono`}
                  />
                  {suggestedModels.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {suggestedModels.slice(0, 6).map((m) => (
                        <button
                          key={m}
                          type="button"
                          onClick={() => setModelName(m)}
                          className={`studio-btn px-2 py-0.5 rounded-lg text-[10px] font-mono border cursor-pointer ${
                            modelName === m
                              ? "bg-studio-terracotta/15 border-studio-terracotta/50 text-[#A53420] dark:text-[#FFA991]"
                              : "bg-[var(--studio-surface-subtle)] border-[var(--studio-border)] text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)]"
                          }`}
                        >
                          {m}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 border-t border-[var(--studio-border)]">
                <div>
                  <label className="block text-[var(--studio-text-muted)] mb-1">Timeout (s)</label>
                  <input
                    type="number"
                    step="1"
                    min="1"
                    max="180"
                    value={cloudTimeout}
                    onChange={(e) => setCloudTimeout(Number(e.target.value))}
                    className={`${inputCls} font-mono`}
                  />
                </div>
                <div>
                  <label className="block text-[var(--studio-text-muted)] mb-1">Temperature</label>
                  <input
                    type="number"
                    step="0.05"
                    min="0"
                    max="2"
                    value={cloudTemp}
                    onChange={(e) => setCloudTemp(Number(e.target.value))}
                    className={`${inputCls} font-mono`}
                  />
                </div>
                <div>
                  <label className="block text-[var(--studio-text-muted)] mb-1">Max Tokens</label>
                  <input
                    type="number"
                    step="64"
                    min="128"
                    max="8192"
                    value={cloudMaxTokens}
                    onChange={(e) => setCloudMaxTokens(Number(e.target.value))}
                    className={`${inputCls} font-mono`}
                  />
                </div>
                <div>
                  <label className="block text-[var(--studio-text-muted)] mb-1">On Error Fallback</label>
                  <select
                    value={cloudFallback}
                    onChange={(e) => setCloudFallback(e.target.value as any)}
                    className={inputCls}
                  >
                    <option value="heuristic">Heuristic Fallback</option>
                    <option value="safe_wait">Safe Wait Only</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[var(--studio-text-muted)] mb-1">Org ID (optional)</label>
                  <input
                    type="text"
                    value={orgId}
                    onChange={(e) => setOrgId(e.target.value)}
                    placeholder="org-..."
                    className={`${inputCls} font-mono`}
                  />
                </div>
                <div>
                  <label className="block text-[var(--studio-text-muted)] mb-1">Project ID (optional)</label>
                  <input
                    type="text"
                    value={projectId}
                    onChange={(e) => setProjectId(e.target.value)}
                    placeholder="proj_..."
                    className={`${inputCls} font-mono`}
                  />
                </div>
              </div>

              {cloudTestResult && (
                <div
                  className={`p-3 rounded-xl border flex items-center gap-2.5 ${
                    cloudTestResult.ok
                      ? "bg-emerald-600/12 border-emerald-700/30 text-[#1D6144] dark:text-emerald-300"
                      : "bg-red-600/12 border-red-700/30 text-[#9E2418] dark:text-red-300"
                  }`}
                >
                  {cloudTestResult.ok ? (
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                  ) : (
                    <XCircle className="w-4 h-4 shrink-0" />
                  )}
                  <div className="flex-1">
                    {cloudTestResult.message}
                    {cloudTestResult.latency_ms ? ` (${cloudTestResult.latency_ms}ms)` : ""}
                  </div>
                </div>
              )}

              <div className="flex flex-wrap items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={handleTestCloud}
                  disabled={testingCloud}
                  className="studio-btn px-4 py-2 rounded-xl bg-[var(--studio-surface-subtle)] hover:bg-[var(--studio-surface-elevated)] border border-[var(--studio-border-strong)] text-[var(--studio-text-primary)] font-semibold flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  {testingCloud ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                  Test Connection
                </button>
                <button
                  type="button"
                  onClick={() => handleSaveCloud(false)}
                  disabled={savingCloud}
                  className="studio-btn px-4 py-2 rounded-xl bg-[var(--studio-surface-elevated)] border border-[var(--studio-border-strong)] text-[var(--studio-text-primary)] font-semibold cursor-pointer disabled:opacity-50"
                >
                  Save Settings
                </button>
                <button
                  type="button"
                  onClick={() => handleSaveCloud(true)}
                  disabled={savingCloud}
                  className="studio-btn px-4 py-2 rounded-xl bg-studio-terracotta hover:bg-studio-vermilion text-white font-semibold cursor-pointer disabled:opacity-50"
                >
                  Save &amp; Activate AI Mode
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="p-3.5 rounded-xl bg-emerald-600/10 border border-emerald-700/25 flex items-start gap-2.5 text-[var(--studio-text-secondary)]">
                <Server className="w-4 h-4 text-[#1D6144] dark:text-emerald-300 shrink-0 mt-0.5" strokeWidth={1.5} />
                <div>
                  <div className="font-semibold text-[var(--studio-text-primary)]">
                    Local Ollama Inference — Zero External API Dependency
                  </div>
                  <div className="text-[11px] text-[var(--studio-text-muted)] mt-0.5">
                    Recommended initial model: <code className="px-1.5 py-0.5 rounded bg-[var(--studio-surface-elevated)] font-mono text-[var(--studio-text-primary)]">qwen3.5:4b</code>. Install locally with{" "}
                    <code className="px-1.5 py-0.5 rounded bg-[var(--studio-surface-elevated)] font-mono">ollama pull qwen3.5:4b</code>. Local LLM failures stay strictly local and never silently invoke cloud APIs.
                  </div>
                </div>
              </div>

              {localTestResult && (
                <div
                  className={`p-3 rounded-xl border flex items-center gap-2.5 ${
                    localTestResult.ok
                      ? "bg-emerald-600/12 border-emerald-700/30 text-[#1D6144] dark:text-emerald-300"
                      : "bg-amber-600/12 border-amber-700/30 text-[#8F4F0D] dark:text-amber-300"
                  }`}
                >
                  {localTestResult.ok ? (
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                  ) : (
                    <ShieldAlert className="w-4 h-4 shrink-0" />
                  )}
                  <div className="flex-1">
                    {localTestResult.message}
                    {localTestResult.latency_ms ? ` (${localTestResult.latency_ms}ms)` : ""}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-[var(--studio-text-secondary)] font-semibold mb-1">
                    Ollama Base URL
                  </label>
                  <input
                    type="text"
                    value={localUrl}
                    onChange={(e) => setLocalUrl(e.target.value)}
                    placeholder="http://localhost:11434"
                    className={`${inputCls} font-mono`}
                  />
                </div>
                <div>
                  <label className="block text-[var(--studio-text-secondary)] font-semibold mb-1">
                    Local Model Tag
                  </label>
                  <input
                    type="text"
                    value={localModel}
                    onChange={(e) => setLocalModel(e.target.value)}
                    placeholder="qwen3.5:4b"
                    className={`${inputCls} font-mono`}
                  />
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {Array.from(new Set(["qwen3.5:4b", ...installedModels])).map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => setLocalModel(m)}
                        className={`studio-btn px-2 py-0.5 rounded-lg text-[10px] font-mono border cursor-pointer ${
                          localModel === m
                            ? "bg-emerald-600/15 border-emerald-700/40 text-[#1D6144] dark:text-emerald-300"
                            : "bg-[var(--studio-surface-subtle)] border-[var(--studio-border)] text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)]"
                        }`}
                      >
                        {m}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 border-t border-[var(--studio-border)]">
                <div>
                  <label className="block text-[var(--studio-text-muted)] mb-1">Context (num_ctx)</label>
                  <input
                    type="number"
                    step="512"
                    min="512"
                    max="32768"
                    value={localCtx}
                    onChange={(e) => setLocalCtx(Number(e.target.value))}
                    className={`${inputCls} font-mono`}
                  />
                </div>
                <div>
                  <label className="block text-[var(--studio-text-muted)] mb-1">Timeout (s)</label>
                  <input
                    type="number"
                    step="1"
                    min="2"
                    max="180"
                    value={localTimeout}
                    onChange={(e) => setLocalTimeout(Number(e.target.value))}
                    className={`${inputCls} font-mono`}
                  />
                </div>
                <div>
                  <label className="block text-[var(--studio-text-muted)] mb-1">Temperature</label>
                  <input
                    type="number"
                    step="0.05"
                    min="0"
                    max="2"
                    value={localTemp}
                    onChange={(e) => setLocalTemp(Number(e.target.value))}
                    className={`${inputCls} font-mono`}
                  />
                </div>
                <div>
                  <label className="block text-[var(--studio-text-muted)] mb-1">On Error Fallback</label>
                  <select
                    value={localFallback}
                    onChange={(e) => setLocalFallback(e.target.value as any)}
                    className={inputCls}
                  >
                    <option value="heuristic">Heuristic Fallback</option>
                    <option value="safe_wait">Safe Wait Only</option>
                  </select>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={handleTestLocal}
                  disabled={testingLocal}
                  className="studio-btn px-4 py-2 rounded-xl bg-[var(--studio-surface-subtle)] hover:bg-[var(--studio-surface-elevated)] border border-[var(--studio-border-strong)] text-[var(--studio-text-primary)] font-semibold flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  {testingLocal ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                  Check Ollama &amp; Models
                </button>
                <button
                  type="button"
                  onClick={() => handleSaveLocal(false)}
                  disabled={savingLocal}
                  className="studio-btn px-4 py-2 rounded-xl bg-[var(--studio-surface-elevated)] border border-[var(--studio-border-strong)] text-[var(--studio-text-primary)] font-semibold cursor-pointer disabled:opacity-50"
                >
                  Save Settings
                </button>
                <button
                  type="button"
                  onClick={() => handleSaveLocal(true)}
                  disabled={savingLocal}
                  className="studio-btn px-4 py-2 rounded-xl bg-studio-sage hover:opacity-95 text-white font-semibold cursor-pointer disabled:opacity-50"
                >
                  Save &amp; Activate Local LLM
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
