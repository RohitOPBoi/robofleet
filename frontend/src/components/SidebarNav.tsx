import React from "react";
import {
  AlertOctagon,
  AlertTriangle,
  BarChart3,
  Bell,
  Box,
  Brain,
  Columns2,
  History,
  Info,
  Map as MapIcon,
  Package,
  Play,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  UserCheck,
  ZapOff,
  type LucideIcon,
} from "lucide-react";
import { setStore, useStore } from "../store/useStore";

interface RailButtonProps {
  icon: LucideIcon;
  label: string;
  shortcut?: string;
  active?: boolean;
  badge?: number;
  badgeTone?: "neutral" | "amber" | "crimson";
  onClick: () => void;
}

const RailButton: React.FC<RailButtonProps> = ({
  icon: Icon,
  label,
  shortcut,
  active = false,
  badge,
  badgeTone = "neutral",
  onClick,
}) => {
  const badgeColor =
    badgeTone === "crimson"
      ? "bg-studio-crimson text-white"
      : badgeTone === "amber"
        ? "bg-amber-400 text-studio-ink"
        : active
          ? "bg-studio-terracotta text-white"
          : "bg-white/25 text-white";

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-pressed={active}
      className={`group relative w-9 h-9 rounded-xl flex items-center justify-center studio-btn cursor-pointer ${
        active
          ? "bg-white text-studio-ink shadow-sm"
          : "text-white/80 hover:text-white hover:bg-white/14"
      }`}
    >
      <Icon
        className={`w-[18px] h-[18px] shrink-0 ${
          active ? "text-studio-terracotta" : ""
        }`}
        strokeWidth={1.5}
      />

      {badge !== undefined && badge > 0 && (
        <span
          className={`absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full text-[9.5px] font-mono font-semibold flex items-center justify-center leading-none tabular-nums shadow-sm ${badgeColor}`}
        >
          {badge > 99 ? "99+" : badge}
        </span>
      )}

      {/* Origin-aware non-linear frosted tooltip */}
      <span className="studio-rail-tip hidden sm:flex items-center gap-2 absolute left-full ml-3 px-2.5 py-1.5 rounded-xl bg-studio-espresso/95 text-[#FFFBF8] border border-white/15 shadow-lg text-[11.5px] font-medium whitespace-nowrap z-50 backdrop-blur-xl">
        <span>{label}</span>
        {shortcut && (
          <kbd className="px-1.5 py-0.5 rounded bg-white/15 text-[10px] font-mono text-white/80">
            {shortcut}
          </kbd>
        )}
      </span>
    </button>
  );
};

