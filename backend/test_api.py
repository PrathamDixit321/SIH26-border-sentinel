import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from starlette.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

res_health = client.get('/api/health')
assert res_health.status_code == 200, f'Health failed: {res_health.text}'
print('[PASS] /api/health ->', res_health.json())

res_stats = client.get('/api/stats')
assert res_stats.status_code == 200, f'Stats failed: {res_stats.text}'
print('[PASS] /api/stats -> Threat Status:', res_stats.json()['threat_status'])

res_alerts = client.get('/api/alerts')
assert res_alerts.status_code == 200, f'Alerts failed: {res_alerts.text}'
alerts = res_alerts.json()
assert len(alerts) >= 5, f'Expected at least 5 alerts, got {len(alerts)}'
print(f'[PASS] /api/alerts -> Loaded {len(alerts)} alerts')

res_sim = client.post('/api/simulate-threat')
assert res_sim.status_code == 200, f'Simulation failed: {res_sim.text}'
new_alert = res_sim.json()
print(f'[PASS] /api/simulate-threat -> Created alert {new_alert["alert_id"]} ({new_alert["threat_level"]})')

res_ack = client.post(f'/api/alerts/{new_alert["alert_id"]}/acknowledge', json={'operator_notes': 'QRF Team Alpha Dispatched'})
assert res_ack.status_code == 200
print(f'[PASS] /api/alerts/acknowledge -> {res_ack.json()["status"]}')

# Test live stream frame ingestion
res_frame = client.post('/api/stream/frame', content=b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb')
assert res_frame.status_code == 200
print('[PASS] /api/stream/frame -> Ingested live frame successfully!')

print('\nALL BACKEND API TESTS PASSED 100%!')