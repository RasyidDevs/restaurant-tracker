"""Fitur: peringatan motor atau mobil yang terlalu lama parkir.

Mendukung dua cara pakai pada sumber video parkir terpisah (`parking_source`):
  1. Slot terkalibrasi (`parking_slots` berisi polygon di config.json):
     tiap slot (`C-01`, `M-01`, dst.) memantau apakah ada `car`/`motorcycle` yang menetap.
  2. Tanpa kalibrasi (`parking_slots` kosong pada video asli):
     hanya kendaraan yang benar-benar DIAM di posisi awalnya (IoU >= 0.55 terhadap kotak awal)
     selama >= `min_dwell_s` yang dipromosikan menjadi slot parkir aktif; kendaraan yang sedang
     berjalan/bermanuver tetap ditandai melintas dan tidak membuat slot palsu di jalan.
"""

from __future__ import annotations

import itertools
from collections import deque
from dataclasses import asdict, dataclass, field
from statistics import mean
from typing import Any

from ..core.detection import Detection
from ..core.geometry import Box, Polygon, box_area, box_center, box_to_polygon, iou, point_in_polygon
from ..core.tracks import DwellTracker


@dataclass
class ParkingRules:
    car_limit_min: float = 180.0
    bike_limit_min: float = 120.0
    warn_ratio: float = 0.85
    min_dwell_s: float = 20.0
    lost_grace_s: float = 15.0

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "ParkingRules":
        d = d or {}
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def limit_s_for(self, vehicle_type: str, custom_min: float | None = None) -> float:
        if custom_min is not None:
            return custom_min * 60.0
        return (self.car_limit_min if vehicle_type == "mobil" else self.bike_limit_min) * 60.0


@dataclass
class ParkingZone:
    id: str
    type: str  # "mobil" | "motor"
    zone: Polygon
    limit_min: float | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ParkingZone":
        raw_type = str(d.get("type", "mobil")).lower()
        vtype = "motor" if raw_type in ("motor", "motorcycle", "bike") else "mobil"
        lim = d.get("limit_min")
        return cls(
            id=d["id"],
            type=vtype,
            zone=d["zone"],
            limit_min=float(lim) if lim is not None else None,
        )


@dataclass
class SlotObs:
    vehicle_ids: list[int] = field(default_factory=list)
    vehicle_type: str | None = None  # "mobil" | "motor"
    label: str | None = None


_session_ids = itertools.count(1)
_alert_ids = itertools.count(1)


def _fmt_dur(seconds: float) -> str:
    if seconds < 120:
        return f"{max(0, round(seconds))} detik"
    mins = round(seconds / 60)
    h, m = divmod(mins, 60)
    return f"{h}j {m}m" if h else f"{m}m"


def _group_to_type(group: str) -> str:
    return "motor" if group == "motorcycle" else "mobil"


def _dedup_vehicles(vehicles: list[Detection], frame_hw: tuple[int, int] | None = None) -> list[Detection]:
    """Buang deteksi tumpang-tindih (NMS lintas kelas kendaraan) dan kotak ukuran tidak wajar."""
    frame_area = (frame_hw[0] * frame_hw[1]) if frame_hw else 0
    kept: list[Detection] = []
    for d in sorted(vehicles, key=lambda x: x.conf, reverse=True):
        if frame_area > 0:
            ratio = box_area(d.box) / frame_area
            if ratio < 0.006 or ratio > 0.32:
                continue
        if any(iou(d.box, k.box) >= 0.50 for k in kept):
            continue
        kept.append(d)
    return kept


@dataclass
class ParkingSession:
    id: str
    slot_id: str
    vehicle_type: str
    track_id: int | None
    label: str
    start: float
    limit_s: float
    end: float | None = None
    notified: bool = False
    alerts: list[dict[str, Any]] = field(default_factory=list)

    def duration_s(self, now: float) -> float:
        return max(0.0, (self.end if self.end is not None else now) - self.start)

    def level(self, now: float, warn_ratio: float) -> str:
        if self.end is not None:
            return "selesai"
        r = self.duration_s(now) / self.limit_s if self.limit_s > 0 else 0.0
        if r > 1.0:
            return "lewat"
        if r >= warn_ratio:
            return "mendekati"
        return "normal"

    def to_dict(self, now: float, warn_ratio: float) -> dict[str, Any]:
        dur = self.duration_s(now)
        ratio = dur / self.limit_s if self.limit_s > 0 else 0.0
        d = asdict(self)
        d["duration_s"] = round(dur, 1)
        d["over_s"] = round(max(0.0, dur - self.limit_s), 1)
        d["ratio"] = round(ratio, 3)
        d["level"] = self.level(now, warn_ratio)
        return d


