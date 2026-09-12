import React, { useState, useEffect, useCallback, useRef } from "react";
import TopNav from "./components/TopNav";
import MetricsBar from "./components/MetricsBar";
import VideoFeed from "./components/VideoFeed";
import AlertFeed from "./components/AlertFeed";
import ExplainabilityModal from "./components/ExplainabilityModal";
import { playAlertSound } from "./utils/sound";

export default function App() {
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [selectedCam, setSelectedCam] = useState("CAM-01");
  const [wsConnected, setWsConnected] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [isSimulating, setIsSimulating] = useState(false);

  const wsRef = useRef(null);

  // Fetch initial alerts and stats
  const fetchInitialData = useCallback(async () => {
    try {
      const [alertsRes, statsRes] = await Promise.all([
        fetch("/api/alerts?limit=50"),
        fetch("/api/stats")
      ]);
      if (alertsRes.ok) {
        const data = await alertsRes.json();
        setAlerts(data);
      }
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }
    } catch (err) {
      console.warn("Failed to fetch initial telemetry:", err);
    }
  }, []);

  // Setup WebSocket connection
  useEffect(() => {
    fetchInitialData();

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/alerts`;

    let reconnectTimer = null;

    const connectWS = () => {
      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setWsConnected(true);
          console.log("[WS] Connected to Border Sentinel Alert Stream");
        };

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === "NEW_ALERT" && msg.data) {
              const newAlert = msg.data;
              setAlerts((prev) => [newAlert, ...prev.filter((a) => a.alert_id !== newAlert.alert_id)]);
              
              // Play alert sound if not suppressed
              if (soundEnabled && !newAlert.environmental_noise_filtered) {
                playAlertSound(newAlert.threat_level);
              }

              // Auto-refresh stats
              fetch("/api/stats")
                .then((r) => r.json())
                .then((s) => setStats(s))
                .catch(() => {});
            } else if (msg.type === "ALERT_ACKNOWLEDGED" && msg.data) {
              setAlerts((prev) =>
                prev.map((a) => (a.alert_id === msg.data.alert_id ? msg.data : a))
              );
              if (selectedAlert?.alert_id === msg.data.alert_id) {
                setSelectedAlert(msg.data);
              }
            } else if (msg.stats) {
              setStats(msg.stats);
            }
          } catch (e) {
            console.warn("WS Parse Error:", e);
          }
        };

        ws.onclose = () => {
          setWsConnected(false);
          reconnectTimer = setTimeout(connectWS, 3000);
        };

        ws.onerror = () => {
          setWsConnected(false);
          ws.close();
        };
      } catch (err) {
        setWsConnected(false);
        reconnectTimer = setTimeout(connectWS, 4000);
      }
    };

    connectWS();

    // Fallback polling every 5 seconds
    const pollInterval = setInterval(() => {
      fetch("/api/stats")
        .then((r) => r.json())
        .then((s) => setStats(s))
        .catch(() => {});
    }, 5000);

    return () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      clearInterval(pollInterval);
      if (wsRef.current) wsRef.current.close();
    };
  }, [fetchInitialData, soundEnabled, selectedAlert]);

  // Acknowledge alert
  const handleAcknowledge = async (alertId) => {
    try {
      const res = await fetch(`/api/alerts/${alertId}/acknowledge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ operator_notes: "Acknowledged and verified by operator" }),
      });
      if (res.ok) {
        const updated = await res.json();
        setAlerts((prev) =>
          prev.map((a) => (a.alert_id === alertId ? updated : a))
        );
        if (selectedAlert?.alert_id === alertId) {
          setSelectedAlert(updated);
        }
      }
    } catch (err) {
      console.error("Failed to acknowledge alert:", err);
    }
  };

  // Trigger simulated threat (Demo)
  const handleSimulateThreat = async () => {
    setIsSimulating(true);
    try {
      const res = await fetch("/api/simulate-threat", { method: "POST" });
      if (res.ok) {
        const alert = await res.json();
        // Immediately select this alert so the judges see the prominent explainability modal right away!
        setSelectedAlert(alert);
      }
    } catch (err) {
      console.error("Simulation error:", err);
    } finally {
      setIsSimulating(false);
    }
  };

  // Trigger simulated environmental noise (Demo)
  const handleSimulateEnvironmental = async () => {
    setIsSimulating(true);
    try {
      const res = await fetch("/api/simulate-environmental", { method: "POST" });
      if (res.ok) {
        const alert = await res.json();
        setSelectedAlert(alert);
      }
    } catch (err) {
      console.error("Environmental simulation error:", err);
    } finally {
      setIsSimulating(false);
    }
  };

  const latestAlert = alerts.find((a) => a.threat_level === "CRITICAL" && a.status === "UNACKNOWLEDGED") || alerts[0];

  return (
    <div className="min-h-screen bg-[#060a0f] text-slate-100 flex flex-col font-sans">
      {/* 1. Top Navigation Bar */}
      <TopNav
        stats={stats}
        wsConnected={wsConnected}
        soundEnabled={soundEnabled}
        setSoundEnabled={setSoundEnabled}
        onSimulateThreat={handleSimulateThreat}
        onSimulateEnvironmental={handleSimulateEnvironmental}
        isSimulating={isSimulating}
      />

      {/* 2. Main Dashboard View */}
      <main className="flex-1 p-3 sm:p-4 max-w-[1700px] w-full mx-auto flex flex-col">
        
        {/* Telemetry Metrics Strip */}
        <MetricsBar stats={stats} />

        {/* Tactical 2-Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 flex-1">
          
          {/* Left Column: Live Border Surveillance Feed (7 Cols) */}
          <div className="lg:col-span-7 flex flex-col space-y-4">
            <VideoFeed
              selectedCam={selectedCam}
              setSelectedCam={setSelectedCam}
              latestAlert={latestAlert}
              onSelectAlert={(a) => setSelectedAlert(a)}
            />

            {/* Explainable AI Spotlight Card below feed */}
            {latestAlert && (
              <div className="bg-[#0b131d]/90 border border-slate-800 rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-lg">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800">
                      CURRENT SPOTLIGHT REASONING
                    </span>
                    <span className="text-xs font-mono text-slate-400">
                      {latestAlert.sector}
                    </span>
                  </div>
                  <p className="text-xs text-slate-200 leading-relaxed font-sans">
                    {latestAlert.reason}
                  </p>
                </div>

                <button
                  onClick={() => setSelectedAlert(latestAlert)}
                  className="px-3 py-1.5 rounded bg-cyan-500 hover:bg-cyan-400 text-black font-mono text-xs font-bold whitespace-nowrap transition shadow-[0_0_12px_rgba(0,240,255,0.3)] shrink-0"
                >
                  Expand Forensic Dossier &rarr;
                </button>
              </div>
            )}
          </div>

          {/* Right Column: Real-Time Incident Triage Feed (5 Cols) */}
          <div className="lg:col-span-5 flex flex-col">
            <AlertFeed
              alerts={alerts}
              selectedAlert={selectedAlert}
              onSelectAlert={(alert) => setSelectedAlert(alert)}
              onAcknowledge={handleAcknowledge}
            />
          </div>

        </div>

      </main>

      {/* 3. Click-to-Expand Snapshot & Prominent Explainability Modal */}
      {selectedAlert && (
        <ExplainabilityModal
          alert={selectedAlert}
          onClose={() => setSelectedAlert(null)}
          onAcknowledge={handleAcknowledge}
        />
      )}

      {/* 4. Footer */}
      <footer className="border-t border-slate-800/80 bg-[#070b10] py-2 px-4 text-center text-xs font-mono text-slate-500">
        <span>MINISTRY OF HOME AFFAIRS // SMART INDIA HACKATHON 2026 // PROBLEM ID: SIH26187</span>
        <span className="hidden sm:inline text-slate-700 mx-2">|</span>
        <span className="hidden sm:inline text-cyan-500/80">AI-Based Intelligent Video Analytics Platform</span>
      </footer>
    </div>
  );
}