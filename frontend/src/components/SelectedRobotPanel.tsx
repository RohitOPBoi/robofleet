import React from "react";
import { Battery, Compass, Gauge, MapPin, ShieldAlert, X } from "lucide-react";
import { emergencyStop } from "../services/api";
import { setStore, useStore } from "../store/useStore";

export const SelectedRobotPanel: React.FC = () => {
  const { robots, selectedRobotId } = useStore();

  if (!selectedRobotId) return null;

  const robot = robots[selectedRobotId];
  if (!robot) return null;

  const handleStopSingle = async () => {
    try {
      await emergencyStop("robot", robot.id);
    } catch (e) {
      console.error(e);
    }
  };

  const batteryPct = Math.round(robot.battery_percent ?? 100);

  return (
    <div className="absolute top-4 right-4 w-72 bg-gray-900/95 border border-gray-800 rounded-xl shadow-2xl backdrop-blur-md p-3.5 z-30 text-xs select-none animate-in fade-in slide-in-from-top-2">
      <div className="flex items-center justify-between pb-2 mb-2 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-blue-500" />
          <span className="font-mono font-bold text-white text-sm">{robot.id}</span>
        </div>
        <button
          type="button"
          onClick={() => setStore({ selectedRobotId: null })}
          className="p-1 rounded text-gray-400 hover:text-white hover:bg-gray-800 transition cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="space-y-2.5 text-gray-300">
        {/* State Badge */}
        <div className="flex items-center justify-between">
          <span className="text-gray-400">Status:</span>
          <span
            className={`px-2 py-0.5 rounded font-mono font-semibold text-[11px] ${
              robot.state === "CHARGING"
                ? "bg-amber-950 text-amber-400 border border-amber-800"
                : robot.state === "FAULTED" || robot.state === "EMERGENCY_STOPPED"
                ? "bg-red-950 text-red-400 border border-red-800"
                : "bg-emerald-950 text-emerald-400 border border-emerald-800"
            }`}
          >
            {robot.state}
          </span>
        </div>

        {/* Battery Telemetry */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="flex items-center gap-1 text-gray-400">
              <Battery className="w-3.5 h-3.5 text-emerald-400" /> Battery:
            </span>
            <span className="font-mono font-semibold text-white">{batteryPct}%</span>
          </div>
          <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden">
            <div
              className={`h-full ${
                batteryPct > 50 ? "bg-emerald-500" : batteryPct > 20 ? "bg-amber-500" : "bg-red-500"
              }`}
              style={{ width: `${batteryPct}%` }}
            />
          </div>
        </div>

        {/* Spatial Coordinates & Heading */}
        <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
          <div className="p-2 rounded bg-gray-950 border border-gray-800">
            <div className="flex items-center gap-1 text-gray-400 text-[10px] mb-0.5">
              <MapPin className="w-3 h-3 text-blue-400" /> Position
            </div>
            <div className="font-semibold text-gray-200">
              ({robot.coord?.x ?? 0}, {robot.coord?.y ?? 0})
            </div>
          </div>
          <div className="p-2 rounded bg-gray-950 border border-gray-800">
            <div className="flex items-center gap-1 text-gray-400 text-[10px] mb-0.5">
              <Compass className="w-3 h-3 text-purple-400" /> Heading
            </div>
            <div className="font-semibold text-gray-200">{Math.round(robot.heading_deg ?? 0)}°</div>
          </div>
        </div>

        {/* Speed & Odometer */}
        <div className="p-2 rounded bg-gray-950 border border-gray-800 flex items-center justify-between font-mono text-[11px]">
          <div className="flex items-center gap-1 text-gray-400">
            <Gauge className="w-3 h-3 text-amber-400" /> Speed:
          </div>
          <div className="font-semibold text-gray-200">
            {robot.telemetry?.current_speed_m_s ? robot.telemetry.current_speed_m_s.toFixed(2) : "0.00"} m/s
          </div>
        </div>

        {/* Actions */}
        <div className="pt-2 border-t border-gray-800 flex gap-2">
          <button
            type="button"
            onClick={handleStopSingle}
            className="flex-1 py-1.5 rounded-lg bg-red-950/60 border border-red-800 text-red-400 hover:bg-red-900/60 transition flex items-center justify-center gap-1.5 font-medium cursor-pointer"
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Halt AMR</span>
          </button>
        </div>
      </div>
    </div>
  );
};
