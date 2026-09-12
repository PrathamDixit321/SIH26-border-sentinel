import React, { useState, useEffect } from "react";
import { ShieldAlert, Volume2, VolumeX, Radio, Activity, RefreshCw, Zap, Wind } from "lucide-react";

export default function TopNav({
  stats,
  wsConnected,
  soundEnabled,
  setSoundEnabled,
  onSimulateThreat,
  onSimulateEnvironmental,
  isSimulating
}) {
  const [timeStr, setTimeStr] = useState("");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(now.toLocaleTimeString("en-IN", { hour12: false }) + " IST");
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const threatStatus = stats?.threat_status || "NORMAL";

  return (
    <header className="border-b border-slate-800 bg-[#090e15]/90 backdrop-blur sticky top-0 z-40 px-4 py-2.5">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 max-w-[1700px] mx-auto">
        
        {/* Left: Branding & Status */}
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-cyan-950/60 border border-cyan-500/40 text-cyan-400 shadow-[0_0_15px_rgba(0,240,255,0.15)]">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-mono font-bold tracking-wider text-base text-white">
                BORDER SENTINEL AI
              </h1>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 font-mono">
                SIH-26187
              </span>
              <span className="hidden sm:inline-block text-[10px] px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800/60 font-mono">
                MHA // DEFENSE C2
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Autonomous Video Analytics &amp; Explainable Threat Discrimination
            </p>
          </div>
        </div>

        {/* Center: Real-time DEFCON Status & Live Indicator */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2 px-3 py-1 rounded border bg-slate-900/80 border-slate-800 font-mono text-xs">
            <Radio className={`w-3.5 h-3.5 ${wsConnected ? "text-emerald-400 animate-pulse" : "text-amber-400"}`} />
            <span className="text-slate-400">TELEMETRY:</span>
            <span className={wsConnected ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"}>
              {wsConnected ? "LIVE STREAM" : "POLLING"}
            </span>
          </div>

          <div className="flex items-center gap-2 px-3 py-1 rounded border bg-slate-900/80 border-slate-800 font-mono text-xs">
            <Activity className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-slate-400">STATUS:</span>
            <span
              className={`font-bold px-2 py-0.5 rounded text-[11px] ${
                threatStatus === "CRITICAL"
                  ? "bg-red-500/20 text-red-400 border border-red-500/50 animate-pulse"
                  : threatStatus === "ELEVATED"
                  ? "bg-amber-500/20 text-amber-400 border border-amber-500/50"
                  : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/50"
              }`}
            >
              DEFCON // {threatStatus}
            </span>
          </div>

          <div className="hidden md:block font-mono text-xs text-slate-400 px-2 py-1 bg-slate-900/40 rounded border border-slate-800">
            {timeStr}
          </div>
        </div>

        {/* Right: Quick Demo Actions & Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Sound Toggle */}
          <button
            onClick={() => setSoundEnabled(!soundEnabled)}
            className={`p-2 rounded border text-xs flex items-center gap-1.5 transition ${
              soundEnabled
                ? "bg-cyan-950/40 border-cyan-500/40 text-cyan-300 hover:bg-cyan-900/40"
                : "bg-slate-900 border-slate-800 text-slate-500 hover:text-slate-400"
            }`}
            title={soundEnabled ? "Siren Audio Active" : "Siren Audio Muted"}
          >
            {soundEnabled ? <Volume2 className="w-4 h-4 text-cyan-400" /> : <VolumeX className="w-4 h-4" />}
            <span className="hidden sm:inline font-mono">{soundEnabled ? "AUDIO ON" : "MUTED"}</span>
          </button>

          {/* Quick Demo Threat Injection */}
          <button
            onClick={onSimulateThreat}
            disabled={isSimulating}
            className="px-2.5 py-1.5 rounded bg-red-950/60 border border-red-500/50 hover:bg-red-900/60 text-red-300 hover:text-white font-mono text-xs flex items-center gap-1.5 transition shadow-[0_0_10px_rgba(255,51,75,0.15)] disabled:opacity-50"
            title="Inject simulated human intruder to demonstrate real-time alert and XAI reasoning"
          >
            <Zap className="w-3.5 h-3.5 text-red-400 fill-red-400/20" />
            <span>INTRUDER ALERT</span>
          </button>

          {/* Quick Demo Environmental Suppression */}
          <button
            onClick={onSimulateEnvironmental}
            disabled={isSimulating}
            className="px-2.5 py-1.5 rounded bg-slate-900 hover:bg-slate-800 border border-emerald-500/40 text-emerald-300 font-mono text-xs flex items-center gap-1.5 transition disabled:opacity-50"
            title="Inject simulated wind/foliage motion to prove false-alarm rejection"
          >
            <Wind className="w-3.5 h-3.5 text-emerald-400" />
            <span>WIND/NOISE (USP)</span>
          </button>
        </div>

      </div>
    </header>
  );
}