class _SlotState:
    def __init__(self, zone: ParkingZone, rules: ParkingRules, dynamic_box: Box | None = None):
        self.zone = zone
        self.rules = rules
        self.dynamic_box = dynamic_box
        self.dwell = DwellTracker(rules.min_dwell_s, rules.lost_grace_s)
        self.session: ParkingSession | None = None
        self.last_vehicle_seen: float | None = None

    def step(self, t: float, obs: SlotObs) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        vtype = obs.vehicle_type or self.zone.type

        if self.session is None:
            self.dwell.update(t, obs.vehicle_ids)
            settled = self.dwell.settled()
            if settled:
                tid = min(settled, key=settled.get)  # type: ignore[arg-type]
                start = settled[tid]
                default_label = "Motor" if vtype == "motor" else "Mobil"
                label = obs.label or default_label
                self.session = ParkingSession(
                    id=f"P{next(_session_ids):04d}",
                    slot_id=self.zone.id,
                    vehicle_type=vtype,
                    track_id=tid,
                    label=label,
                    start=start,
                    limit_s=self.rules.limit_s_for(vtype, self.zone.limit_min),
                )
                self.last_vehicle_seen = t
                out.append({"type": "parking_start", "slot": self.zone.id, "t": start})
                out += self._check_alerts(t)
            return out

        s = self.session
        if obs.vehicle_ids:
            self.last_vehicle_seen = t
            s.track_id = obs.vehicle_ids[0]
            if obs.label:
                s.label = obs.label
        elif self.last_vehicle_seen is not None and t - self.last_vehicle_seen > self.rules.lost_grace_s:
            s.end = self.last_vehicle_seen
            self.dwell.tracks.clear()
            self.session = None
            self.last_vehicle_seen = None
            out.append({"type": "parking_end", "slot": self.zone.id, "session": s.to_dict(s.end, self.rules.warn_ratio)})
            return out

        out += self._check_alerts(t)
        return out

    def _check_alerts(self, t: float) -> list[dict[str, Any]]:
        s = self.session
        if s is None or s.limit_s <= 0:
            return []
        dur = s.duration_s(t)
        ratio = dur / s.limit_s
        kinds = {a["kind"] for a in s.alerts}
        out: list[dict[str, Any]] = []
        vname = "Motor" if s.vehicle_type == "motor" else "Mobil"
        lim_txt = _fmt_dur(s.limit_s)

        if ratio >= self.rules.warn_ratio and ratio <= 1.0 and "mendekati" not in kinds:
            msg = f"{vname} di slot {self.zone.id} sudah parkir {_fmt_dur(dur)}, mendekati batas {lim_txt}."
            out.append(self._emit_alert(s, "mendekati", "sedang", f"{vname} parkir mendekati batas", msg, t))
        if ratio > 1.0 and "lewat" not in kinds:
            over_txt = _fmt_dur(dur - s.limit_s)
            msg = f"{vname} di slot {self.zone.id} parkir {_fmt_dur(dur)} (+{over_txt} lewat batas {lim_txt})."
            out.append(self._emit_alert(s, "lewat", "tinggi", f"{vname} parkir terlalu lama", msg, t))
        return out

    def _emit_alert(self, s: ParkingSession, kind: str, severity: str, title: str, msg: str, t: float) -> dict[str, Any]:
        alert = {
            "id": f"PA-{next(_alert_ids):04d}",
            "kind": kind,
            "severity": severity,
            "title": title,
            "message": msg,
            "slot": self.zone.id,
            "vehicle_type": s.vehicle_type,
            "label": s.label,
            "t": t,
            "resolved": False,
        }
        s.alerts.append(alert)
        return {"type": "parking_alert", **alert}

    def snapshot(self, now: float) -> dict[str, Any]:
        s = self.session
        dur = s.duration_s(now) if s else 0.0
        vtype = s.vehicle_type if s else self.zone.type
        limit_s = s.limit_s if s else self.rules.limit_s_for(vtype, self.zone.limit_min)
        ratio = (dur / limit_s) if (s and limit_s > 0) else 0.0
        return {
            "id": self.zone.id,
            "type": self.zone.type,
            "zone": self.zone.zone,
            "box": list(self.dynamic_box) if self.dynamic_box is not None else None,
            "occupied": s is not None,
            "vehicle_type": vtype,
            "label": s.label if s else None,
            "track_id": s.track_id if s else None,
            "start": s.start if s else None,
            "duration_s": round(dur, 1),
            "duration_min": round(dur / 60, 1),
            "limit_s": round(limit_s, 1),
            "limit_min": round(limit_s / 60, 1),
            "over_s": round(max(0.0, dur - limit_s), 1) if s else 0.0,
            "ratio": round(ratio, 3),
            "level": s.level(now, self.rules.warn_ratio) if s else "kosong",
            "notified": s.notified if s else False,
            "session_id": s.id if s else None,
        }


