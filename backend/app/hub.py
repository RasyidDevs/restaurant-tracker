"""State bersama antara thread worker CV (meja & parkir) dan API (thread-safe)."""

from __future__ import annotations

import threading
from collections import deque
from typing import Any

from .config import Config
from .core.detection import Detection
from .core.perception import Perception
from .core.zones import TableObs
from .features.parking import ParkingFeature, ParkingRules, SlotObs
from .features.waiting_time import WaitingRules, WaitingTimeFeature


class Hub:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.perception = Perception(cfg.tables, cfg.core)
        self.waiting = WaitingTimeFeature(self.perception, WaitingRules.from_dict(cfg.features.get("waiting_time")))
        self.perception.add_feature(self.waiting)

        self.parking = ParkingFeature(cfg.parking_slots, ParkingRules.from_dict(cfg.features.get("parking")))
        self._resolved_alerts: set[str] = set()

        self.events: deque[dict[str, Any]] = deque(maxlen=500)
        self.source_status: dict[str, Any] = {"state": "starting", "detail": ""}
        self.parking_status: dict[str, Any] = (
            {"state": "starting", "detail": ""}
            if cfg.parking_source is not None
            else {"state": "idle", "detail": "Sumber video parkir belum diatur (isi parking_source atau --parking-source)"}
        )
        self.latest_jpeg: bytes | None = None
        self.latest_parking_jpeg: bytes | None = None

    # dipanggil worker meja ---------------------------------------------
    def step(self, t: float, obs: dict[str, TableObs]) -> None:
        with self.lock:
            self.events.extend(self.perception.step(t, obs))

    def step_detections(self, t: float, dets: list[Detection]) -> None:
        with self.lock:
            self.events.extend(self.perception.step_detections(t, dets))

    def set_status(self, state: str, detail: str = "") -> None:
        with self.lock:
            self.source_status = {"state": state, "detail": detail}

    # dipanggil worker parkir -------------------------------------------
    def step_parking(self, t: float, obs: dict[str, SlotObs]) -> None:
        with self.lock:
            self.events.extend(self.parking.step(t, obs))

    def step_parking_detections(
        self, t: float, dets: list[Detection], frame_hw: tuple[int, int] | None = None
    ) -> None:
        with self.lock:
            self.events.extend(self.parking.step_detections(t, dets, frame_hw))

    def set_parking_status(self, state: str, detail: str = "") -> None:
        with self.lock:
            self.parking_status = {"state": state, "detail": detail}

    # dipanggil API -----------------------------------------------------
    def core_snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {**self.perception.snapshot(), "source": dict(self.source_status)}

    def waiting_snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {**self.waiting.snapshot(self.perception), "source": dict(self.source_status)}

    def confirm_waiting(self, session_id: str) -> dict[str, Any] | None:
        with self.lock:
            return self.waiting.confirm(session_id, self.perception.now)

    def parking_snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {**self.parking.snapshot(), "source": dict(self.parking_status)}

    def notify_parking(self, slot_id: str) -> dict[str, Any] | None:
        with self.lock:
            return self.parking.notify(slot_id)

    def resolve_alert(self, alert_id: str) -> bool:
        with self.lock:
            if self.parking.resolve_alert(alert_id):
                return True
            self._resolved_alerts.add(alert_id)
            return True

    def alerts_snapshot(self) -> dict[str, Any]:
        with self.lock:
            items: list[dict[str, Any]] = []
            for a in self.parking.alerts:
                items.append(
                    {
                        "id": a["id"],
                        "type": "parkir-lama",
                        "severity": a["severity"],
                        "title": a["title"],
                        "description": a["message"],
                        "location": f"Slot {a['slot']}",
                        "t": a["t"],
                        "camera": "CAM-P2" if a.get("vehicle_type") == "motor" else "CAM-P1",
                        "resolved": bool(a["resolved"] or a["id"] in self._resolved_alerts),
                    }
                )
            active_tables = {tid for tid, tw in self.waiting.per_table.items() if tw.phase == "menunggu"}
            for a in self.waiting.alerts:
                aid = f"WA-{a['table']}-{a['kind']}-{int(a['t'])}"
                tb = self.perception.tables.get(a["table"])
                tname = tb.zone.name if tb else a["table"]
                items.append(
                    {
                        "id": aid,
                        "type": "waiting-lama",
                        "severity": "tinggi" if a["kind"] == "belum_disajikan" else "sedang",
                        "title": "Belum ada sajian" if a["kind"] == "belum_disajikan" else "Pesanan belum lengkap",
                        "description": a["message"],
                        "location": tname,
                        "t": a["t"],
                        "camera": "CAM-01",
                        "resolved": aid in self._resolved_alerts or a["table"] not in active_tables,
                    }
                )
            items.sort(key=lambda x: x["t"], reverse=True)
            now = max(self.perception.now, self.parking.now)
            return {"now": now, "alerts": items[:80]}
