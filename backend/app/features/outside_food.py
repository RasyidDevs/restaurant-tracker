"""Fitur: indikasi makanan & minuman dari luar di meja.

Input fitur ini hanya `OutsideObs` per meja (jenis objek + confidence), jadi
sumbernya bisa diganti tanpa mengubah aturan:
  - CV asli : grup YOLO berawalan "outside_" (lihat config.classes), dibagi ke
              meja lewat polygon zona -> observe_detections()
  - mock    : generator simulasi (features/outside_food_mock.py) -> observe()

Aturan anti false alarm per (meja, jenis objek):

  deteksi conf < conf_threshold          -> diabaikan
  terlihat >= min_persist_s DAN muncul di >= min_hit_ratio sampel
  dalam jendela min_persist_s terakhir   -> ALERT aktif
  tidak terlihat >= clear_after_s        -> alert selesai (objek hilang)
  alert ulang untuk meja+objek yang sama -> ditahan cooldown_s sejak alert terakhir selesai
  require_occupied                       -> kandidat baru hanya saat meja ada orangnya
  staf klik "sudah ditangani"            -> alert selesai, objek yang sama tidak di-alert
                                            lagi selama masih terlihat
"""

from __future__ import annotations

import itertools
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any

from ..core.detection import Detection
from ..core.geometry import box_center, point_in_polygon
from ..core.perception import Perception
from ..core.table_state import CoreEvent

GROUP_PREFIX = "outside_"

# Grup bawaan: nama tampilan + kategori. Grup outside_* lain dari config tetap
# dipakai (kategori ditebak dari nama, tampilan = nama grup).
KINDS: dict[str, dict[str, str]] = {
    "outside_bottle": {"label": "Botol minuman", "category": "minuman"},
    "outside_cup": {"label": "Cup minuman (takeaway)", "category": "minuman"},
    "outside_bag": {"label": "Kantong makanan", "category": "makanan"},
    "outside_box": {"label": "Kotak makanan", "category": "makanan"},
}


def kind_meta(kind: str) -> dict[str, str]:
    if kind in KINDS:
        return KINDS[kind]
    drink = any(w in kind for w in ("bottle", "cup", "drink"))
    return {"label": kind.removeprefix(GROUP_PREFIX).replace("_", " "), "category": "minuman" if drink else "makanan"}


@dataclass
class OutsideRules:
    conf_threshold: float = 0.45
    min_persist_s: float = 8.0
    min_hit_ratio: float = 0.6
    clear_after_s: float = 30.0
    cooldown_s: float = 300.0
    require_occupied: bool = True
    ignore_kinds: list[str] = field(default_factory=list)  # mis. botol air mineral yang dijual restoran

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "OutsideRules":
        d = d or {}
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class OutsideObs:
    """Satu objek terindikasi dari luar pada satu frame, sudah dibagi ke meja."""

    kind: str  # nama grup, mis. "outside_cup"
    conf: float


_ids = itertools.count(1)


@dataclass
class _Track:
    """Riwayat satu jenis objek di satu meja."""

    first_hit: float
    last_hit: float
    samples: deque = field(default_factory=deque)  # (t, conf | None)
    alert_id: str | None = None
    acknowledged: bool = False  # staf sudah menangani, jangan alert lagi selama masih terlihat


