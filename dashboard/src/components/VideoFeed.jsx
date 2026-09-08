import React, { useState } from "react";
import { Video, Layers, Maximize2, Shield, Eye, AlertTriangle } from "lucide-react";

const CAMERAS = [
  { id: "CAM-01", name: "Sector 4 (North Ridge)", status: "ONLINE", threat: "CRITICAL" },
  { id: "CAM-02", name: "Sector 2 (Foliage Valley)", status: "ONLINE", threat: "LOW" },
  { id: "CAM-03", name: "Sector 7 (Riverine Outpost)", status: "ONLINE", threat: "HIGH" },
  { id: "CAM-04", name: "Sector 5 (Desert Ground Watch)", status: "ONLINE", threat: "CRITICAL" },
];

export default function VideoFeed({ selectedCam, setSelectedCam, latestAlert, onSelectAlert }) {
  const [showTripwire, setShowTripwire] = useState(true);
  const [showBBoxes, setShowBBoxes] = useState(true);
  const [showReticle, setShowReticle] = useState(true);
  const [streamError, setStreamError] = useState(false);

  const activeCamObj = CAMERAS.find((c) => c.id === selectedCam) || CAMERAS[0];

  return (
    <div className="bg-[#0b131d]/90 border border-slate-800 rounded-xl overflow-hidden shadow-2xl flex flex-col">
      {/* 1. Camera Selector Header */}
      <div className="p-3 border-b border-slate-800 flex flex-wrap items-center justify-between gap-2 bg-[#080d14]">
        <div className="flex items-center gap-2">
          <Video className="w-4 h-4 text-cyan-400" />
          <span className="font-mono text-xs font-bold text-white uppercase tracking-wider">
            OPTICAL SURVEILLANCE FEED // {activeCamObj.name}
          </span>
        </div>

        {/* Camera Selector Pills */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {CAMERAS.map((cam) => {
            const isSelected = cam.id === selectedCam;
            return (
              <button
                key={cam.id}
                onClick={() => {
                  setSelectedCam(cam.id);
                  setStreamError(false);
                }}
                className={`px-2.5 py-1 rounded text-xs font-mono transition flex items-center gap-1.5 border ${
                  isSelected
                    ? "bg-cyan-950/80 border-cyan-500 text-cyan-300 shadow-[0_0_10px_rgba(0,240,255,0.2)]"
                    : "bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200"
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    cam.threat === "CRITICAL"
                      ? "bg-red-500 animate-pulse"
                      : cam.threat === "HIGH"
                      ? "bg-amber-400"
                      : "bg-emerald-400"
                  }`}
                />
                <span>{cam.id}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. Main Live Video Stream Box */}
      <div className="relative aspect-video w-full bg-slate-950 flex items-center justify-center overflow-hidden group">
        {!streamError ? (
          <img
            src={`/api/stream?camera_id=${selectedCam}`}
            alt="Live Border Surveillance Stream"
            className="w-full h-full object-cover"
            onError={() => setStreamError(true)}
          />
        ) : (
          <div className="flex flex-col items-center justify-center text-center p-6 space-y-2">
            <AlertTriangle className="w-8 h-8 text-amber-400" />
            <p className="text-xs font-mono text-slate-300">Live stream server initializing...</p>
            <button
              onClick={() => setStreamError(false)}
              className="px-3 py-1 bg-cyan-950 border border-cyan-500/40 text-cyan-300 text-xs font-mono rounded"
            >
              Reconnect Video Feed
            </button>
          </div>
        )}

        {/* Interactive Tactical HUD Overlays */}
        <div className="absolute inset-0 pointer-events-none p-4 flex flex-col justify-between scanline">
          {/* Top telemetry badges */}
          <div className="flex items-center justify-between text-[11px] font-mono">
            <div className="flex items-center gap-2 bg-black/60 backdrop-blur px-2.5 py-1 rounded border border-slate-700/60 text-slate-200">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
              <span>REC // 1080P 30FPS</span>
              <span className="text-slate-400">|</span>
              <span className="text-cyan-400 font-bold">ORB-RANSAC LOCKED</span>
            </div>

            <div className="bg-black/60 backdrop-blur px-2.5 py-1 rounded border border-slate-700/60 text-emerald-400">
              ADAPTIVE BASELINE: STABLE
            </div>
          </div>

          {/* Center Target Reticle */}
          {showReticle && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="w-24 h-24 border border-cyan-500/20 rounded-full flex items-center justify-center">
                <div className="w-2 h-2 bg-cyan-500/40 rounded-full" />
              </div>
            </div>
          )}

          {/* Bottom active threat ticker if a critical intrusion is current */}
          {latestAlert && latestAlert.threat_level === "CRITICAL" && (
            <div className="pointer-events-auto bg-red-950/80 backdrop-blur border border-red-500/60 p-2.5 rounded-lg flex items-center justify-between gap-3 shadow-[0_0_20px_rgba(255,51,75,0.3)] animate-pulse-slow">
              <div className="flex items-center gap-2 text-xs font-mono">
                <Shield className="w-4 h-4 text-red-400" />
                <span className="font-bold text-red-300">ACTIVE INTRUSION DETECTED:</span>
                <span className="text-white">{latestAlert.reason?.slice(0, 85)}...</span>
              </div>
              <button
                onClick={() => onSelectAlert(latestAlert)}
                className="px-2.5 py-1 rounded bg-red-500 hover:bg-red-600 text-white text-[11px] font-mono font-bold transition flex items-center gap-1 shrink-0"
              >
                <Eye className="w-3.5 h-3.5" />
                INSPECT REASON
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 3. Stream Controls & Overlay Toggles */}
      <div className="p-3 border-t border-slate-800 bg-[#080d14] flex flex-wrap items-center justify-between gap-2 text-xs font-mono">
        <div className="flex items-center gap-2 text-slate-400">
          <Layers className="w-3.5 h-3.5 text-cyan-400" />
          <span>TACTICAL OVERLAYS:</span>
          
          <label className="flex items-center gap-1 text-slate-300 cursor-pointer hover:text-white">
            <input
              type="checkbox"
              checked={showTripwire}
              onChange={(e) => setShowTripwire(e.target.checked)}
              className="accent-cyan-400"
            />
            <span>Geofence Tripwire</span>
          </label>

          <label className="flex items-center gap-1 text-slate-300 cursor-pointer hover:text-white">
            <input
              type="checkbox"
              checked={showBBoxes}
              onChange={(e) => setShowBBoxes(e.target.checked)}
              className="accent-cyan-400"
            />
            <span>YOLO Bounding Boxes</span>
          </label>

          <label className="flex items-center gap-1 text-slate-300 cursor-pointer hover:text-white">
            <input
              type="checkbox"
              checked={showReticle}
              onChange={(e) => setShowReticle(e.target.checked)}
              className="accent-cyan-400"
            />
            <span>HUD Crosshairs</span>
          </label>
        </div>

        <div className="text-slate-500 text-[11px]">
          STREAM ENCODING: MJPEG-OVER-HTTP (ZERO LATENCY)
        </div>
      </div>
    </div>
  );
}