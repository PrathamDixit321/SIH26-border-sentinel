import json
import socket
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import monotonic
from unittest.mock import patch

import requests
import uvicorn
from websockets.sync.client import connect

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.main import app, store


def _post_and_receive(session, websocket, api_url, path, payload):
    with ThreadPoolExecutor(max_workers=1) as executor:
        response_future = executor.submit(
            session.post, f"{api_url}{path}", json=payload, timeout=5
        )
        event = json.loads(websocket.recv(timeout=5))
        response = response_future.result(timeout=5)
    return response, event


def _fake_add(alert_data):
    alert_data = dict(alert_data)
    alert_data.setdefault("alert_id", f"TEST-{alert_data.get('camera_id', 'CAM')}")
    alert_data.setdefault("timestamp", "2026-10-04T10:00:00Z")
    alert_data.setdefault("status", "UNACKNOWLEDGED")
    return alert_data


def test_normal_and_weapon_alerts_use_separate_immediate_websocket_events():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    listener.setblocking(False)
    port = listener.getsockname()[1]
    api_url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical", lifespan="off"))
    server_thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    server_thread.start()
    session = requests.Session()
    deadline = monotonic() + 5
    while monotonic() < deadline:
        try:
            if session.get(f"{api_url}/api/health", timeout=0.2).ok:
                break
        except requests.RequestException:
            threading.Event().wait(0.05)
    else:
        server.should_exit = True
        server_thread.join(timeout=5)
        listener.close()
        raise AssertionError("Local FastAPI server did not become ready")

    initial_alert_count = len(store.get_all(limit=200))
    normal_payload = {
        "alert_id": "NORMAL-TEST-01",
        "camera_id": "CAM-01",
        "sector": "Sector 4",
        "threat_level": "HIGH",
        "label": "HUMAN",
        "category": "PEDESTRIAN",
        "confidence": 0.91,
        "bbox": [20, 30, 40, 80],
        "reason": "Normal alert sequence test",
    }
    weapon_payload = {
        "weapon_detected": True,
        "weapon_type": "rifle",
        "weapon_confidence": 0.94,
        "timestamp": "2026-10-04T10:30:00Z",
        "sector": "Sector 7",
        "camera_id": "CAM-03",
    }

    try:
        with patch.object(store, "add", side_effect=_fake_add) as add_alert:
            with connect(f"ws://127.0.0.1:{port}/ws/alerts", open_timeout=5) as websocket:
                assert json.loads(websocket.recv(timeout=5))["type"] == "CONNECTION_READY"

                invalid_response = session.post(
                    f"{api_url}/api/weapon-alert",
                    json={"weapon_detected": True},
                    timeout=5,
                )
                assert invalid_response.status_code == 422
                print("[PASS] Incomplete weapon detection -> rejected without broadcasting")

                response, event = _post_and_receive(
                    session, websocket, api_url, "/api/weapon-alert", weapon_payload
                )
                assert response.status_code == 200
                assert event["type"] == "WEAPON_ALERT"
                assert event["data"]["priority"] == "CRITICAL"
                assert event["data"]["weapon_type"] == "rifle"
                assert event["data"]["weapon_confidence"] == 0.94
                assert event["data"]["timestamp"] == weapon_payload["timestamp"]
                assert event["data"]["sector"] == "Sector 7"
                assert event["data"]["camera_id"] == "CAM-03"
                assert add_alert.call_count == 0
                print("[PASS] Weapon alert only -> immediate separate WEAPON_ALERT, metadata preserved, not stored")

                response, event = _post_and_receive(
                    session, websocket, api_url, "/api/alerts", normal_payload
                )
                assert response.status_code == 200
                assert event["type"] == "NEW_ALERT"
                assert event["data"]["alert_id"] == "NORMAL-TEST-01"
                print("[PASS] Normal alert only -> NEW_ALERT delivered over existing WebSocket")

                normal_response, normal_event = _post_and_receive(
                    session,
                    websocket,
                    api_url,
                    "/api/alerts",
                    {**normal_payload, "alert_id": "NORMAL-TEST-02"},
                )
                weapon_response, weapon_event = _post_and_receive(
                    session, websocket, api_url, "/api/weapon-alert", weapon_payload
                )
                assert normal_response.status_code == weapon_response.status_code == 200
                assert normal_event["type"] == "NEW_ALERT"
                assert weapon_event["type"] == "WEAPON_ALERT"
                print("[PASS] Normal followed immediately by weapon -> separate ordered events")

                for index in range(3):
                    response, event = _post_and_receive(
                        session,
                        websocket,
                        api_url,
                        "/api/alerts",
                        {**normal_payload, "alert_id": f"NORMAL-BURST-{index}"},
                    )
                    assert response.status_code == 200
                    assert event["type"] == "NEW_ALERT"

                response, event = _post_and_receive(
                    session, websocket, api_url, "/api/weapon-alert", weapon_payload
                )
                assert response.status_code == 200
                assert event["type"] == "WEAPON_ALERT"
                assert event["data"]["weapon_detected"] is True
                assert add_alert.call_count == 5
                print("[PASS] Multiple normal alerts followed by weapon -> next independent event")

                response, event = _post_and_receive(
                    session,
                    websocket,
                    api_url,
                    "/api/weapon-alert",
                    {"weapon_detected": False},
                )
                assert response.status_code == 200
                assert event["type"] == "WEAPON_ALERT"
                assert event["data"]["weapon_detected"] is False
                assert event["data"]["priority"] == "NORMAL"
                assert add_alert.call_count == 5
                assert len(store.get_all(limit=200)) == initial_alert_count
                print("[PASS] weapon_detected=false -> clear/reset event, no normal-store insertion")
    finally:
        server.should_exit = True
        server_thread.join(timeout=5)
        session.close()
        listener.close()

    print("ALL WEAPON PRIORITY WEBSOCKET TESTS PASSED")


if __name__ == "__main__":
    test_normal_and_weapon_alerts_use_separate_immediate_websocket_events()