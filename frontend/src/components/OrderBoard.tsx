import React, { useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  Layers,
  Package,
  Search,
  Truck,
  X,
} from "lucide-react";
import { setStore, useStore } from "../store/useStore";
import type { OrderStatus } from "../types/generated";

const getStatusBadgeStyle = (status: OrderStatus) => {
  switch (status) {
    case "RECEIVED":
    case "QUEUED":
      return "bg-stone-900/[0.06] text-[var(--studio-text-secondary)] border-[var(--studio-border-strong)] dark:bg-white/[0.08]";
    case "PLANNED":
      return "bg-amber-900/[0.08] text-[#58473D] border-stone-500/25 dark:bg-white/[0.09] dark:text-[#D3C3B8] dark:border-white/15";
    case "RETRIEVING":
      return "bg-[#E87454]/14 text-[#A9351F] border-[#D9533B]/30 dark:bg-[#E87454]/18 dark:text-[#FFA991] dark:border-[#E87454]/35";
    case "AT_STATION":
    case "PICKING":
      return "bg-amber-600/12 text-[#8F4F0D] border-amber-700/25 dark:bg-amber-500/16 dark:text-amber-300 dark:border-amber-500/35";
    case "CONSOLIDATING":
      return "bg-orange-600/12 text-[#9A4318] border-orange-700/25 dark:bg-orange-500/16 dark:text-orange-300 dark:border-orange-500/35";
    case "PACKED":
    case "READY_FOR_DISPATCH":
      return "bg-[#D9533B]/14 text-[#A53420] border-[#D9533B]/30 dark:bg-[#D9533B]/20 dark:text-[#FF9D8A] dark:border-[#D9533B]/40";
    case "HANDED_OVER":
      return "bg-emerald-600/12 text-[#1D6144] border-emerald-700/25 dark:bg-emerald-500/18 dark:text-emerald-300 dark:border-emerald-500/35 font-semibold";
    case "FAILED_PARTIAL":
    case "FAILED":
      return "bg-red-600/12 text-[#9E2418] border-red-700/25 dark:bg-red-500/18 dark:text-red-300 dark:border-red-500/35";
    case "CANCELLED":
      return "bg-stone-900/[0.04] text-[var(--studio-text-muted)] border-[var(--studio-border)] dark:bg-white/[0.04]";
    default:
      return "bg-stone-900/[0.05] text-[var(--studio-text-secondary)] border-[var(--studio-border)]";
  }
};

const formatOrderStatus = (status: OrderStatus): string => {
  const words = status.toLowerCase().split("_");
  return words.map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
};

const LIFECYCLE_STAGES: OrderStatus[] = [
  "RECEIVED",
  "PLANNED",
  "RETRIEVING",
  "PICKING",
  "CONSOLIDATING",
  "PACKED",
  "HANDED_OVER",
];

const getStageIndex = (status: OrderStatus): number => {
  if (status === "QUEUED") return 0;
  if (status === "AT_STATION") return 3;
  if (status === "READY_FOR_DISPATCH") return 5;
  const idx = LIFECYCLE_STAGES.indexOf(status);
  return idx >= 0 ? idx : 0;
};

