import React from "react";
import { AlertTriangle, ShieldAlert, X } from "lucide-react";
import { blockCells, emergencyStop, resumeEmergency } from "../services/api";
import { setStore, useStore } from "../store/useStore";

export const ControlModals: React.FC = () => {
  const { isEStopModalOpen, selectedCellsToBlock, blockModeActive } = useStore();

  if (!isEStopModalOpen) return null;

  const handleEStopAll = async () => {
    try {
      await emergencyStop("all");
      setStore({ isEStopModalOpen: false });
    } catch (e) {
      console.error(e);
    }
  };

  const handleResumeAll = async () => {
    try {
      await resumeEmergency("all");
      setStore({ isEStopModalOpen: false });
    } catch (e) {
      console.error(e);
    }
  };

  const handleConfirmBlock = async () => {
    try {
      await blockCells(selectedCellsToBlock);
      setStore({
        isEStopModalOpen: false,
        blockModeActive: false,
        selectedCellsToBlock: [],
      });
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in select-none">
      <div className="bg-gray-900 border border-red-900/80 rounded-xl max-w-md w-full shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="px-5 py-3.5 border-b border-gray-800 flex items-center justify-between bg-red-950/30">
          <div className="flex items-center gap-2 text-red-400 font-semibold text-sm">
            <ShieldAlert className="w-5 h-5 text-red-500" />
            <span>Emergency Operations Control</span>
          </div>
          <button
            type="button"
            aria-label="Close modal"
            onClick={() => setStore({ isEStopModalOpen: false })}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 space-y-4 text-xs text-gray-300">
          {blockModeActive && selectedCellsToBlock.length > 0 ? (
            <div>
              <p className="text-gray-200 text-sm font-medium mb-1">
                Confirm blocking {selectedCellsToBlock.length} warehouse grid cell(s)?
              </p>
              <p className="text-gray-400 leading-relaxed mb-3">
                All pathfinding algorithms will dynamically re-route AMRs around these coordinates. If an AMR is
                currently occupying a blocked cell, it will yield and request replanning.
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleConfirmBlock}
                  className="flex-1 py-2 bg-red-600 hover:bg-red-500 text-white font-semibold rounded-lg transition shadow-md cursor-pointer"
                >
                  Apply Cell Block
                </button>
                <button
                  type="button"
                  onClick={() => setStore({ isEStopModalOpen: false, blockModeActive: false, selectedCellsToBlock: [] })}
                  className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium rounded-lg transition cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div>
              <div className="p-3 rounded-lg bg-red-950/30 border border-red-800/40 flex items-start gap-2.5 mb-4">
                <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                <span className="text-red-300 leading-relaxed">
                  Executing Emergency Stop immediately halts motion on the selected scope. Path reservations will be held
                  until a supervisory resume command is authenticated.
                </span>
              </div>

              <div className="space-y-2">
                <button
                  type="button"
                  onClick={handleEStopAll}
                  className="w-full py-2.5 bg-red-600 hover:bg-red-500 text-white font-semibold rounded-lg transition shadow-md flex items-center justify-center gap-2 cursor-pointer active:scale-95"
                >
                  <ShieldAlert className="w-4 h-4" />
                  <span>EMERGENCY STOP (ALL AMRs)</span>
                </button>

                <button
                  type="button"
                  onClick={handleResumeAll}
                  className="w-full py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 font-medium rounded-lg transition flex items-center justify-center gap-2 cursor-pointer active:scale-95"
                >
                  <span>Resume Fleet Operations</span>
                </button>

                <button
                  type="button"
                  onClick={() => setStore({ isEStopModalOpen: false })}
                  className="w-full py-1.5 text-gray-400 hover:text-gray-200 transition text-center cursor-pointer"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-2.5 border-t border-gray-800 bg-gray-950/60 flex justify-end">
          <button
            onClick={() => setStore({ isEStopModalOpen: false })}
            className="px-3 py-1 bg-gray-800 hover:bg-gray-700 text-white rounded text-xs transition"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};
