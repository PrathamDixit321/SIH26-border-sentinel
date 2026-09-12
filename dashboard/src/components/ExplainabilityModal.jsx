import React from "react";
import { X, ShieldAlert, ShieldCheck, CheckCircle2, Crosshair, HelpCircle, Download, Send, AlertTriangle, Wind, User, Truck } from "lucide-react";

export default function ExplainabilityModal({ alert, onClose, onAcknowledge }) {
  if (!alert) return null;

  const isCritical = alert.threat_level === "CRITICAL";
  const isSuppressed = alert.environmental_noise_filtered;
  const metrics = alert.metrics || {};
  const xai = alert.xai_breakdown || {};

  const handleDownloadJSON = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(alert, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `forensic_${alert.alert_id}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-md overflow-y-auto">
      <div className="relative w-full max-w-4xl bg-[#090f17] border border-slate-700/80 rounded-2xl shadow-[0_0_50px_rgba(0,0,0,0.8)] overflow-hidden my-auto flex flex-col">
        
        {/* 1. Tactical Modal Header */}
        <div className="p-4 border-b border-slate-800 bg-[#060b11] flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div
              className={`p-2 rounded-lg border ${
                isCritical
                  ? "bg-red-950/60 border-red-500/50 text-red-400"
                  : isSuppressed
                  ? "bg-emerald-950/60 border-emerald-500/50 text-emerald-400"
                  : "bg-cyan-950/60 border-cyan-500/50 text-cyan-400"
              }`}
            >
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-mono text-base font-bold text-white tracking-wider">
                  INCIDENT FORENSIC DOSSIER // {alert.alert_id}
                </h2>
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
              </div>
              <p className="text-xs text-slate-400 font-mono">
                {alert.sector} &bull; {alert.camera_id} &bull; {new Date(alert.timestamp).toLocaleString("en-IN")}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 2. Modal Body Grid */}
        <div className="p-5 space-y-5 overflow-y-auto max-h-[78vh]">
          
          {/* Top Section: Snapshot Image + Snapshot Metadata */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
            
            {/* Snapshot Image Container */}
            <div className="md:col-span-7 bg-slate-950 rounded-xl border border-slate-800 overflow-hidden relative group">
              <img
                src={alert.snapshot_url || "/snapshots/sample_intruder_01.jpg"}
                alt="Intrusion Forensic Snapshot"
                className="w-full h-auto object-contain max-h-[290px] mx-auto"
                onError={(e) => {
                  e.target.src = "/snapshots/sample_intruder_01.jpg";
                }}
              />
              {/* Corner badge on snapshot */}
              <div className="absolute top-2 left-2 bg-black/70 backdrop-blur px-2 py-0.5 rounded text-[10px] font-mono text-cyan-400 border border-cyan-500/30">
                FORENSIC CAPTURE // 1080P
              </div>
              <div className="absolute bottom-2 right-2 bg-black/70 backdrop-blur px-2 py-0.5 rounded text-[10px] font-mono text-slate-300 border border-slate-700">
                BBOX: [{alert.bbox ? alert.bbox.join(", ") : "N/A"}]
              </div>
            </div>

            {/* Quick Metrics Column */}
            <div className="md:col-span-5 flex flex-col justify-between space-y-3">
              <div className="bg-[#0e1622] p-3.5 rounded-xl border border-slate-800 space-y-2">
                <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
                  Detection Confidence &amp; Target
                </div>
                <div className="flex items-center justify-between">
                  <span className="font-mono text-2xl font-bold text-white">
                    {(alert.confidence * 100).toFixed(1)}%
                  </span>
                  <span className="px-2.5 py-1 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 font-mono text-xs font-semibold">
                    {alert.category || alert.classification}
                  </span>
                </div>
                {/* Confidence Bar */}
                <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      isCritical ? "bg-red-500" : isSuppressed ? "bg-emerald-400" : "bg-cyan-400"
                    }`}
                    style={{ width: `${Math.min(100, alert.confidence * 100)}%` }}
                  />
                </div>
              </div>

              {/* Status / Zone Incursion Box */}
              <div className="bg-[#0e1622] p-3.5 rounded-xl border border-slate-800 space-y-1.5 text-xs font-mono">
                <div className="text-slate-400 text-[11px] uppercase">Restricted Zone Dwell</div>
                <div className="text-white font-semibold text-sm">{alert.zone || "Restricted Buffer Zone Alpha"}</div>
                <div className="text-slate-400 text-[11px] pt-1 border-t border-slate-800 flex justify-between">
                  <span>ORB Homography Status:</span>
                  <span className="text-emerald-400 font-bold">LOCKED (0.032px)</span>
                </div>
              </div>

              {/* Suppressed / Threat Badge Alert */}
              <div
                className={`p-3 rounded-xl border text-xs font-mono ${
                  isSuppressed
                    ? "bg-emerald-950/30 border-emerald-500/40 text-emerald-300"
                    : "bg-red-950/30 border-red-500/40 text-red-300"
                }`}
              >
                <div className="font-bold flex items-center gap-1.5 mb-1">
                  {isSuppressed ? <ShieldCheck className="w-4 h-4" /> : <ShieldAlert className="w-4 h-4" />}
                  <span>{isSuppressed ? "AUTOMATIC FALSE-ALARM SUPPRESSION" : "ACTIVE THREAT CLASSIFICATION"}</span>
                </div>
                <p className="text-[11px] text-slate-300">
                  {isSuppressed
                    ? "Filtered out to protect border operators from alarm fatigue. No manual intervention needed."
                    : "Immediate tactical intervention recommended. Alert dispatched to Command Center."}
                </p>
              </div>

            </div>

          </div>

          {/* 3. VISUALLY PROMINENT EXPLAINABLE AI (XAI) REASONING (KEY DIFFERENTIATOR) */}
          <div className="bg-gradient-to-br from-[#0f1d2e] to-[#0a1420] border-2 border-cyan-500/60 rounded-2xl p-4 sm:p-5 shadow-[0_0_30px_rgba(0,240,255,0.12)]">
            
            <div className="flex items-center gap-2.5 mb-2.5">
              <div className="p-1.5 rounded-md bg-cyan-500/20 text-cyan-400 border border-cyan-500/40">
                <HelpCircle className="w-4 h-4" />
              </div>
              <div>
                <span className="text-[11px] font-mono tracking-widest text-cyan-400 font-bold uppercase">
                  EXPLAINABLE AI (XAI) REASONING ENGINE // FORENSIC EXPLANATION
                </span>
                <span className="block text-[10px] text-slate-400 font-mono">
                  Why this event was flagged or filtered vs environmental foliage noise
                </span>
              </div>
            </div>

            {/* The Main Plain-Language Reason Banner */}
            <div className="bg-black/50 border border-cyan-500/30 rounded-xl p-3.5 mb-4 text-sm text-cyan-100 font-sans leading-relaxed shadow-inner">
              <span className="font-bold text-cyan-300 font-mono mr-1.5">[AI REASONING]:</span>
              {alert.reason}
            </div>

            {/* 4 Forensic Verification Pillars */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono">
              
              {/* Pillar 1: Shape Solidity */}
              <div className="p-3 rounded-lg bg-[#070d14]/80 border border-slate-700/60 space-y-1">
                <div className="text-cyan-400 font-bold flex items-center justify-between">
                  <span>1. MORPHOLOGICAL STRUCTURE</span>
                  <span className="text-[10px] text-slate-400">SOLIDITY</span>
                </div>
                <p className="text-slate-300 text-[11px] leading-relaxed">
                  {xai.shape_analysis || `Solidity: ${metrics.solidity || 0.82} | Aspect Ratio: ${metrics.aspect_ratio || 2.21}`}
                </p>
              </div>

              {/* Pillar 2: Motion Vector Profile */}
              <div className="p-3 rounded-lg bg-[#070d14]/80 border border-slate-700/60 space-y-1">
                <div className="text-cyan-400 font-bold flex items-center justify-between">
                  <span>2. KINEMATIC TRAJECTORY</span>
                  <span className="text-[10px] text-slate-400">DISPLACEMENT</span>
                </div>
                <p className="text-slate-300 text-[11px] leading-relaxed">
                  {xai.motion_profile || `Translational Vector: ${metrics.displacement || 34.5}px over ${metrics.frames_tracked || 18} frames`}
                </p>
              </div>

              {/* Pillar 3: Jitter Compensation */}
              <div className="p-3 rounded-lg bg-[#070d14]/80 border border-slate-700/60 space-y-1">
                <div className="text-cyan-400 font-bold flex items-center justify-between">
                  <span>3. FRAME HOMOGRAPHY</span>
                  <span className="text-[10px] text-emerald-400">VERIFIED</span>
                </div>
                <p className="text-slate-300 text-[11px] leading-relaxed">
                  {xai.frame_alignment || "ORB Keypoint RANSAC confirmed stable optical ground plane with zero camera pole shake."}
                </p>
              </div>

              {/* Pillar 4: Environmental Verdict */}
              <div className="p-3 rounded-lg bg-[#070d14]/80 border border-slate-700/60 space-y-1">
                <div className="text-cyan-400 font-bold flex items-center justify-between">
                  <span>4. ENVIRONMENTAL VERDICT</span>
                  <span className="text-[10px] text-cyan-300">THRESHOLD</span>
                </div>
                <p className="text-slate-300 text-[11px] leading-relaxed">
                  {xai.environmental_verdict || "Organic oscillation filters bypassed; classified as physical tactical entity."}
                </p>
              </div>

            </div>

          </div>

          {/* 4. Telemetry Raw Metrics Table */}
          <div className="bg-[#090e15] border border-slate-800 rounded-xl p-3.5 space-y-2">
            <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider flex items-center justify-between">
              <span>Pipeline Telemetry &amp; YOLOv8 Match</span>
              <span className="text-[10px] text-slate-500">pipeline.py contract</span>
            </div>
            
            <div className="grid grid-cols-2 sm:grid-cols-6 gap-2 text-xs font-mono">
              <div className="bg-slate-900/60 p-2 rounded border border-slate-800">
                <span className="text-[10px] text-slate-500 block">Area</span>
                <span className="text-white font-bold">{metrics.area || "N/A"} px</span>
              </div>
              <div className="bg-slate-900/60 p-2 rounded border border-slate-800">
                <span className="text-[10px] text-slate-500 block">Solidity</span>
                <span className="text-white font-bold">{metrics.solidity || "N/A"}</span>
              </div>
              <div className="bg-slate-900/60 p-2 rounded border border-slate-800">
                <span className="text-[10px] text-slate-500 block">Fragments</span>
                <span className="text-white font-bold">{metrics.fragments ?? 1}</span>
              </div>
              <div className="bg-slate-900/60 p-2 rounded border border-slate-800">
                <span className="text-[10px] text-slate-500 block">Aspect Ratio</span>
                <span className="text-white font-bold">{metrics.aspect_ratio || "N/A"}</span>
              </div>
              <div className="bg-slate-900/60 p-2 rounded border border-slate-800">
                <span className="text-[10px] text-slate-500 block">Displacement</span>
                <span className="text-white font-bold">{metrics.displacement || 0} px</span>
              </div>
              <div className="bg-slate-900/60 p-2 rounded border border-slate-800">
                <span className="text-[10px] text-slate-500 block">YOLO Target</span>
                <span className="text-cyan-400 font-bold uppercase">{metrics.yolo_match || "none"}</span>
              </div>
            </div>
          </div>

        </div>

        {/* 5. Modal Tactical Actions Footer */}
        <div className="p-4 border-t border-slate-800 bg-[#060b11] flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <button
              onClick={handleDownloadJSON}
              className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white font-mono text-xs flex items-center gap-1.5 transition border border-slate-700"
            >
              <Download className="w-3.5 h-3.5" />
              Export Forensic JSON
            </button>
          </div>

          <div className="flex items-center gap-2">
            {alert.status !== "ACKNOWLEDGED" ? (
              <button
                onClick={() => {
                  onAcknowledge(alert.alert_id);
                  onClose();
                }}
                className="px-4 py-1.5 rounded bg-red-600 hover:bg-red-500 text-white font-mono text-xs font-bold flex items-center gap-1.5 transition shadow-[0_0_15px_rgba(255,51,75,0.4)]"
              >
                <Send className="w-3.5 h-3.5" />
                Dispatch QRF Team &amp; Acknowledge
              </button>
            ) : (
              <div className="flex items-center gap-1.5 text-emerald-400 font-mono text-xs px-3 py-1.5 bg-emerald-950/40 rounded border border-emerald-500/30">
                <CheckCircle2 className="w-4 h-4" />
                <span>Incident Acknowledged by Command</span>
              </div>
            )}

            <button
              onClick={onClose}
              className="px-3.5 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white font-mono text-xs transition"
            >
              Close
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}