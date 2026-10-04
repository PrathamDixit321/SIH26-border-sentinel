import React from "react";
import { AlertTriangle, Clock, MapPin } from "lucide-react";

export default function WeaponAlertBanner({ alert }) {
  if (alert?.weapon_detected !== true) return null;

  const confidence = Number.isFinite(alert.weapon_confidence)
    ? `${(alert.weapon_confidence * 100).toFixed(0)}%`
    : "N/A";
  const location = alert.location || [alert.sector, alert.camera_id].filter(Boolean).join(" / ");

  return (
    <section
      role="alert"
      data-testid="weapon-alert-banner"
      className="border-b-2 border-red-500 bg-gradient-to-r from-red-950 via-[#320d13] to-[#170b10] p-4 shadow-[inset_0_0_28px_rgba(239,68,68,0.16)]"
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 rounded border border-red-400/60 bg-red-500/20 p-2 text-red-300">
          <AlertTriangle className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-red-200">
              Immediate Weapon Alert
            </span>
            <span className="rounded border border-red-400/60 bg-red-500/20 px-1.5 py-0.5 text-[9px] font-mono font-bold text-red-200">
              CRITICAL PRIORITY
            </span>
          </div>
          <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h3 className="text-lg font-mono font-black uppercase text-white">
              {alert.weapon_type || "Unknown weapon"}
            </h3>
            <span className="text-sm font-mono font-bold text-red-200">
              {confidence} confidence
            </span>
          </div>
          {(alert.timestamp || location) && (
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] font-mono text-red-100/80">
              {alert.timestamp && (
                <span className="inline-flex items-center gap-1.5">
                  <Clock className="h-3 w-3" />
                  <time dateTime={alert.timestamp}>{alert.timestamp}</time>
                </span>
              )}
              {location && (
                <span className="inline-flex items-center gap-1.5">
                  <MapPin className="h-3 w-3" />
                  {location}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}