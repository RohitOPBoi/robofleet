import React, { useState } from "react";
import {
  Activity,
  ArrowRight,
  Brain,
  CheckCircle2,
  Clock,
  Download,
  Filter,
  Search,
  Sliders,
  Sparkles,
  X,
  Zap,
} from "lucide-react";
import type { Decision } from "../../types/generated";
import { setStore, useStore } from "../../store/useStore";

export const DecisionLogPanel: React.FC = () => {
  const store = useStore();
  const { decisions, isDecisionLogOpen, aiMode, brainProvider } = store;
  const [filterTrigger, setFilterTrigger] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [expandedDecisionId, setExpandedDecisionId] = useState<string | null>(null);

  if (!isDecisionLogOpen) return null;

  const filteredDecisions = decisions.filter((d) => {
    if (filterTrigger !== "all" && d.trigger !== filterTrigger) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchId = d.decision_id.toLowerCase().includes(q);
      const matchRationale = d.rationale.toLowerCase().includes(q);
      const matchTrigger = d.trigger.toLowerCase().includes(q);
      return matchId || matchRationale || matchTrigger;
    }
    return true;
  });

  const exportLog = () => {
    const jsonStr = JSON.stringify(decisions, null, 2);
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
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-950/80 text-emerald-400 border border-emerald-800/80 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            Improved
          </span>
        );
      case "worsened":
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-950/80 text-rose-400 border border-rose-800/80 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
            Worsened
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-800 text-gray-300 border border-gray-700 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />
            Neutral
          </span>
        );
    }
  };

  const handleEntityClick = (text: string) => {
    const robotMatch = text.match(/\bR-\d{3,}\b/);
    if (robotMatch && store.robots[robotMatch[0]]) {
      setStore({ selectedRobotId: robotMatch[0] });
      return;
    }
    const orderMatch = text.match(/\bORD-[A-Za-z0-9_-]+\b/);
    if (orderMatch && store.orders[orderMatch[0]]) {
      setStore({ selectedOrderId: orderMatch[0] });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="bg-gray-950 border border-gray-800 rounded-2xl w-full max-w-4xl h-[85vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-800/80 bg-gray-900/60 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white shadow-lg shadow-indigo-500/25">
              <Brain className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white tracking-tight">AI Operations Decision Log</h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono uppercase bg-cyan-950 text-cyan-400 border border-cyan-800/80 font-bold">
                  {aiMode === "ai" ? `Live (${brainProvider})` : "Baseline Fallback"}
                </span>
                <span className="text-xs text-gray-400 font-mono">
                  ({decisions.length} decisions)
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-0.5">
                Every action taken by the Mission Orchestrator and Specialists with grounded rationales
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={exportLog}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-900 hover:bg-gray-800 text-gray-300 hover:text-white border border-gray-700/80 text-xs font-medium transition cursor-pointer active:scale-95"
              title="Export all decisions as JSON"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export</span>
            </button>
            <button
              type="button"
              onClick={() => setStore({ isDecisionLogOpen: false })}
              className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Filter & Search Bar */}
        <div className="px-6 py-2.5 bg-gray-900/40 border-b border-gray-800/80 flex flex-wrap items-center justify-between gap-3 shrink-0">
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-gray-400" />
            <span className="text-xs text-gray-400">Trigger:</span>
            <div className="flex items-center gap-1">
              {[
                { id: "all", label: "All" },
                { id: "order_at_risk", label: "At-Risk Order" },
                { id: "station_queue_imbalance", label: "Queue Imbalance" },
                { id: "critical_battery", label: "Low Battery" },
                { id: "periodic_heartbeat", label: "Heartbeat" },
              ].map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setFilterTrigger(t.id)}
                  className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition cursor-pointer ${
                    filterTrigger === t.id
                      ? "bg-indigo-600 text-white font-semibold shadow-sm"
                      : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/60"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          <div className="relative">
            <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search decisions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-3 py-1 bg-gray-950 border border-gray-800 rounded-lg text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-indigo-500 w-56"
            />
          </div>
        </div>

        {/* Decisions Feed List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-3.5 divide-y divide-gray-800/40">
          {filteredDecisions.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-gray-500">
              <Brain className="w-10 h-10 mb-2 stroke-[1.25] text-gray-600" />
              <p className="text-sm font-medium">No decisions matching filter</p>
              <p className="text-xs text-gray-600 mt-1">
                The AI brain will log decisions automatically as events trigger or orders arrive.
              </p>
            </div>
          ) : (
            filteredDecisions.map((decision) => {
              const isExpanded = expandedDecisionId === decision.decision_id;
              return (
                <div
                  key={decision.decision_id}
                  className="pt-3.5 first:pt-0 group transition-all"
                >
                  <div className="p-4 rounded-xl bg-gray-900/60 hover:bg-gray-900/90 border border-gray-800/70 hover:border-gray-700/80 transition-all flex flex-col gap-2.5">
                    {/* Top Row: Tick, ID, Trigger, Latency, Outcome */}
                    <div className="flex items-center justify-between gap-2 flex-wrap text-xs">
                      <div className="flex items-center gap-2 font-mono">
                        <span className="px-2 py-0.5 rounded bg-gray-800 text-gray-300 font-bold text-[11px]">
                          T+{decision.tick}
                        </span>
                        <span className="text-indigo-400 font-semibold">
                          #{decision.decision_id}
                        </span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-purple-950/60 text-purple-300 border border-purple-800/60">
                          {decision.trigger}
                        </span>
                        <span className="text-gray-500 text-[10px]" title="Deterministic Situation Brief SHA256">
                          brief:{decision.brief_hash}
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        {getOutcomeBadge(decision.observed_outcome)}
                        <span className="text-[11px] font-mono text-gray-400">
                          {decision.latency_ms}ms
                        </span>
                        {decision.cost_usd > 0 && (
                          <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/40 px-1.5 py-0.5 rounded border border-emerald-800/40">
                            ${decision.cost_usd.toFixed(4)}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Operational Rationale */}
                    <div
                      onClick={() => handleEntityClick(decision.rationale)}
                      className="text-sm text-gray-200 leading-relaxed font-sans bg-gray-950/50 p-3 rounded-lg border border-white/5 cursor-pointer hover:border-indigo-500/40 transition"
                      title="Click any referenced entity ID to inspect on map"
                    >
                      <span className="text-gray-400 mr-1.5 font-medium">Rationale:</span>
                      {decision.rationale || "Operational flow balanced across picking stations."}
                    </div>

                    {/* Commands Executed Summary */}
                    {decision.final_commands && decision.final_commands.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 text-xs">
                        <span className="text-gray-400 text-[11px] font-medium">Approved Commands:</span>
                        {decision.final_commands.map((cmd, idx) => (
                          <span
                            key={idx}
                            className="px-2 py-0.5 rounded-md bg-cyan-950/50 text-cyan-300 border border-cyan-800/50 font-mono text-[11px] flex items-center gap-1"
                          >
                            <Zap className="w-3 h-3 text-cyan-400" />
                            {cmd.command_type}
                            {cmd.order_id && `(${cmd.order_id})`}
                            {cmd.robot_id && `(${cmd.robot_id})`}
                            {cmd.zone_id && `(${cmd.zone_id})`}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Expand/Collapse Proposals Drilldown */}
                    <div className="flex items-center justify-between pt-1 border-t border-gray-800/40 text-[11px] text-gray-400">
                      <div className="flex items-center gap-3">
                        <span>
                          Specialists:{" "}
                          <strong className="text-gray-200">
                            {decision.proposals ? decision.proposals.length : 0} proposals
                          </strong>
                        </span>
                        <span>
                          Governance:{" "}
                          <strong
                            className={
                              decision.governance_outcome === "approved"
                                ? "text-emerald-400"
                                : "text-amber-400"
                            }
                          >
                            {decision.governance_outcome.toUpperCase()}
                          </strong>
                        </span>
                      </div>

                      <button
                        type="button"
                        onClick={() =>
                          setExpandedDecisionId(isExpanded ? null : decision.decision_id)
                        }
                        className="text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-medium cursor-pointer"
                      >
                        {isExpanded ? "Hide Proposals" : "View Specialists Proposals"}
                        <ArrowRight
                          className={`w-3 h-3 transition-transform ${isExpanded ? "rotate-90" : ""}`}
                        />
                      </button>
                    </div>

                    {/* Expanded Proposals Drawer */}
                    {isExpanded && decision.proposals && (
                      <div className="mt-2 space-y-2 p-3 bg-gray-950 rounded-lg border border-gray-800/80 animate-in fade-in">
                        <h4 className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">
                          Specialist Proposals
                        </h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                          {decision.proposals.map((prop, pIdx) => (
                            <div
                              key={pIdx}
                              className="p-2.5 rounded-lg bg-gray-900 border border-gray-800 text-xs flex flex-col gap-1"
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-bold text-indigo-300 capitalize flex items-center gap-1">
                                  <Sparkles className="w-3 h-3 text-indigo-400" />
                                  {prop.specialist}
                                </span>
                                <span className="text-[10px] font-mono text-gray-400">
                                  Confidence: {(prop.confidence * 100).toFixed(0)}%
                                </span>
                              </div>
                              <div className="font-mono text-[11px] text-cyan-400">
                                Action: {prop.action}
                              </div>
                              <p className="text-gray-300 text-[11px] leading-tight mt-0.5">
                                {prop.rationale}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