@dataclass
class _AutoCandidate:
    anchor_box: Box
    group: str
    track_id: int
    first_seen: float
    last_seen: float


class ParkingFeature:
    name = "parking"

    def __init__(self, zones: list[ParkingZone], rules: ParkingRules):
        self.rules = rules
        self.configured_zones = list(zones)
        self.slots: dict[str, _SlotState] = {z.id: _SlotState(z, rules) for z in zones}
        self._candidates: list[_AutoCandidate] = []
        self.completed: deque[dict[str, Any]] = deque(maxlen=300)
        self.alerts: deque[dict[str, Any]] = deque(maxlen=200)
        self.now = 0.0

    @property
    def auto_mode(self) -> bool:
        return len(self.configured_zones) == 0

    def _next_auto_id(self, vtype: str) -> str:
        prefix = "C" if vtype == "mobil" else "M"
        i = 1
        while f"{prefix}-{i:02d}" in self.slots:
            i += 1
        return f"{prefix}-{i:02d}"

    def ensure_sim_slots(self) -> list[ParkingZone]:
        if self.slots:
            return list(self.configured_zones)
        zones = [
            *(ParkingZone(f"C-{i:02d}", "mobil", [[0, 0], [10, 0], [10, 10], [0, 10]]) for i in range(1, 9)),
            *(ParkingZone(f"M-{i:02d}", "motor", [[0, 0], [10, 0], [10, 10], [0, 10]]) for i in range(1, 13)),
        ]
        self.configured_zones = zones
        self.slots = {z.id: _SlotState(z, self.rules) for z in zones}
        return zones

    def step_detections(
        self, t: float, dets: list[Detection], frame_hw: tuple[int, int] | None = None
    ) -> list[dict[str, Any]]:
        vehicles = _dedup_vehicles([d for d in dets if d.group in ("car", "motorcycle")], frame_hw)
        if not self.auto_mode:
            obs = {sid: SlotObs() for sid in self.slots}
            for i, d in enumerate(vehicles):
                c = box_center(d.box)
                tid = d.track_id if d.track_id is not None else (10_000 + i)
                for sid, st in self.slots.items():
                    if not obs[sid].vehicle_ids and point_in_polygon(c, st.zone.zone):
                        obs[sid].vehicle_ids.append(tid)
                        obs[sid].vehicle_type = _group_to_type(d.group)
                        break
            return self.step(t, obs)
        return self._step_auto(t, vehicles)

    def _step_auto(self, t: float, vehicles: list[Detection]) -> list[dict[str, Any]]:
        obs = {sid: SlotObs() for sid in self.slots}
        # Pasangkan 1-ke-1 antara kendaraan dan slot dinamis aktif berdasarkan IoU tertinggi
        pairs: list[tuple[float, int, str]] = []
        for idx, d in enumerate(vehicles):
            for sid, st in self.slots.items():
                if st.dynamic_box is not None:
                    v = iou(d.box, st.dynamic_box)
                    if v >= 0.45:
                        pairs.append((v, idx, sid))
        pairs.sort(reverse=True)
        used_det: set[int] = set()
        used_slot: set[str] = set()
        for _, idx, sid in pairs:
            if idx in used_det or sid in used_slot:
                continue
            used_det.add(idx)
            used_slot.add(sid)
            d = vehicles[idx]
            tid = d.track_id if d.track_id is not None else (10_000 + idx)
            st = self.slots[sid]
            assert st.dynamic_box is not None
            # Haluskan kotak sedikit tanpa ikut terseret jika mobil mulai jalan keluar
            st.dynamic_box = tuple(0.9 * a + 0.1 * b for a, b in zip(st.dynamic_box, d.box))  # type: ignore[assignment]
            st.zone.zone = box_to_polygon(st.dynamic_box)
            obs[sid] = SlotObs([tid], _group_to_type(d.group))

        # Kendaraan yang belum punya slot: cek apakah benar-benar DIAM di anchor_box yang sama
        for idx, d in enumerate(vehicles):
            if idx in used_det:
                continue
            # Abaikan jika menumpuk dengan slot parkir yang sudah ada
            if any(st.dynamic_box is not None and iou(d.box, st.dynamic_box) >= 0.30 for st in self.slots.values()):
                continue
            tid = d.track_id if d.track_id is not None else (10_000 + idx)
            cand = next((c for c in self._candidates if iou(d.box, c.anchor_box) >= 0.55), None)
            if cand is None:
                self._candidates.append(_AutoCandidate(d.box, d.group, tid, t, t))
            else:
                cand.track_id = tid
                cand.last_seen = t
                if cand.last_seen - cand.first_seen >= self.rules.min_dwell_s:
                    vtype = _group_to_type(cand.group)
                    sid = self._next_auto_id(vtype)
                    z = ParkingZone(sid, vtype, box_to_polygon(d.box))
                    st = _SlotState(z, self.rules, dynamic_box=d.box)
                    st.dwell.tracks[tid] = [cand.first_seen, t]
                    self.slots[sid] = st
                    obs[sid] = SlotObs([tid], vtype)
                    self._candidates.remove(cand)

        # Kandidat yang bergerak pergi hilang cepat (maks 3 dtk) supaya jalan tetap bersih
        self._candidates = [c for c in self._candidates if t - c.last_seen <= min(3.0, self.rules.lost_grace_s)]
        events = self.step(t, obs)
        for sid in [k for k, st in self.slots.items() if st.dynamic_box is not None and st.session is None]:
            del self.slots[sid]
        return events

    def step(self, t: float, obs: dict[str, SlotObs]) -> list[dict[str, Any]]:
        self.now = t
        out: list[dict[str, Any]] = []
        for sid, st in self.slots.items():
            out += st.step(t, obs.get(sid) or SlotObs())
        for ev in out:
            if ev["type"] == "parking_end":
                self.completed.append(ev["session"])
                for a in self.alerts:
                    if a["slot"] == ev["slot"]:
                        a["resolved"] = True
            elif ev["type"] == "parking_alert":
                self.alerts.append(ev)
        return out

    def notify(self, slot_id: str) -> dict[str, Any] | None:
        st = self.slots.get(slot_id)
        if st is None or st.session is None:
            return None
        st.session.notified = True
        for a in self.alerts:
            if a["slot"] == slot_id and not a["resolved"]:
                a["resolved"] = True
        return st.snapshot(self.now)

    def resolve_alert(self, alert_id: str) -> bool:
        for a in self.alerts:
            if a["id"] == alert_id:
                a["resolved"] = True
                return True
        return False

    def snapshot(self) -> dict[str, Any]:
        now = self.now
        slots = [st.snapshot(now) for st in sorted(self.slots.values(), key=lambda x: x.zone.id)]
        cars = [s for s in slots if s["type"] == "mobil"]
        bikes = [s for s in slots if s["type"] == "motor"]
        near = [s for s in slots if s["level"] == "mendekati"]
        over = [s for s in slots if s["level"] == "lewat"]
        warnings = sorted(near + over, key=lambda s: s["ratio"], reverse=True)
        occ_durs = [s["duration_s"] for s in slots if s["occupied"]]
        return {
            "now": now,
            "mode": "auto" if self.auto_mode else "slots",
            "rules": asdict(self.rules),
            "slots": slots,
            "warnings": warnings,
            "completed": list(reversed(self.completed))[:50],
            "alerts": list(reversed(self.alerts))[:50],
            "stats": {
                "car_total": len(cars),
                "car_occupied": sum(1 for c in cars if c["occupied"]),
                "bike_total": len(bikes),
                "bike_occupied": sum(1 for b in bikes if b["occupied"]),
                "near_count": len(near),
                "over_count": len(over),
                "avg_duration_s": round(mean(occ_durs), 1) if occ_durs else None,
            },
        }
