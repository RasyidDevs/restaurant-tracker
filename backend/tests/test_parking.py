"""Tes fitur peringatan parkir motor/mobil (slot terkalibrasi, auto-slot, ganti track_id, API)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import BACKEND_DIR, _resolve_source
from app.core.detection import Detection
from app.features.parking import ParkingFeature, ParkingRules, ParkingZone
from app.main import app

CAR_SLOT = ParkingZone("C-01", "mobil", [[0, 0], [200, 0], [200, 200], [0, 200]])
BIKE_SLOT = ParkingZone("M-01", "motor", [[250, 0], [400, 0], [400, 200], [250, 200]])


def _run(feat: ParkingFeature, t0: float, t1: float, dets: list[Detection], step: float = 1.0) -> float:
    t = t0
    while t < t1:
        feat.step_detections(t, dets)
        t = round(t + step, 2)
    return t


def test_passing_vehicle_does_not_occupy_slot():
    f = ParkingFeature([CAR_SLOT], ParkingRules(min_dwell_s=20, lost_grace_s=15))
    t = _run(f, 0, 8, [Detection("car", (20, 20, 150, 150), 0.9, 1)])
    _run(f, t, 40, [])
    snap = f.snapshot()
    assert not snap["slots"][0]["occupied"]
    assert snap["alerts"] == []


def test_car_and_motorcycle_near_and_over_limit_alerts():
    rules = ParkingRules(car_limit_min=3, bike_limit_min=2, warn_ratio=0.85, min_dwell_s=5, lost_grace_s=5)
    f = ParkingFeature([CAR_SLOT, BIKE_SLOT], rules)
    car = Detection("car", (20, 20, 150, 150), 0.9, 10)
    bike = Detection("motorcycle", (270, 20, 350, 150), 0.88, 20)

    # Motor batas 120 dtk -> mendekati di 102 dtk, lewat di >120 dtk
    t = _run(f, 0, 105, [car, bike])
    kinds_bike = [a["kind"] for a in f.alerts if a["slot"] == "M-01"]
    assert kinds_bike == ["mendekati"]

    t = _run(f, t, 125, [car, bike])
    kinds_bike = [a["kind"] for a in f.alerts if a["slot"] == "M-01"]
    assert kinds_bike == ["mendekati", "lewat"]

    # Mobil batas 180 dtk -> lewat di >180 dtk
    t = _run(f, t, 185, [car, bike])
    snap = f.snapshot()
    assert snap["stats"]["over_count"] == 2
    assert [w["id"] for w in snap["warnings"]] == ["M-01", "C-01"]


def test_track_id_switch_and_brief_occlusion_keep_duration():
    rules = ParkingRules(car_limit_min=10, min_dwell_s=5, lost_grace_s=10)
    f = ParkingFeature([CAR_SLOT], rules)

    t = _run(f, 0, 30, [Detection("car", (20, 20, 150, 150), 0.9, 1)])
    t = _run(f, t, 36, [])  # tertutup 6 detik (< lost_grace_s=10)
    t = _run(f, t, 120, [Detection("car", (22, 22, 152, 152), 0.9, 99)])  # ByteTrack ganti ID 1 -> 99

    slot = f.snapshot()["slots"][0]
    assert slot["occupied"]
    assert slot["track_id"] == 99
    assert slot["duration_s"] == pytest.approx(119, abs=1.5)


def test_departure_records_completed_and_resolves_alert():
    rules = ParkingRules(bike_limit_min=1, min_dwell_s=4, lost_grace_s=5)
    f = ParkingFeature([BIKE_SLOT], rules)
    bike = Detection("motorcycle", (270, 20, 350, 150), 0.9, 7)

    t = _run(f, 0, 70, [bike])
    assert f.snapshot()["slots"][0]["level"] == "lewat"

    # Juru parkir diberitahu
    notified = f.notify("M-01")
    assert notified is not None and notified["notified"] is True

    # Motor keluar > lost_grace_s
    t = _run(f, t, 85, [])
    snap = f.snapshot()
    assert not snap["slots"][0]["occupied"]
    assert len(snap["completed"]) == 1
    assert all(a["resolved"] for a in snap["alerts"])


def test_auto_slot_mode_tracks_uncalibrated_video():
    rules = ParkingRules(bike_limit_min=1, min_dwell_s=4, lost_grace_s=5)
    f = ParkingFeature([], rules)  # tanpa parking_slots di config
    assert f.auto_mode

    t = _run(f, 0, 65, [Detection("motorcycle", (100, 100, 180, 220), 0.9, 42)])
    snap = f.snapshot()
    assert len(snap["slots"]) == 1
    assert snap["slots"][0]["id"] == "M-01"
    assert snap["slots"][0]["level"] == "lewat"

    _run(f, t, 80, [])
    assert f.snapshot()["slots"] == []
    assert len(f.snapshot()["completed"]) == 1


def test_resolve_relative_source_from_outside_backend():
    resolved = _resolve_source("config/config.example.json")
    assert resolved == str(BACKEND_DIR / "config" / "config.example.json")


def test_api_parking_and_alerts_endpoints(monkeypatch):
    monkeypatch.setenv("CV_SOURCE", "simulate")
    monkeypatch.setenv("CV_PARKING_SOURCE", "simulate")
    with TestClient(app) as client:
        r_park = client.get("/api/parking")
        assert r_park.status_code == 200
        pdata = r_park.json()
        assert pdata["stats"]["car_total"] >= 1
        assert pdata["stats"]["bike_total"] >= 1

        occ = next((s for s in pdata["slots"] if s["occupied"]), None)
        if occ:
            r_not = client.post(f"/api/parking/slots/{occ['id']}/notify")
            assert r_not.status_code == 200
            assert r_not.json()["notified"] is True

        r_empty = client.post("/api/parking/slots/TIDAK-ADA/notify")
        assert r_empty.status_code == 404

        r_alerts = client.get("/api/alerts")
        assert r_alerts.status_code == 200
        adata = r_alerts.json()
        assert "alerts" in adata
        if adata["alerts"]:
            aid = adata["alerts"][0]["id"]
            assert client.post(f"/api/alerts/{aid}/resolve").status_code == 200