export const OrderBoard: React.FC = () => {
  const { orders, tick, selectedOrderId } = useStore();
  const [activeTab, setActiveTab] = useState<"active" | "completed" | "at_risk" | "all">("active");
  const [search, setSearch] = useState("");

  const orderList = useMemo(() => Object.values(orders), [orders]);

  const filteredOrders = useMemo(() => {
    let list = orderList;

    if (activeTab === "active") {
      list = list.filter(
        (o) =>
          o.status !== "HANDED_OVER" &&
          o.status !== "CANCELLED" &&
          o.status !== "FAILED"
      );
    } else if (activeTab === "completed") {
      list = list.filter((o) => o.status === "HANDED_OVER");
    } else if (activeTab === "at_risk") {
      list = list.filter((o) => o.at_risk);
    }

    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (o) =>
          o.id.toLowerCase().includes(q) ||
          o.sla_tier.toLowerCase().includes(q) ||
          (o.tote_id && o.tote_id.toLowerCase().includes(q))
      );
    }

    // Sort: at-risk first, then by priority descending, then deadline ascending
    return list.sort((a, b) => {
      if (a.at_risk !== b.at_risk) return a.at_risk ? -1 : 1;
      if (b.priority !== a.priority) return b.priority - a.priority;
      return a.deadline_tick - b.deadline_tick;
    });
  }, [orderList, activeTab, search]);

  const atRiskCount = useMemo(() => orderList.filter((o) => o.at_risk).length, [orderList]);
  const activeCount = useMemo(
    () =>
      orderList.filter(
        (o) =>
          o.status !== "HANDED_OVER" &&
          o.status !== "CANCELLED" &&
          o.status !== "FAILED"
      ).length,
    [orderList]
  );
  const completedCount = useMemo(
    () => orderList.filter((o) => o.status === "HANDED_OVER").length,
    [orderList]
  );

  return (
    <div className="w-full h-full flex flex-col text-xs overflow-hidden bg-[var(--studio-surface)] text-[var(--studio-text-primary)]">
      {/* Board Header */}
      <div className="p-3 border-b border-[var(--studio-border)] bg-[var(--studio-surface-subtle)] shrink-0 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 font-semibold text-[var(--studio-text-primary)] text-[13px] tracking-tight">
            <Package className="w-4 h-4 text-[#A53420] dark:text-studio-coral shrink-0" strokeWidth={1.5} />
            <span>Fulfillment order journey</span>
          </div>
          <span className="font-mono text-[var(--studio-text-muted)] text-[11px] tabular-nums">
            {filteredOrders.length} orders
          </span>
        </div>

        {/* Search */}
        <div className="relative">
          <Search
            className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--studio-text-muted)] pointer-events-none"
            strokeWidth={1.5}
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search ID, tote, or tier"
            aria-label="Search orders"
            className="w-full bg-[var(--studio-surface-elevated)] border border-[var(--studio-border-strong)] rounded-xl pl-8 pr-8 py-1.5 text-xs text-[var(--studio-text-primary)] placeholder:text-[var(--studio-text-muted)] focus:outline-none focus:border-studio-terracotta transition-[border-color,background-color] duration-200"
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch("")}
              aria-label="Clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-md text-[var(--studio-text-muted)] hover:text-[var(--studio-text-primary)] hover:bg-stone-900/[0.06] dark:hover:bg-white/10 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" strokeWidth={1.5} />
            </button>
          )}
        </div>

        {/* Filter Tabs */}
        <div className="grid grid-cols-4 gap-1 bg-[var(--studio-surface-subtle)] p-1 rounded-xl border border-[var(--studio-border)] font-medium text-[11px]">
          <button
            type="button"
            onClick={() => setActiveTab("active")}
            className={`py-1 px-1.5 rounded-lg text-center flex items-center justify-center gap-1 cursor-pointer transition-colors duration-150 ${
              activeTab === "active"
                ? "bg-[var(--studio-surface-elevated)] text-[var(--studio-text-primary)] font-semibold shadow-sm"
                : "text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)]"
            }`}
          >
            <span>Active</span>
            <span className="px-1.5 py-0.5 rounded-full bg-stone-900/[0.08] dark:bg-white/10 text-[var(--studio-text-secondary)] text-[10px] leading-none tabular-nums">
              {activeCount}
            </span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("completed")}
            className={`py-1 px-1.5 rounded-lg text-center flex items-center justify-center gap-1 cursor-pointer transition-colors duration-150 ${
              activeTab === "completed"
                ? "bg-emerald-600/12 dark:bg-emerald-500/20 text-[#1D6144] dark:text-emerald-300 font-semibold shadow-sm"
                : "text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)]"
            }`}
          >
            <span>Done</span>
            {completedCount > 0 && (
              <span className="px-1.5 py-0.5 rounded-full bg-emerald-700/15 dark:bg-emerald-500/25 text-[#1D6144] dark:text-emerald-200 text-[10px] leading-none tabular-nums">
                {completedCount}
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("at_risk")}
            className={`py-1 px-1.5 rounded-lg text-center flex items-center justify-center gap-1 cursor-pointer transition-colors duration-150 ${
              activeTab === "at_risk"
                ? "bg-red-600/12 dark:bg-red-500/20 text-[#9E2418] dark:text-red-300 font-semibold shadow-sm"
                : "text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)]"
            }`}
          >
            <span>At risk</span>
            {atRiskCount > 0 && (
              <span className="px-1.5 py-0.5 rounded-full bg-red-700/15 dark:bg-red-500/25 text-[#9E2418] dark:text-red-200 text-[10px] leading-none tabular-nums">
                {atRiskCount}
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("all")}
            className={`py-1 px-1.5 rounded-lg text-center cursor-pointer transition-colors duration-150 ${
              activeTab === "all"
                ? "bg-[var(--studio-surface-elevated)] text-[var(--studio-text-primary)] font-semibold shadow-sm"
                : "text-[var(--studio-text-secondary)] hover:text-[var(--studio-text-primary)]"
            }`}
          >
            All
          </button>
        </div>
      </div>

      {/* Orders List */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-2 min-h-0">
        {filteredOrders.length === 0 ? (
          <div className="h-40 flex flex-col items-center justify-center text-center px-4">
            <CheckCircle
              className="w-6 h-6 text-[var(--studio-text-muted)] mb-2"
              strokeWidth={1.5}
            />
            <p className="font-medium text-[var(--studio-text-secondary)] text-xs">
              No matching orders
            </p>
            <p className="text-[11px] text-[var(--studio-text-muted)] mt-0.5">
              Orders will appear as fulfillment progresses.
            </p>
          </div>
        ) : (
          filteredOrders.map((order) => {
            const isSelected = selectedOrderId === order.id;
            const remainingTicks = order.deadline_tick - tick;
            const remainingSecs = Math.max(0, Math.floor(remainingTicks / 10));
            const mins = Math.floor(remainingSecs / 60);
            const secs = remainingSecs % 60;
            const countdownStr =
              remainingTicks > 0 ? `${mins}m ${String(secs).padStart(2, "0")}s` : "Expired";

            const totalDurationTicks = Math.max(1, order.deadline_tick - order.received_tick);
            const progressFraction = Math.max(
              0,
              Math.min(1, remainingTicks / totalDurationTicks)
            );
            const currentStageIdx = getStageIndex(order.status);
            const da = order.delay_attribution;

            return (
              <div
                key={order.id}
                className={`p-3 rounded-xl border transition-[border-color,background-color,box-shadow] duration-200 ${
                  isSelected
                    ? "bg-[var(--studio-surface-elevated)] border-studio-terracotta ring-1 ring-studio-terracotta/25 shadow-sm"
                    : order.at_risk
                      ? "bg-red-50/75 dark:bg-red-950/25 border-red-700/25 dark:border-red-500/35 hover:border-red-700/45"
                      : "bg-[var(--studio-surface-elevated)] border-[var(--studio-border)] hover:border-[var(--studio-border-strong)]"
                }`}
              >
                {/* Order Top Line */}
                <button
                  type="button"
                  aria-expanded={isSelected}
                  className="w-full text-left flex items-center justify-between gap-2 cursor-pointer rounded-lg"
                  onClick={() => setStore({ selectedOrderId: isSelected ? null : order.id })}
                >
                  <div className="flex items-center gap-1.5 font-mono font-semibold text-[var(--studio-text-primary)] text-xs min-w-0">
                    <span className="truncate tabular-nums">{order.id}</span>
                    {order.tote_id && (
                      <span className="px-1.5 py-0.5 rounded-md bg-stone-900/[0.06] dark:bg-white/[0.08] text-[var(--studio-text-secondary)] border border-[var(--studio-border)] text-[10px] font-mono tabular-nums shrink-0">
                        {order.tote_id}
                      </span>
                    )}
                    {order.at_risk && (
                      <span className="flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-red-600/12 dark:bg-red-500/20 text-[#9E2418] dark:text-red-300 border border-red-700/25 dark:border-red-500/35 text-[10px] font-semibold shrink-0">
                        <AlertCircle className="w-3 h-3" strokeWidth={1.5} />
                        <span>At risk</span>
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span
                      className={`px-2 py-0.5 rounded-md text-[10px] font-medium border flex items-center gap-1 ${getStatusBadgeStyle(
                        order.status
                      )}`}
                    >
                      {order.status === "HANDED_OVER" ? (
                        <>
                          <Truck
                            className="w-3 h-3 text-[#1D6144] dark:text-emerald-300"
                            strokeWidth={1.5}
                          />
                          <span>Delivered</span>
                        </>
                      ) : (
                        formatOrderStatus(order.status)
                      )}
                    </span>
                    {isSelected ? (
                      <ChevronUp
                        className="w-3.5 h-3.5 text-[var(--studio-text-secondary)]"
                        strokeWidth={1.5}
                      />
                    ) : (
                      <ChevronDown
                        className="w-3.5 h-3.5 text-[var(--studio-text-muted)]"
                        strokeWidth={1.5}
                      />
                    )}
                  </div>
                </button>

                {/* SLA Deadline Bar */}
                {order.status !== "HANDED_OVER" && order.status !== "CANCELLED" && (
                  <div className="mt-2.5 mb-1.5">
                    <div className="flex justify-between items-center text-[10.5px] text-[var(--studio-text-secondary)] mb-1">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3 text-[var(--studio-text-muted)]" strokeWidth={1.5} />
                        <span>SLA deadline</span>
                      </span>
                      <span
                        className={`font-mono font-semibold tabular-nums ${
                          order.at_risk || remainingTicks <= 0
                            ? "text-[#9E2418] dark:text-red-300"
                            : "text-[var(--studio-text-primary)]"
                        }`}
                      >
                        {countdownStr}
                      </span>
                    </div>
                    <div className="w-full h-1.5 bg-stone-900/10 dark:bg-white/10 rounded-full overflow-hidden">
                      <div
                        className={`w-full h-full rounded-full origin-left transform transition-transform duration-300 ease-[var(--ease-out)] ${
                          order.at_risk || remainingTicks <= 0
                            ? "bg-[#B93829] dark:bg-red-500"
                            : "bg-[var(--studio-accent-solid)]"
                        }`}
                        style={{ transform: `scaleX(${progressFraction})` }}
                      />
                    </div>
                  </div>
                )}

                {/* Multi-step Journey Progress Pills */}
                <div className="mt-2 grid grid-cols-7 gap-1 text-center">
                  {LIFECYCLE_STAGES.map((st, idx) => {
                    const isDone = currentStageIdx >= idx;
                    const isCurr = currentStageIdx === idx;
                    return (
                      <div
                        key={st}
                        title={formatOrderStatus(st)}
                        className={`h-1.5 rounded-full transition-colors duration-200 ${
                          isCurr
                            ? "bg-[var(--studio-accent-solid)] ring-1 ring-studio-terracotta/35"
                            : isDone
                              ? "bg-[#2E7D5B] dark:bg-emerald-500/80"
                              : "bg-stone-900/10 dark:bg-white/10"
                        }`}
                      />
                    );
                  })}
                </div>

                {/* SKU count & Tier */}
                <div className="flex items-center justify-between text-[10.5px] text-[var(--studio-text-muted)] pt-2 mt-2 border-t border-[var(--studio-border)]">
                  <span className="flex items-center gap-1 tabular-nums min-w-0 truncate">
                    <Layers className="w-3 h-3 text-[var(--studio-text-muted)] shrink-0" strokeWidth={1.5} />
                    <span>{order.lines?.length || 0} items</span>
                    {order.assigned_robot_ids && order.assigned_robot_ids.length > 0 && (
                      <span className="ml-1 text-[var(--studio-text-secondary)] truncate font-mono">
                        · {order.assigned_robot_ids.join(", ")}
                      </span>
                    )}
                  </span>
                  <span
                    className={`font-mono font-medium text-[10.5px] shrink-0 ${
                      order.sla_tier === "express"
                        ? "text-[#A53420] dark:text-studio-coral"
                        : "text-[var(--studio-text-secondary)]"
                    }`}
                  >
                    {order.sla_tier.charAt(0).toUpperCase() + order.sla_tier.slice(1)}
                  </span>
                </div>

                {/* Expandable Journey & Delay Attribution Drawer */}
                {isSelected && (
                  <div className="mt-2.5 pt-2.5 border-t border-[var(--studio-border)] space-y-2.5 text-[11px] text-[var(--studio-text-secondary)]">
                    {/* Line Items Details */}
                    <div>
                      <div className="text-[11px] font-medium text-[var(--studio-text-secondary)] mb-1 flex items-center gap-1.5">
                        <Package className="w-3 h-3 text-[var(--studio-text-muted)]" strokeWidth={1.5} />
                        <span>Order lines</span>
                      </div>
                      <div className="space-y-1 bg-[var(--studio-surface-subtle)] p-2 rounded-lg border border-[var(--studio-border)] font-mono text-[10.5px]">
                        {order.lines.map((l) => (
                          <div key={l.sku_id} className="flex justify-between items-center gap-2">
                            <span className="text-[var(--studio-text-primary)] truncate">{l.sku_id}</span>
                            <span className="text-[var(--studio-text-muted)] tabular-nums shrink-0">
                              Qty:{" "}
                              <strong className="text-[var(--studio-text-primary)] font-semibold">
                                {l.picked_quantity}
                              </strong>{" "}
                              / {l.quantity}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Delay Attribution */}
                    {da && da.total_lateness_ticks > 0 && (
                      <div className="bg-red-600/[0.07] dark:bg-red-950/35 p-2.5 rounded-lg border border-red-700/20 dark:border-red-500/35">
                        <div className="flex items-center justify-between text-[11px] font-semibold text-[#9E2418] dark:text-red-300 mb-1.5">
                          <span className="flex items-center gap-1.5">
                            <AlertCircle className="w-3.5 h-3.5 shrink-0" strokeWidth={1.5} />
                            <span>Delay attribution</span>
                          </span>
                          <span className="font-mono tabular-nums">
                            +{(da.total_lateness_ticks / 10).toFixed(1)}s late
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-1.5 text-[10.5px] font-mono text-[var(--studio-text-secondary)] tabular-nums">
                          <div>
                            Wait for AMR:{" "}
                            <span className="text-[var(--studio-text-primary)] font-medium">
                              {(da.waiting_for_robot_ticks / 10).toFixed(1)}s
                            </span>
                          </div>
                          <div>
                            AMR travel:{" "}
                            <span className="text-[var(--studio-text-primary)] font-medium">
                              {(da.travel_ticks / 10).toFixed(1)}s
                            </span>
                          </div>
                          <div>
                            Station queue:{" "}
                            <span className="text-[var(--studio-text-primary)] font-medium">
                              {(da.station_queue_ticks / 10).toFixed(1)}s
                            </span>
                          </div>
                          <div>
                            Station pick:{" "}
                            <span className="text-[var(--studio-text-primary)] font-medium">
                              {(da.picking_ticks / 10).toFixed(1)}s
                            </span>
                          </div>
                          <div>
                            Consolidation:{" "}
                            <span className="text-[var(--studio-text-primary)] font-medium">
                              {(da.consolidation_ticks / 10).toFixed(1)}s
                            </span>
                          </div>
                          <div>
                            Supervisor bay:{" "}
                            <span className="text-[var(--studio-text-primary)] font-medium">
                              {(da.supervisor_handoff_ticks / 10).toFixed(1)}s
                            </span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
