import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { after, before, test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const dashboardRoot = resolve(import.meta.dirname, "..");
const contractAlerts = JSON.parse(
  readFileSync(resolve(dashboardRoot, "../contracts/sample_alerts.json"), "utf8")
);
const pipelineAlerts = JSON.parse(
  readFileSync(resolve(dashboardRoot, "../outputs/alerts.json"), "utf8")
);

let vite;
let AlertFeed;
let getWeaponAlertFromEvent;

before(async () => {
  vite = await createServer({
    root: dashboardRoot,
    configFile: resolve(dashboardRoot, "vite.config.js"),
    server: { middlewareMode: true },
    appType: "custom",
  });
  ({ default: AlertFeed } = await vite.ssrLoadModule("/src/components/AlertFeed.jsx"));
  ({ getWeaponAlertFromEvent } = await vite.ssrLoadModule("/src/utils/weaponAlerts.js"));
});

after(async () => {
  await vite?.close();
});

function renderFeed(alerts = contractAlerts, weaponAlert) {
  return renderToStaticMarkup(
    React.createElement(AlertFeed, {
      alerts,
      weaponAlert,
      selectedAlert: null,
      onSelectAlert: () => {},
      onAcknowledge: () => {},
    })
  );
}

test("existing normal alerts render with their location and confidence", () => {
  const markup = renderFeed();
  assert.match(markup, /5 Events/);
  assert.match(markup, /PEDESTRIAN/);
  assert.match(markup, /Sector 4 \(North Ridge Fence\)/);
  assert.match(markup, /96% Match/);
  assert.doesNotMatch(markup, /weapon-alert-banner/);
});

test("existing pipeline alert JSON remains renderable", () => {
  const markup = renderFeed(pipelineAlerts);
  assert.match(markup, new RegExp(`${pipelineAlerts.length} Events`));
  assert.match(markup, new RegExp(pipelineAlerts[0].category));
  assert.match(markup, new RegExp(`${(pipelineAlerts[0].confidence * 100).toFixed(0)}% Match`));
});

test("mock weapon detection shows type, confidence, timestamp, and location", () => {
  const markup = renderFeed(contractAlerts, {
    weapon_detected: true,
    weapon_type: "rifle",
    weapon_confidence: 0.94,
    timestamp: "2026-10-04T10:30:00Z",
    sector: "Sector 7",
    camera_id: "CAM-03",
  });
  assert.match(markup, /Immediate Weapon Alert/);
  assert.match(markup, /CRITICAL PRIORITY/);
  assert.ok(markup.indexOf("weapon-alert-banner") < markup.indexOf("REAL-TIME INCIDENT TRIAGE FEED"));
  assert.match(markup, />rifle</);
  assert.match(markup, /94% confidence/);
  assert.match(markup, /2026-10-04T10:30:00Z/);
  assert.match(markup, /Sector 7 \/ CAM-03/);
});

test("weapon_detected false hides the weapon banner and keeps normal alerts", () => {
  const markup = renderFeed(contractAlerts, {
    weapon_detected: false,
    weapon_type: "rifle",
    weapon_confidence: 0.94,
  });
  assert.doesNotMatch(markup, /weapon-alert-banner/);
  assert.match(markup, /PEDESTRIAN/);
});

test("priority WebSocket weapon events adapt directly to the existing banner contract", () => {
  const weaponData = {
    weapon_detected: true,
    weapon_type: "rifle",
    weapon_confidence: 0.94,
    timestamp: "2026-10-04T10:30:00Z",
    location: "Sector 7",
  };
  assert.deepEqual(getWeaponAlertFromEvent({ type: "WEAPON_ALERT", data: weaponData }), weaponData);
  assert.equal(getWeaponAlertFromEvent({ type: "WEAPON_ALERT", data: { weapon_detected: false } }).weapon_detected, false);
  assert.equal(getWeaponAlertFromEvent({ type: "NEW_ALERT", data: weaponData }), null);
});

test("low-light status reflects active and inactive telemetry", () => {
  const active = renderFeed([{
    ...contractAlerts[0],
    metrics: { ...contractAlerts[0].metrics, low_light_active: true },
  }]);
  const inactive = renderFeed([{
    ...contractAlerts[0],
    metrics: { ...contractAlerts[0].metrics, low_light_active: false },
  }]);
  assert.match(active, /data-testid="low-light-status"[^>]*>ACTIVE/);
  assert.match(inactive, /data-testid="low-light-status"[^>]*>INACTIVE/);
});

test("thermal status reflects active mode and defaults inactive without telemetry", () => {
  const active = renderFeed([{ ...contractAlerts[0], input_mode: "THERMAL" }]);
  const inactive = renderFeed(contractAlerts);
  assert.match(active, /data-testid="thermal-status"[^>]*>ACTIVE/);
  assert.match(inactive, /data-testid="thermal-status"[^>]*>INACTIVE/);
});