class OutsideFoodFeature:
    name = "outside_food"

    def __init__(self, perception: Perception, rules: OutsideRules, source: str = "cv"):
        self.rules = rules
        self.source = source  # "cv" | "mock"
        self.tables = perception.tables
        self.tracks: dict[tuple[str, str], _Track] = {}
        self.last_end: dict[tuple[str, str], float] = {}  # waktu alert terakhir selesai (untuk cooldown)
        self.alerts: dict[str, dict[str, Any]] = {}  # alert aktif
        self.history: deque[dict[str, Any]] = deque(maxlen=200)
        self._pending: dict[str, list[OutsideObs]] = {}

    # ------------------------------------------------------------- input
    def observe(self, obs: dict[str, list[OutsideObs]]) -> None:
        """Observasi untuk langkah berikutnya (dipanggil sebelum Perception.step)."""
        self._pending = obs

    def observe_detections(self, dets: list[Detection]) -> None:
        """Bagi deteksi YOLO grup outside_* ke meja berdasarkan polygon zona meja."""
        out: dict[str, list[OutsideObs]] = {}
        for d in dets:
            if not d.group.startswith(GROUP_PREFIX):
                continue
            c = box_center(d.box)
            for tid, ts in self.tables.items():
                if point_in_polygon(c, ts.zone.surface) or point_in_polygon(c, ts.zone.zone):
                    out.setdefault(tid, []).append(OutsideObs(d.group, d.conf))
                    break
        self._pending = out

    # -------------------------------------------------------------- aturan
    def on_step(self, t: float, perception: Perception, events: list[CoreEvent]) -> list[dict[str, Any]]:
        r = self.rules
        obs, self._pending = self._pending, {}
        out: list[dict[str, Any]] = []

        # confidence terbaik per (meja, jenis) di frame ini
        best: dict[tuple[str, str], float] = {}
        for tid, items in obs.items():
            if tid not in self.tables:
                continue
            for o in items:
                if o.conf < r.conf_threshold or o.kind in r.ignore_kinds:
                    continue
                key = (tid, o.kind)
                best[key] = max(best.get(key, 0.0), o.conf)

        for key, conf in best.items():
            if key not in self.tracks:
                if r.require_occupied and self.tables[key[0]].people == 0:
                    continue
                self.tracks[key] = _Track(first_hit=t, last_hit=t)
            self.tracks[key].last_hit = t

        for key in list(self.tracks):
            tr = self.tracks[key]
            tr.samples.append((t, best.get(key)))
            while tr.samples and t - tr.samples[0][0] > r.min_persist_s:
                tr.samples.popleft()

            if t - tr.last_hit >= r.clear_after_s:  # objek hilang
                if tr.alert_id:
                    out.append(self._end(tr.alert_id, t, "objek_hilang"))
                if tr.alert_id or tr.acknowledged:
                    self.last_end[key] = t
                del self.tracks[key]
                continue

            if tr.alert_id:
                self._refresh(tr, t)
            elif not tr.acknowledged and self._consistent(tr, t) and self._cooled(key, t):
                out.append(self._raise(key, tr, t))
        return out

    def _consistent(self, tr: _Track, t: float) -> bool:
        if t - tr.first_hit < self.rules.min_persist_s:
            return False
        hits = sum(1 for _, c in tr.samples if c is not None)
        return hits / max(1, len(tr.samples)) >= self.rules.min_hit_ratio

    def _cooled(self, key: tuple[str, str], t: float) -> bool:
        last = self.last_end.get(key)
        return last is None or t - last >= self.rules.cooldown_s

    def _raise(self, key: tuple[str, str], tr: _Track, t: float) -> dict[str, Any]:
        tid, kind = key
        meta = kind_meta(kind)
        confs = [c for _, c in tr.samples if c is not None]
        alert = {
            "id": f"OF{next(_ids):04d}",
            "type": "outside_food",
            "table": tid,
            "table_name": self.tables[tid].zone.name,
            "kind": kind,
            "label": meta["label"],
            "category": meta["category"],
            "confidence": round(sum(confs) / len(confs), 3),
            "max_confidence": round(max(confs), 3),
            "first_seen": tr.first_hit,
            "t": t,  # waktu alert dibuat
            "last_seen": tr.last_hit,
            "status": "active",
            "end_reason": None,
            "ended_at": None,
            "source": self.source,
        }
        tr.alert_id = alert["id"]
        self.alerts[alert["id"]] = alert
        return {**alert, "type": "alert", "feature": self.name}

    def _refresh(self, tr: _Track, t: float) -> None:
        a = self.alerts[tr.alert_id]  # type: ignore[index]
        a["last_seen"] = tr.last_hit
        confs = [c for _, c in tr.samples if c is not None]
        if confs:
            a["max_confidence"] = round(max(a["max_confidence"], max(confs)), 3)

    def _end(self, alert_id: str, t: float, reason: str) -> dict[str, Any]:
        a = self.alerts.pop(alert_id)
        a.update(status="resolved", end_reason=reason, ended_at=t)
        self.history.append(a)
        return {"type": "alert_end", "feature": self.name, "id": alert_id, "table": a["table"], "reason": reason, "t": t}

    def resolve(self, alert_id: str, now: float) -> dict[str, Any] | None:
        """Staf menandai alert sudah ditangani."""
        if alert_id not in self.alerts:
            return None
        for tr in self.tracks.values():
            if tr.alert_id == alert_id:
                tr.alert_id = None
                tr.acknowledged = True
        self._end(alert_id, now, "ditangani_staf")
        return self.history[-1]

    # ------------------------------------------------------------ snapshot
    def active(self) -> list[dict[str, Any]]:
        return sorted(self.alerts.values(), key=lambda a: a["t"], reverse=True)

    def snapshot(self, perception: Perception) -> dict[str, Any]:
        active = self.active()
        flagged = {a["table"] for a in active}
        history = list(reversed(self.history))
        by_kind: dict[str, int] = {}
        for a in active + history:
            by_kind[a["label"]] = by_kind.get(a["label"], 0) + 1
        return {
            "now": perception.now,
            "source": self.source,
            "rules": asdict(self.rules),
            "active": active,
            "history": history[:50],
            "tables": [
                {"id": tid, "name": ts.zone.name, "people": ts.people, "flagged": tid in flagged}
                for tid, ts in perception.tables.items()
            ],
            "stats": {
                "active_count": len(active),
                "total_count": len(active) + len(self.history),
                "handled_count": sum(1 for a in self.history if a["end_reason"] == "ditangani_staf"),
                "by_kind": [{"label": k, "jumlah": v} for k, v in sorted(by_kind.items(), key=lambda kv: -kv[1])],
            },
        }