export const SidebarNav: React.FC = () => {
  const {
    connected,
    activeWorkspaceView,
    decisions,
    alerts,
    leftPanelOpen,
    rightPanelOpen,
    pendingApprovals,
    activeFaults,
    activeFaultsCount,
    pendingExceptions,
    isDecisionLogOpen,
    isAISettingsOpen,
    isApprovalsDrawerOpen,
    isChaosControlOpen,
    isExceptionsQueueOpen,
    isAuditLogOpen,
    isSupervisorBarOpen,
    environmentDisclosure,
    staticWorld,
    robots,
  } = useStore();

  const activeAlertCount = alerts.filter((a) => !a.cleared).length;
  const faultCount = Math.max(activeFaults.length, activeFaultsCount);
  const hasEmergencyStopped = Object.values(robots).some(
    (r) => r.state === "EMERGENCY_STOPPED"
  );

  const scenarioName =
    environmentDisclosure?.scenario ||
    staticWorld?.meta?.scenario_name ||
    "standard";

  return (
    <aside className="w-14 shrink-0 h-full studio-sidebar-glass flex flex-col items-center py-3 px-2 text-white select-none z-40 relative">
      {/* Brand Emblem + Live Telemetry Status */}
      <div className="relative mb-3">
        <button
          type="button"
          onClick={() =>
            setStore({
              activeWorkspaceView: "split",
              viewMode: "split",
              leftPanelOpen: true,
              rightPanelOpen: true,
            })
          }
          title="RoboFleet Command Studio — Reset to Unified Split Workspace"
          className="w-9 h-9 rounded-xl bg-gradient-to-br from-studio-coral to-studio-vermilion text-white font-bold text-xs flex items-center justify-center shadow-sm studio-btn cursor-pointer"
        >
          RF
        </button>
        <span
          className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-[#2A1B15] ${
            connected ? "bg-emerald-400" : "bg-red-400"
          }`}
          title={connected ? "WebSocket stream connected" : "WebSocket offline"}
        />
      </div>

      {/* Quick Supervisor Command Search */}
      <RailButton
        icon={Search}
        label="Supervisor command bar"
        shortcut="⌘K"
        active={isSupervisorBarOpen}
        onClick={() => setStore({ isSupervisorBarOpen: !isSupervisorBarOpen })}
      />

      <div className="w-7 h-px bg-white/15 my-2.5 shrink-0" />

      {/* Workspace Views */}
      <nav className="flex-1 flex flex-col items-center gap-1 overflow-visible py-0.5 w-full">
        <RailButton
          icon={Columns2}
          label="Split 2D & 3D studio"
          shortcut="V"
          active={activeWorkspaceView === "split"}
          onClick={() => setStore({ activeWorkspaceView: "split", viewMode: "split" })}
        />
        <RailButton
          icon={MapIcon}
          label="2D tactical map"
          active={activeWorkspaceView === "2d"}
          onClick={() => setStore({ activeWorkspaceView: "2d", viewMode: "2d" })}
        />
        <RailButton
          icon={Box}
          label="3D warehouse twin"
          active={activeWorkspaceView === "3d"}
          onClick={() => setStore({ activeWorkspaceView: "3d", viewMode: "3d" })}
        />
        <RailButton
          icon={BarChart3}
          label="Analytics overview"
          active={activeWorkspaceView === "overview"}
          onClick={() => setStore({ activeWorkspaceView: "overview" })}
        />

        <div className="w-7 h-px bg-white/15 my-1 shrink-0" />

        {/* Direct Panel & Drawer Triggers */}
        <RailButton
          icon={Package}
          label={leftPanelOpen ? "Hide orders board" : "Show orders board"}
          shortcut="["
          active={leftPanelOpen && activeWorkspaceView !== "overview"}
          onClick={() => setStore({ leftPanelOpen: !leftPanelOpen })}
        />
        <RailButton
          icon={Bell}
          label={rightPanelOpen ? "Hide alerts & events" : "Show alerts & events"}
          shortcut="]"
          active={rightPanelOpen}
          badge={activeAlertCount}
          badgeTone="amber"
          onClick={() => setStore({ rightPanelOpen: !rightPanelOpen })}
        />

        <div className="w-7 h-px bg-white/15 my-1 shrink-0" />

        {/* Intelligence & Resilience Modules */}
        <RailButton
          icon={Brain}
          label="AI decisions log"
          active={isDecisionLogOpen}
          badge={decisions.length}
          onClick={() => setStore({ isDecisionLogOpen: true })}
        />
        <RailButton
          icon={SlidersHorizontal}
          label="AI & local model settings"
          active={isAISettingsOpen}
          onClick={() => setStore({ isAISettingsOpen: true })}
        />
        <RailButton
          icon={UserCheck}
          label="Governance approvals"
          active={isApprovalsDrawerOpen}
          badge={pendingApprovals.length}
          badgeTone="amber"
          onClick={() => setStore({ isApprovalsDrawerOpen: true })}
        />
        <RailButton
          icon={ZapOff}
          label="Chaos & fault injection"
          active={isChaosControlOpen}
          badge={faultCount}
          badgeTone="crimson"
          onClick={() => setStore({ isChaosControlOpen: true })}
        />
        <RailButton
          icon={AlertOctagon}
          label="Supervisor exceptions"
          active={isExceptionsQueueOpen}
          badge={pendingExceptions.length}
          badgeTone="amber"
          onClick={() => setStore({ isExceptionsQueueOpen: true })}
        />
        <RailButton
          icon={ShieldCheck}
          label="Immutable audit ledger"
          active={isAuditLogOpen}
          onClick={() => setStore({ isAuditLogOpen: true })}
        />
        <RailButton
          icon={History}
          label="Run replay timeline"
          active={activeWorkspaceView === "replay"}
          onClick={() => setStore({ activeWorkspaceView: "replay", leftPanelOpen: false })}
        />
      </nav>

      {/* Bottom Environment & E-Stop */}
      <div className="pt-2.5 mt-2 border-t border-white/15 flex flex-col items-center gap-1.5 shrink-0">
        <RailButton
          icon={Info}
          label={`Environment (${scenarioName})`}
          onClick={() => setStore({ isEnvironmentModalOpen: true })}
        />
        <button
          type="button"
          onClick={() => setStore({ isEStopModalOpen: true })}
          aria-label={hasEmergencyStopped ? "Resume fleet" : "Emergency stop"}
          className={`group relative w-10 h-10 rounded-xl flex items-center justify-center studio-btn cursor-pointer border ${
            hasEmergencyStopped
              ? "bg-emerald-600/90 hover:bg-emerald-600 border-emerald-400/40 text-white"
              : "bg-studio-crimson/90 hover:bg-studio-crimson border-white/20 text-white"
          }`}
        >
          {hasEmergencyStopped ? (
            <Play className="w-4 h-4 fill-current" strokeWidth={1.5} />
          ) : (
            <AlertTriangle className="w-4 h-4" strokeWidth={1.5} />
          )}
          <span className="studio-rail-tip hidden sm:flex items-center gap-2 absolute left-full ml-3 px-2.5 py-1.5 rounded-xl bg-studio-espresso/95 text-[#FFFBF8] border border-white/15 shadow-lg text-[11.5px] font-medium whitespace-nowrap z-50 backdrop-blur-xl">
            {hasEmergencyStopped ? "Resume fleet" : "Emergency stop"}
          </span>
        </button>
      </div>
    </aside>
  );
};
