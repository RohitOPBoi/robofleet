import React, { useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle,
  Clock,
  Package,
  Search,
  Truck,
  ChevronDown,
  ChevronUp,
  Cpu,
  Layers,
} from "lucide-react";
import { setStore, useStore } from "../store/useStore";
import type { OrderStatus } from "../types/generated";

const getStatusBadgeStyle = (status: OrderStatus) => {
  switch (status) {
    case "RECEIVED":
    case "QUEUED":
      return "bg-gray-800 text-gray-300 border-gray-700";
    case "PLANNED":
      return "bg-blue-950/80 text-blue-300 border-blue-800";
    case "RETRIEVING":
      return "bg-cyan-950/80 text-cyan-300 border-cyan-800 animate-pulse";
    case "AT_STATION":
    case "PICKING":
      return "bg-amber-950/80 text-amber-300 border-amber-800";
    case "CONSOLIDATING":
      return "bg-indigo-950/80 text-indigo-300 border-indigo-800";
    case "PACKED":
    case "READY_FOR_DISPATCH":
      return "bg-amber-950/80 text-amber-300 border-amber-800 animate-pulse";
    case "HANDED_OVER":
      return "bg-emerald-950/90 text-emerald-300 border-emerald-600 font-bold";
    case "FAILED_PARTIAL":
    case "FAILED":
      return "bg-red-950/80 text-red-300 border-red-800";
    case "CANCELLED":
      return "bg-zinc-900 text-zinc-500 border-zinc-800";
    default:
      return "bg-gray-800 text-gray-400 border-gray-700";
  }
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
    <div className="w-full h-full flex flex-col text-xs select-none overflow-hidden bg-gray-950/90">
      {/* Board Header */}
      <div className="p-3 border-b border-gray-800 bg-gray-950/60 shrink-0">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5 font-semibold text-white text-xs">
            <Package className="w-3.5 h-3.5 text-blue-400" />
            <span>Fulfillment Order Journey</span>
          </div>
          <span className="font-mono text-gray-400 text-[11px]">{filteredOrders.length} orders</span>
        </div>

        {/* Search */}
        <div className="relative mb-2">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2 text-gray-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search ID, tote, or tier..."
            className="w-full bg-gray-900 border border-gray-800 rounded-md pl-8 pr-3 py-1.5 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500 transition"
          />
        </div>

        {/* Filter Tabs */}
        <div className="flex bg-gray-900 p-0.5 rounded-lg border border-gray-800 font-medium text-[11px]">
          <button
            type="button"
            onClick={() => setActiveTab("active")}
            className={`flex-1 py-1 rounded text-center transition flex items-center justify-center gap-1 cursor-pointer ${
              activeTab === "active"
                ? "bg-gray-800 text-white font-semibold shadow-sm"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            <span>Active</span>
            <span className="px-1.5 py-0.2 rounded-full bg-gray-700 text-gray-300 text-[10px]">
              {activeCount}
            </span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("completed")}
            className={`flex-1 py-1 rounded text-center transition flex items-center justify-center gap-1 cursor-pointer ${
              activeTab === "completed"
                ? "bg-green-950 text-green-300 font-semibold shadow-sm"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            <span>Done</span>
            {completedCount > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-green-800/80 text-white text-[10px]">
                {completedCount}
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("at_risk")}
            className={`flex-1 py-1 rounded text-center transition flex items-center justify-center gap-1 cursor-pointer ${
              activeTab === "at_risk"
                ? "bg-red-950 text-red-300 font-semibold shadow-sm"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            <span>At risk</span>
            {atRiskCount > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-red-800 text-white text-[10px]">
                {atRiskCount}
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("all")}
            className={`flex-1 py-1 rounded text-center transition cursor-pointer ${
              activeTab === "all"
                ? "bg-gray-800 text-white font-semibold shadow-sm"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            All
          </button>
        </div>
      </div>

      {/* Orders List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2 min-h-0">
        {filteredOrders.length === 0 ? (
          <div className="h-40 flex flex-col items-center justify-center text-gray-500 text-center px-4">
            <CheckCircle className="w-6 h-6 text-gray-600 mb-1" />
            <p className="font-medium text-gray-400 text-xs">No matching orders</p>
            <p className="text-[10px] text-gray-500">Orders will appear as fulfillment progresses.</p>
          </div>
        ) : (
          filteredOrders.map((order) => {
            const isSelected = selectedOrderId === order.id;
            const remainingTicks = order.deadline_tick - tick;
            const remainingSecs = Math.max(0, Math.floor(remainingTicks / 10));
            const mins = Math.floor(remainingSecs / 60);
            const secs = remainingSecs % 60;
            const countdownStr = remainingTicks > 0 ? `${mins}m ${String(secs).padStart(2, "0")}s` : "EXPIRED";

            const totalDurationTicks = Math.max(1, order.deadline_tick - order.received_tick);
            const progressFraction = Math.max(0, Math.min(1, remainingTicks / totalDurationTicks));
            const currentStageIdx = getStageIndex(order.status);
            const da = order.delay_attribution;

            return (
              <div
                key={order.id}
                className={`p-2.5 rounded-lg border transition select-none ${
                  isSelected
                    ? "bg-blue-950/40 border-blue-600 shadow-md ring-1 ring-blue-500/30"
                    : order.at_risk
                    ? "bg-red-950/20 border-red-800/70 hover:border-red-600"
                    : "bg-gray-950/60 border-gray-800 hover:border-gray-700"
                }`}
              >
                {/* Order Top Line */}
                <div
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() => setStore({ selectedOrderId: isSelected ? null : order.id })}
                >
                  <div className="flex items-center gap-1.5 font-mono font-semibold text-gray-200 text-xs">
                    <span>{order.id}</span>
                    {order.tote_id && (
                      <span className="px-1 py-0.2 rounded bg-indigo-950/80 text-indigo-300 border border-indigo-800 text-[10px] font-mono">
                        {order.tote_id}
                      </span>
                    )}
                    {order.at_risk && (
                      <span className="flex items-center gap-0.5 px-1 py-0.2 rounded bg-red-950 text-red-400 border border-red-800 text-[10px] font-bold">
                        <AlertCircle className="w-2.5 h-2.5" />
                        AT RISK
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider border flex items-center gap-1 ${getStatusBadgeStyle(
                        order.status
                      )}`}
                    >
                      {order.status === "HANDED_OVER" ? (
                        <>
                          <Truck className="w-3 h-3 text-emerald-400" />
                          <span>DONE / DELIVERED</span>
                        </>
                      ) : (
                        order.status.replace("_", " ")
                      )}
                    </span>
                    {isSelected ? (
                      <ChevronUp className="w-3.5 h-3.5 text-gray-400" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
                    )}
                  </div>
                </div>

                {/* SLA Deadline Bar */}
                {order.status !== "HANDED_OVER" && order.status !== "CANCELLED" && (
                  <div className="mt-2 mb-1">
                    <div className="flex justify-between items-center text-[10px] text-gray-400 mb-0.5">
                      <span className="flex items-center gap-1">
                        <Clock className="w-2.5 h-2.5" /> SLA deadline:
                      </span>
                      <span
                        className={`font-mono font-semibold ${
                          order.at_risk || remainingTicks <= 0 ? "text-red-400" : "text-gray-300"
                        }`}
                      >
                        {countdownStr}
                      </span>
                    </div>
                    <div className="w-full h-1 bg-gray-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full transition-all duration-300 ${
                          order.at_risk || remainingTicks <= 0 ? "bg-red-500" : "bg-blue-500"
                        }`}
                        style={{ width: `${progressFraction * 100}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Multi-step Journey Progress Pills */}
                <div className="mt-2 grid grid-cols-7 gap-0.5 text-center">
                  {LIFECYCLE_STAGES.map((st, idx) => {
                    const isDone = currentStageIdx >= idx;
                    const isCurr = currentStageIdx === idx;
                    return (
                      <div
                        key={st}
                        title={st}
                        className={`h-1.5 rounded-sm transition-all ${
                          isCurr
                            ? "bg-amber-400 ring-1 ring-amber-300"
                            : isDone
                            ? "bg-blue-500"
                            : "bg-gray-800"
                        }`}
                      />
                    );
                  })}
                </div>

                {/* SKU count & Tier */}
                <div className="flex items-center justify-between text-[10px] text-gray-500 pt-1.5 mt-1 border-t border-gray-900">
                  <span className="flex items-center gap-1">
                    <Layers className="w-2.5 h-2.5 text-gray-400" />
                    {order.lines?.length || 0} items
                    {order.assigned_robot_ids && order.assigned_robot_ids.length > 0 && (
                      <span className="ml-1 text-gray-400">
                        • {order.assigned_robot_ids.join(", ")}
                      </span>
                    )}
                  </span>
                  <span
                    className={`font-mono font-semibold uppercase text-[10px] ${
                      order.sla_tier === "express" ? "text-purple-400" : "text-gray-400"
                    }`}
                  >
                    {order.sla_tier}
                  </span>
                </div>

                {/* Expandable Journey & Delay Attribution Drawer */}
                {isSelected && (
                  <div className="mt-2 pt-2 border-t border-gray-800/80 space-y-2 text-[11px] text-gray-300">
                    {/* Line Items Details */}
                    <div>
                      <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1 flex items-center gap-1">
                        <Package className="w-2.5 h-2.5" /> Order Lines:
                      </div>
                      <div className="space-y-1 bg-gray-900/80 p-2 rounded border border-gray-800 font-mono text-[10px]">
                        {order.lines.map((l, i) => (
                          <div key={i} className="flex justify-between items-center">
                            <span className="text-gray-300">{l.sku_id}</span>
                            <span className="text-gray-400">
                              Qty: <strong className="text-white">{l.picked_quantity}</strong> / {l.quantity}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* WareMax Delay Attribution (P3-A8) */}
                    {da && da.total_lateness_ticks > 0 && (
                      <div className="bg-red-950/30 p-2 rounded border border-red-900/60">
                        <div className="flex items-center justify-between text-[10px] font-bold text-red-300 mb-1">
                          <span className="flex items-center gap-1">
                            <AlertCircle className="w-3 h-3 text-red-400" />
                            Delay Attribution
                          </span>
                          <span>+{(da.total_lateness_ticks / 10).toFixed(1)}s late</span>
                        </div>
                        <div className="grid grid-cols-2 gap-1 text-[10px] font-mono text-gray-400">
                          <div>Wait for AMR: <span className="text-gray-200">{(da.waiting_for_robot_ticks / 10).toFixed(1)}s</span></div>
                          <div>AMR Travel: <span className="text-gray-200">{(da.travel_ticks / 10).toFixed(1)}s</span></div>
                          <div>Station Queue: <span className="text-gray-200">{(da.station_queue_ticks / 10).toFixed(1)}s</span></div>
                          <div>Station Pick: <span className="text-gray-200">{(da.picking_ticks / 10).toFixed(1)}s</span></div>
                          <div>Consolidation: <span className="text-gray-200">{(da.consolidation_ticks / 10).toFixed(1)}s</span></div>
                          <div>Supervisor Bay: <span className="text-gray-200">{(da.supervisor_handoff_ticks / 10).toFixed(1)}s</span></div>
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
