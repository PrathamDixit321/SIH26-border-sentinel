import React, { useState } from "react";
import { AlertCircle, ShieldAlert, CheckCircle2, Eye, EyeOff, Search, Clock, Truck, User, Wind } from "lucide-react";

export default function AlertFeed({ alerts, selectedAlert, onSelectAlert, onAcknowledge }) {
  const [filterTab, setFilterTab] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  const filteredAlerts = alerts.filter((alert) => {
    // Tab filtering
    if (filterTab === "CRITICAL" && alert.threat_level !== "CRITICAL") return false;
    if (filterTab === "VEHICLE" && alert.category !== "VEHICLE") return false;
    if (filterTab === "SUPPRESSED" && !alert.environmental_noise_filtered) return false;
    if (filterTab === "THREATS" && alert.environmental_noise_filtered) return false;

    // Search query filtering
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchSector = alert.sector?.toLowerCase().includes(q);
      const matchReason = alert.reason?.toLowerCase().includes(q);
      const matchCategory = alert.category?.toLowerCase().includes(q);
      const matchCam = alert.camera_id?.toLowerCase().includes(q);
      if (!matchSector && !matchReason && !matchCategory && !matchCam) return false;
    }
    return true;
  });

  const formatTimeAgo = (ts) => {
    if (!ts) return "Just now";
    const diffSec = Math.floor((new Date() - new Date(ts)) / 1000);
    if (diffSec < 15) return "Just now";
    if (diffSec < 60) return `${diffSec}s ago`;
    const min = Math.floor(diffSec / 60);
    if (min < 60) return `${min}m ago`;
    const hr = Math.floor(min / 60);
    return `${hr}h ago`;
  };

  return (
    <div className="bg-[#0b131d]/90 border border-slate-800 rounded-xl overflow-hidden shadow-2xl flex flex-col h-full max-h-[750px]">
      
      {/* 1. Header & Filter Tabs */}
      <div className="p-3 border-b border-slate-800 bg-[#080d14] space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-cyan-400" />
            <h2 className="font-mono text-xs font-bold text-white uppercase tracking-wider">
              REAL-TIME INCIDENT TRIAGE FEED
            </h2>
          </div>
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
            {filteredAlerts.length} Events
          </span>
        </div>

        {/* Tab Pills */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 text-xs font-mono">
          <button
            onClick={() => setFilterTab("ALL")}
            className={`px-2.5 py-1 rounded transition whitespace-nowrap ${
              filterTab === "ALL" ? "bg-slate-700 text-white font-bold" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            All
          </button>
          <button
            onClick={() => setFilterTab("CRITICAL")}
            className={`px-2.5 py-1 rounded transition whitespace-nowrap flex items-center gap-1 ${
              filterTab === "CRITICAL" ? "bg-red-950 text-red-300 border border-red-500/40 font-bold" : "text-slate-400 hover:text-red-300"
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
            Critical
          </button>
          <button
            onClick={() => setFilterTab("VEHICLE")}
            className={`px-2.5 py-1 rounded transition whitespace-nowrap flex items-center gap-1 ${
              filterTab === "VEHICLE" ? "bg-amber-950 text-amber-300 border border-amber-500/40 font-bold" : "text-slate-400 hover:text-amber-300"
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            Vehicles
          </button>
          <button
            onClick={() => setFilterTab("SUPPRESSED")}
            className={`px-2.5 py-1 rounded transition whitespace-nowrap flex items-center gap-1 ${
              filterTab === "SUPPRESSED" ? "bg-emerald-950 text-emerald-300 border border-emerald-500/40 font-bold" : "text-slate-400 hover:text-emerald-300"
            }`}
            title="Shows environmental noise (wind, branches, animals) filtered out by the AI"
          >
            <Wind className="w-3 h-3 text-emerald-400" />
            Suppressed Noise (USP)
          </button>
        </div>

        {/* Search input */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search by sector, reason, camera..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-[#05080c] border border-slate-800 rounded px-2.5 py-1.5 pl-8 text-xs font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500/60"
          />
        </div>
      </div>

      {/* 2. Alert Scrollable List */}
      <div className="flex-1 overflow-y-auto divide-y divide-slate-850 p-2 space-y-2">
        {filteredAlerts.length === 0 ? (
          <div className="p-8 text-center text-slate-500 font-mono text-xs">
            No incidents found for current filter.
          </div>
        ) : (
          filteredAlerts.map((alert) => {
            const isSelected = selectedAlert?.alert_id === alert.alert_id;
            const isCritical = alert.threat_level === "CRITICAL";
            const isSuppressed = alert.environmental_noise_filtered;
            const isAcknowledged = alert.status === "ACKNOWLEDGED";

            return (
              <div
                key={alert.alert_id}
                onClick={() => onSelectAlert(alert)}
                className={`p-3 rounded-lg border transition cursor-pointer flex flex-col gap-2 ${
                  isSelected
                    ? "bg-cyan-950/40 border-cyan-500 shadow-[0_0_12px_rgba(0,240,255,0.15)]"
                    : isCritical && !isAcknowledged
                    ? "bg-red-950/30 border-red-500/40 hover:border-red-400"
                    : isSuppressed
                    ? "bg-emerald-950/20 border-emerald-900/40 hover:border-emerald-700/60"
                    : "bg-[#070b10] border-slate-800/80 hover:border-slate-700 hover:bg-[#0a1017]"
                }`}
              >
                {/* Top Row: Threat Badge & Time */}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    {/* Badge */}
                    <span
                      className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${
                        isCritical
                          ? "bg-red-500/20 text-red-400 border-red-500/50"
                          : alert.threat_level === "HIGH"
                          ? "bg-amber-500/20 text-amber-400 border-amber-500/50"
                          : "bg-emerald-500/20 text-emerald-400 border-emerald-500/50"
                      }`}
                    >
                      {alert.threat_level}
                    </span>

                    {/* Category */}
                    <span className="text-xs font-mono font-semibold text-slate-200 flex items-center gap-1">
                      {alert.category === "VEHICLE" ? (
                        <Truck className="w-3.5 h-3.5 text-amber-400" />
                      ) : isSuppressed ? (
                        <Wind className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <User className="w-3.5 h-3.5 text-red-400" />
                      )}
                      <span>{alert.category || alert.classification || "ANOMALY"}</span>
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 text-[11px] font-mono text-slate-400">
                    <Clock className="w-3 h-3" />
                    <span>{formatTimeAgo(alert.timestamp)}</span>
                  </div>
                </div>

                {/* Middle Row: Sector & Explainable AI Reason snippet */}
                <div>
                  <div className="text-[11px] font-mono text-cyan-400 flex items-center justify-between">
                    <span>{alert.sector} ({alert.camera_id})</span>
                    <span className="text-slate-400">{(alert.confidence * 100).toFixed(0)}% Match</span>
                  </div>
                  <p className="text-xs text-slate-300 mt-1 line-clamp-2 leading-relaxed">
                    {alert.reason}
                  </p>
                </div>

                {/* Bottom Row: Actions & Status */}
                <div className="flex items-center justify-between pt-1 border-t border-slate-800/60 text-[11px] font-mono">
                  <span className="text-cyan-400 hover:underline flex items-center gap-1 font-semibold">
                    <Eye className="w-3.5 h-3.5" />
                    Inspect XAI Breakdown &rarr;
                  </span>

                  {isAcknowledged ? (
                    <span className="text-emerald-400 flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Acknowledged
                    </span>
                  ) : (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onAcknowledge(alert.alert_id);
                      }}
                      className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition"
                    >
                      Acknowledge
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

    </div>
  );
}