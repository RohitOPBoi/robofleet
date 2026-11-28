import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  Brain,
  Download,
  Filter,
  Search,
  X,
  Zap,
} from "lucide-react";
import type { Decision } from "../../types/generated";
import { setStore, useStore } from "../../store/useStore";

const TRIGGER_LABELS: Record<string, string> = {
  all: "All",
  deadlock_detected: "Deadlocks",
  order_at_risk: "At-risk order",
  station_queue_imbalance: "Queue imbalance",
  critical_battery: "Low battery",
  periodic_heartbeat: "Heartbeat",
  supervisor_command: "Supervisor",
};

const ENTITY_ID_PATTERN = /(\bR-\d{3,}\b|\bORD-[A-Za-z0-9_-]+\b)/g;

const formatTriggerLabel = (trigger: string): string => {
  if (TRIGGER_LABELS[trigger]) return TRIGGER_LABELS[trigger];
  const spaced = trigger.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
};

export const DecisionLogPanel: React.FC = () => {
  const store = useStore();
  const { decisions, isDecisionLogOpen, aiMode, brainProvider, circuitBreakerTripped } = store;
  const [filterTrigger, setFilterTrigger] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [expandedDecisionId, setExpandedDecisionId] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (isDecisionLogOpen) {
      dialogRef.current?.focus();
    }
  }, [isDecisionLogOpen]);

  const triggerOptions = useMemo(() => {
    const seen = Array.from(new Set(decisions.map((d) => d.trigger).filter(Boolean)));
    const options = [{ id: "all", label: "All" }];
    for (const trig of seen) {
      options.push({ id: trig, label: formatTriggerLabel(trig) });
    }
    if (filterTrigger !== "all" && !seen.includes(filterTrigger)) {
      options.push({ id: filterTrigger, label: formatTriggerLabel(filterTrigger) });
    }
    return options;
  }, [decisions, filterTrigger]);

  const filteredDecisions = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return decisions.filter((d) => {
      if (filterTrigger !== "all" && d.trigger !== filterTrigger) return false;
      if (!q) return true;

      if ((d.decision_id || "").toLowerCase().includes(q)) return true;
      if ((d.rationale || "").toLowerCase().includes(q)) return true;
      if ((d.trigger || "").toLowerCase().includes(q)) return true;
      if ((d.situation_summary || "").toLowerCase().includes(q)) return true;
      if ((d.provider_name || "").toLowerCase().includes(q)) return true;
      if ((d.model_name || "").toLowerCase().includes(q)) return true;
      if ((d.attribution || "").toLowerCase().includes(q)) return true;

      if (
        d.final_commands?.some((cmd) =>
          JSON.stringify(cmd).toLowerCase().includes(q)
        )
      ) {
        return true;
      }
      if (
        d.rejected_commands?.some((rc) =>
          JSON.stringify(rc).toLowerCase().includes(q)
        )
      ) {
        return true;
      }
      if (
        d.proposals?.some(
          (p) =>
            (p.specialist || "").toLowerCase().includes(q) ||
            (p.action || "").toLowerCase().includes(q) ||
            (p.rationale || "").toLowerCase().includes(q) ||
            JSON.stringify(p.command || {}).toLowerCase().includes(q)
        )
      ) {
        return true;
      }
      return false;
    });
  }, [decisions, filterTrigger, searchQuery]);

  if (!isDecisionLogOpen) return null;

  const closePanel = () => setStore({ isDecisionLogOpen: false });

  const exportLog = () => {
    if (filteredDecisions.length === 0) return;
    const jsonStr = JSON.stringify(filteredDecisions, null, 2);
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `robofleet-ai-decisions-tick-${store.tick}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const getOutcomeBadge = (outcome: Decision["observed_outcome"]) => {
    switch (outcome) {
      case "improved":
        return (
          <span className="px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-[#1E7E53]/12 text-[#176441] dark:text-emerald-300 border border-[#1E7E53]/25 inline-flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[#176441] dark:bg-emerald-300" />
            Improved
          </span>
        );
      case "worsened":
        return (
          <span className="px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-[#B93829]/12 text-[#A32D20] dark:text-[#F28B7D] border border-[#B93829]/25 inline-flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[#A32D20] dark:bg-[#F28B7D]" />
            Worsened
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-[var(--studio-surface-subtle)] text-[var(--studio-text-secondary)] border border-[var(--studio-border)] inline-flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--studio-text-muted)]" />
            Neutral
          </span>
        );
    }
  };

  const selectEntity = (entityId: string) => {
    if (/^R-\d{3,}$/.test(entityId)) {
      setStore({
        selectedRobotId: entityId,
        selectedOrderId: null,
        isDecisionLogOpen: false,
      });
    } else if (/^ORD-[A-Za-z0-9_-]+$/.test(entityId)) {
      setStore({
        selectedOrderId: entityId,
        selectedRobotId: null,
        isDecisionLogOpen: false,
      });
    }
  };

  const renderTextWithEntityButtons = (text: string) => {
    const parts = text.split(ENTITY_ID_PATTERN);
    return parts.map((part, idx) => {
      const isRobot = /^R-\d{3,}$/.test(part);
      const isOrder = /^ORD-[A-Za-z0-9_-]+$/.test(part);
      if (!isRobot && !isOrder) {
        return <React.Fragment key={idx}>{part}</React.Fragment>;
      }
      return (
        <button
          key={idx}
          type="button"
          onClick={() => selectEntity(part)}
          className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded-[6px] font-mono text-xs font-semibold bg-[#D9533B]/10 hover:bg-[#D9533B]/20 text-[#B83B24] dark:text-[#E87454] border border-[#D9533B]/25 transition-colors duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D9533B]/40"
          title={`Inspect ${part} on map`}
        >
          {part}
        </button>
      );
    });
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#191310]/65 backdrop-blur-sm p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) closePanel();
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.stopPropagation();
          closePanel();
        }
      }}
    >
      <div
        ref={dialogRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="decision-log-title"
        className="studio-card-modal studio-drawer-enter bg-[#FFFBF8] dark:bg-[#241B16] border border-[var(--studio-border-strong)] shadow-[var(--studio-shadow)] text-[var(--studio-text-primary)] rounded-[20px] w-full max-w-4xl h-[85vh] flex flex-col overflow-hidden select-text outline-none"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-[var(--studio-border)] bg-[var(--studio-surface-subtle)]/55 flex items-center justify-between gap-3 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-[12px] bg-[#D9533B]/12 text-[#B83B24] dark:text-[#E87454] border border-[#D9533B]/25 flex items-center justify-center shrink-0">
              <Brain className="w-5 h-5" strokeWidth={1.5} />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h2
                  id="decision-log-title"
                  className="text-base font-semibold text-[var(--studio-text-primary)] tracking-tight"
                >
                  AI operations decision log
                </h2>
                <span
                  className={`px-2.5 py-0.5 rounded-full text-[11px] font-mono border font-medium ${
                    circuitBreakerTripped
                      ? "bg-[#B93829]/12 text-[#A32D20] dark:text-[#F28B7D] border-[#B93829]/30"
                      : store.brainInferenceInFlight
                        ? "bg-[#B4691E]/12 text-[#85470D] dark:text-amber-300 border-[#B4691E]/30"
                        : aiMode === "baseline"
                          ? "bg-[var(--studio-surface-subtle)] text-[var(--studio-text-secondary)] border-[var(--studio-border)]"
                          : "bg-[#1E7E53]/12 text-[#176441] dark:text-emerald-300 border-[#1E7E53]/25"
                  }`}
                >
                  {store.brainConnectionState || `${aiMode} (${brainProvider})`}
                </span>
                <span className="text-xs text-[var(--studio-text-muted)] font-mono tabular-nums">
                  {filteredDecisions.length === decisions.length
                    ? `${decisions.length} decisions`
                    : `${filteredDecisions.length} / ${decisions.length} decisions`}
                </span>
                <button
                  type="button"
                  onClick={() => setStore({ isDecisionLogOpen: false, isAISettingsOpen: true })}
                  className="studio-btn px-2.5 py-0.5 rounded-[8px] text-[11px] font-medium bg-[#D9533B]/12 hover:bg-[#D9533B]/20 text-[#B83B24] dark:text-[#E87454] border border-[#D9533B]/25 cursor-pointer"
                >
                  AI &amp; local settings
                </button>
              </div>
              <p className="text-xs text-[var(--studio-text-muted)] mt-0.5">
                Every action taken by the mission orchestrator and specialists with grounded rationales
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              disabled={filteredDecisions.length === 0}
              onClick={exportLog}
              className="studio-btn flex items-center gap-1.5 px-3 py-1.5 rounded-[10px] bg-[var(--studio-surface-elevated)] hover:bg-[var(--studio-surface-subtle)] text-[var(--studio-text-primary)] border border-[var(--studio-border-strong)] text-xs font-medium cursor-pointer disabled:opacity-45 disabled:cursor-not-allowed"
              title={
                filteredDecisions.length === 0
                  ? "No matching decisions to export"
                  : "Export visible decisions as JSON"
              }
            >
              <Download className="w-3.5 h-3.5" strokeWidth={1.5} />
              <span>Export</span>
            </button>
            <button
              type="button"
              onClick={closePanel}
              className="studio-btn p-2 rounded-[10px] text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-subtle)] cursor-pointer"
              aria-label="Close decision log"
            >
              <X className="w-4 h-4" strokeWidth={1.5} />
            </button>
          </div>
        </div>

        {/* Circuit Breaker Warning Banner */}
        {circuitBreakerTripped && (
          <div
            role="alert"
            className="px-6 py-2.5 bg-[#B93829]/12 border-b border-[#B93829]/30 text-[#A32D20] dark:text-[#F28B7D] flex items-center justify-between gap-3 text-xs shrink-0"
          >
            <div className="flex items-center gap-2 min-w-0">
              <AlertTriangle className="w-4 h-4 shrink-0" strokeWidth={1.5} />
              <span>
                <strong className="font-semibold">Brain circuit breaker tripped:</strong>{" "}
                consecutive inference failures triggered automatic deterministic fallback.
              </span>
            </div>
            <button
              type="button"
              onClick={() => setStore({ isDecisionLogOpen: false, isAISettingsOpen: true })}
              className="text-xs font-semibold underline hover:opacity-80 transition-opacity duration-150 cursor-pointer shrink-0"
            >
              Review provider
            </button>
          </div>
        )}

        {/* Filter & Search Bar */}
        <div className="px-6 py-2.5 bg-[var(--studio-surface-subtle)]/35 border-b border-[var(--studio-border)] flex flex-wrap items-center justify-between gap-3 shrink-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Filter className="w-3.5 h-3.5 text-[var(--studio-text-muted)]" strokeWidth={1.5} />
            <span className="text-xs text-[var(--studio-text-muted)] font-medium">Trigger</span>
            <div className="flex items-center gap-1 flex-wrap">
              {triggerOptions.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  aria-pressed={filterTrigger === t.id}
                  onClick={() => setFilterTrigger(t.id)}
                  className={`studio-btn px-2.5 py-1 rounded-[8px] text-[11px] font-medium cursor-pointer ${
                    filterTrigger === t.id
                      ? "bg-[#C2432D] hover:bg-[#A93521] text-[#FFFBF8] font-semibold"
                      : "text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)] hover:bg-[var(--studio-surface-subtle)]"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          <div className="relative">
            <Search
              className="w-3.5 h-3.5 text-[var(--studio-text-muted)] absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none"
              strokeWidth={1.5}
            />
            <input
              type="text"
              aria-label="Search decisions"
              placeholder="Search decisions"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-3 py-1.5 bg-[var(--studio-surface-elevated)] border border-[var(--studio-border-strong)] rounded-[8px] text-xs text-[var(--studio-text-primary)] placeholder:text-[var(--studio-text-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D9533B]/40 focus:border-[#D9533B] transition-colors duration-200 w-56"
            />
          </div>
        </div>

        {/* Decisions Feed List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-3.5">
          {filteredDecisions.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-[var(--studio-text-muted)]">
              <Brain className="w-10 h-10 mb-2 text-[var(--studio-text-muted)]" strokeWidth={1.5} />
              <p className="text-sm font-medium text-[var(--studio-text-secondary)]">
                No decisions matching filter
              </p>
              <p className="text-xs text-[var(--studio-text-muted)] mt-1">
                The AI brain logs decisions automatically as events trigger or orders arrive.
              </p>
            </div>
          ) : (
            filteredDecisions.map((decision) => {
              const isExpanded = expandedDecisionId === decision.decision_id;
              const rationaleText =
                decision.rationale ||
                decision.situation_summary ||
                "Operational flow balanced across picking stations.";

              return (
                <div
                  key={decision.decision_id}
                  className="p-4 rounded-[12px] bg-[var(--studio-surface-elevated)]/80 hover:bg-[var(--studio-surface-elevated)] border border-[var(--studio-border)] hover:border-[var(--studio-border-strong)] transition-[background-color,border-color] duration-200 flex flex-col gap-3"
                >
                  {/* Top Row: Tick, ID, Trigger, Latency, Outcome */}
                  <div className="flex items-center justify-between gap-2 flex-wrap text-xs">
                    <div className="flex items-center gap-2 font-mono flex-wrap">
                      <span className="px-2 py-0.5 rounded-[8px] bg-[var(--studio-surface-subtle)] border border-[var(--studio-border)] text-[var(--studio-text-primary)] font-semibold text-[11px] tabular-nums">
                        T+{decision.tick}
                      </span>
                      <span className="text-[#B83B24] dark:text-[#E87454] font-semibold tabular-nums">
                        #{decision.decision_id}
                      </span>
                      <span className="px-2 py-0.5 rounded-[8px] text-[10px] font-mono bg-[#B4691E]/10 text-[#85470D] dark:text-amber-300 border border-[#B4691E]/25">
                        {decision.trigger}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded-[8px] text-[10px] font-mono border ${
                          decision.fallback_used
                            ? "bg-[#B4691E]/12 text-[#85470D] dark:text-amber-300 border-[#B4691E]/30"
                            : decision.provider_mode === "ai"
                              ? "bg-[#D9533B]/12 text-[#B83B24] dark:text-[#E87454] border-[#D9533B]/30"
                              : decision.provider_mode === "local_llm"
                                ? "bg-[#1E7E53]/12 text-[#176441] dark:text-emerald-300 border-[#1E7E53]/30"
                                : "bg-[var(--studio-surface-subtle)] text-[var(--studio-text-secondary)] border-[var(--studio-border)]"
                        }`}
                        title={decision.fallback_reason || decision.attribution || ""}
                      >
                        {decision.attribution ||
                          `${decision.provider_name || decision.provider_mode}${decision.model_name ? ` · ${decision.model_name}` : ""}`}
                      </span>
                      <span
                        className="text-[var(--studio-text-muted)] text-[10px] tabular-nums"
                        title="Deterministic Situation Brief SHA256"
                      >
                        brief:{decision.brief_hash}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      {getOutcomeBadge(decision.observed_outcome)}
                      <span className="text-[11px] font-mono text-[var(--studio-text-muted)] tabular-nums">
                        {decision.latency_ms}ms
                      </span>
                      {decision.cost_usd > 0 && (
                        <span className="text-[11px] font-mono text-[#176441] dark:text-emerald-300 bg-[#1E7E53]/10 px-2 py-0.5 rounded-[8px] border border-[#1E7E53]/25 tabular-nums">
                          ${decision.cost_usd.toFixed(4)}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Operational Rationale */}
                  <div className="text-sm text-[var(--studio-text-primary)] leading-relaxed font-sans bg-[var(--studio-surface-subtle)]/65 p-3 rounded-[12px] border border-[var(--studio-border)]">
                    <span className="text-[var(--studio-text-muted)] mr-1.5 font-medium">
                      Rationale:
                    </span>
                    {renderTextWithEntityButtons(rationaleText)}
                    {decision.fallback_used && decision.fallback_reason && (
                      <div className="mt-1.5 text-[11px] font-mono text-[#85470D] dark:text-amber-300">
                        Fallback trigger: {decision.fallback_reason}
                      </div>
                    )}
                  </div>

                  {/* Rejected Commands / Outcome Metrics Badges */}
                  {decision.rejected_commands && decision.rejected_commands.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 text-xs">
                      <span className="text-[#A32D20] dark:text-[#F28B7D] text-[11px] font-medium">
                        Rejected commands
                      </span>
                      {decision.rejected_commands.map((rc: any, rIdx: number) => (
                        <span
                          key={rIdx}
                          className="px-2 py-0.5 rounded-[8px] bg-[#B93829]/12 text-[#A32D20] dark:text-[#F28B7D] border border-[#B93829]/25 font-mono text-[10px]"
                          title={
                            rc.reason ||
                            rc.rejection_reason ||
                            "Rejected by validator or safety governance"
                          }
                        >
                          {rc.command?.command_type || rc.raw?.command_type || "invalid"} (
                          {rc.reason || rc.rejection_reason || "rejected"})
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Commands Executed Summary */}
                  {decision.final_commands && decision.final_commands.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 text-xs">
                      <span className="text-[var(--studio-text-muted)] text-[11px] font-medium">
                        Approved commands
                      </span>
                      {decision.final_commands.map((cmd, cIdx) => (
                        <span
                          key={cIdx}
                          className="px-2 py-0.5 rounded-[8px] bg-[#1E7E53]/10 text-[#176441] dark:text-emerald-300 border border-[#1E7E53]/25 font-mono text-[11px] inline-flex items-center gap-1"
                        >
                          <Zap className="w-3 h-3" strokeWidth={1.5} />
                          {cmd.command_type}
                          {cmd.order_id && `(${cmd.order_id})`}
                          {cmd.robot_id && `(${cmd.robot_id})`}
                          {cmd.zone_id && `(${cmd.zone_id})`}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Expand/Collapse Proposals Drilldown */}
                  <div className="flex items-center justify-between pt-2 border-t border-[var(--studio-border)] text-[11px] text-[var(--studio-text-muted)]">
                    <div className="flex items-center gap-3 tabular-nums">
                      <span>
                        Specialists:{" "}
                        <strong className="text-[var(--studio-text-primary)] font-semibold">
                          {decision.proposals ? decision.proposals.length : 0} proposals
                        </strong>
                      </span>
                      <span>
                        Governance:{" "}
                        <strong
                          className={`capitalize font-semibold ${
                            decision.governance_outcome === "approved"
                              ? "text-[#176441] dark:text-emerald-300"
                              : decision.governance_outcome === "denied"
                                ? "text-[#A32D20] dark:text-[#F28B7D]"
                                : "text-[#85470D] dark:text-amber-300"
                          }`}
                        >
                          {decision.governance_outcome}
                        </strong>
                      </span>
                    </div>

                    <button
                      type="button"
                      aria-expanded={isExpanded}
                      onClick={() =>
                        setExpandedDecisionId(isExpanded ? null : decision.decision_id)
                      }
                      className="text-[#B83B24] dark:text-[#E87454] hover:text-[#A93521] flex items-center gap-1 font-medium transition-colors duration-150 cursor-pointer"
                    >
                      <span>
                        {isExpanded ? "Hide proposals" : "View specialist proposals"}
                      </span>
                      <ArrowRight
                        className={`w-3 h-3 transition-transform duration-200 ease-studio-drawer ${
                          isExpanded ? "rotate-90" : ""
                        }`}
                        strokeWidth={1.5}
                      />
                    </button>
                  </div>

                  {/* Expanded Proposals Drawer */}
                  {isExpanded && decision.proposals && (
                    <div className="mt-1 space-y-2.5 p-3.5 bg-[var(--studio-surface-subtle)]/75 rounded-[12px] border border-[var(--studio-border)]">
                      <h4 className="text-xs font-semibold text-[var(--studio-text-secondary)]">
                        Specialist proposals
                      </h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                        {decision.proposals.map((prop, pIdx) => (
                          <div
                            key={pIdx}
                            className="p-3 rounded-[12px] bg-[var(--studio-surface-elevated)] border border-[var(--studio-border)] text-xs flex flex-col gap-1"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-semibold text-[#B83B24] dark:text-[#E87454] capitalize flex items-center gap-1.5">
                                <Bot className="w-3 h-3" strokeWidth={1.5} />
                                {prop.specialist}
                              </span>
                              <span className="text-[11px] font-mono text-[var(--studio-text-muted)] tabular-nums">
                                Confidence: {(prop.confidence * 100).toFixed(0)}%
                              </span>
                            </div>
                            <div className="font-mono text-[11px] text-[#176441] dark:text-emerald-300">
                              Action: {prop.action}
                            </div>
                            <p className="text-[var(--studio-text-secondary)] text-[11px] leading-snug mt-0.5">
                              {prop.rationale}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
