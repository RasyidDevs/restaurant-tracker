"""Fitur: jumlah orang per meja, lama duduk, dan estimasi kapan meja kosong.

Memakai status inti meja (core.TableState): people, plates, occupied_since,
empty_since, seat_flags. Fitur ini tidak menghitung ulang orang/piring.

Kunjungan (visit) per meja:
  KOSONG ──(core: occupied)──► DUDUK   START = orang pertama terlihat
  DUDUK  ──(core: emptied)───► KOSONG  SELESAI = orang terakhir terlihat -> masuk riwayat

Fase makan selama DUDUK (dari jumlah piring baru di atas baseline):
  menunggu_makanan  belum ada piring baru
  makan             piring baru sudah datang
  selesai_makan     piring diangkat (piring baru turun ke <= separuh puncak)

Estimasi sisa waktu sampai meja kosong:
  menunggu_makanan  sisa(waktu tunggu makanan) + durasi setelah makanan datang
  makan             durasi setelah makanan datang - sudah berapa lama makan
  selesai_makan     after_meal_min - sudah berapa lama piring diangkat
Durasi "setelah makanan datang" dan "tunggu makanan" dipelajari dari median
riwayat kunjungan (minimal learn_min_visits), sebelum itu pakai default.
"""

from __future__ import annotations

import itertools
from collections import deque
from dataclasses import asdict, dataclass, field
from statistics import mean, median
from typing import Any

from ..core.perception import Perception
from ..core.table_state import CoreEvent, TableState


@dataclass
class OccupancyRules:
    default_food_wait_min: float = 15.0  # default lama menunggu makanan pertama
    default_post_food_min: float = 35.0  # default lama duduk setelah makanan datang (makan + santai)
    after_meal_min: float = 10.0  # perkiraan sisa duduk setelah piring diangkat
    soon_free_min: float = 10.0  # estimasi <= ini -> status "segera kosong"
    min_visit_s: float = 60.0  # kunjungan lebih pendek dari ini tidak masuk statistik
    learn_min_visits: int = 3  # jumlah kunjungan sebelum memakai angka hasil belajar

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "OccupancyRules":
        d = d or {}
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# Rentang distribusi lama duduk (menit): (label, batas bawah, batas atas)
DWELL_BUCKETS = [
    ("<15m", 0, 15),
    ("15-30m", 15, 30),
    ("30-45m", 30, 45),
    ("45-60m", 45, 60),
    ("60-90m", 60, 90),
    (">90m", 90, float("inf")),
]

_ids = itertools.count(1)


@dataclass
class Visit:
    id: str
    table_id: str
    start: float
    baseline_plates: int
    people_peak: int = 0
    plates_peak: int = 0  # puncak piring baru di atas baseline
    first_food_at: float | None = None
    cleared_at: float | None = None
    end: float | None = None
    people_log: list[dict[str, Any]] = field(default_factory=list)

    @property
    def phase(self) -> str:
        if self.cleared_at is not None:
            return "selesai_makan"
        if self.first_food_at is not None:
            return "makan"
        return "menunggu_makanan"

    def duration_s(self, now: float) -> float:
        return (self.end if self.end is not None else now) - self.start

    def to_dict(self, now: float) -> dict[str, Any]:
        d = asdict(self)
        d["phase"] = self.phase
        d["duration_s"] = round(self.duration_s(now), 1)
        d["food_wait_s"] = round(self.first_food_at - self.start, 1) if self.first_food_at is not None else None
        d["post_food_s"] = (
            round(self.end - self.first_food_at, 1) if self.end is not None and self.first_food_at is not None else None
        )
        return d


class _TableOccupancy:
    def __init__(self, table: TableState, rules: OccupancyRules):
        self.table = table
        self.rules = rules
        self.visit: Visit | None = None

    def step(self, t: float, events: list[CoreEvent]) -> list[dict[str, Any]]:
        tb = self.table
        out: list[dict[str, Any]] = []
        mine = [e for e in events if e.table == tb.id]

        if self.visit is None and tb.people > 0:
            start = tb.occupied_since if tb.occupied_since is not None else t
            base_plates, _ = tb.min_items_since(start)
            self.visit = Visit(id=f"V{next(_ids):04d}", table_id=tb.id, start=start, baseline_plates=base_plates)
            out.append({"type": "visit_start", "table": tb.id, "t": start})

        v = self.visit
        if v is None:
            return out

        for e in mine:
            if e.type == "people":
                v.people_log.append({"t": e.t, "people": e.new})

        if tb.people > 0:
            v.people_peak = max(v.people_peak, tb.people)
            self._track_plates(t, v, mine)
            return out

        # Meja kosong (core sudah memastikan lewat lost_grace + penghalus) -> kunjungan selesai.
        v.end = tb.empty_since if tb.empty_since is not None else t
        self.visit = None
        out.append({"type": "visit_end", "table": tb.id, "visit": v.to_dict(v.end)})
        return out

    def _track_plates(self, t: float, v: Visit, events: list[CoreEvent]) -> None:
        tb = self.table
        at = next((e.t for e in events if e.type == "plates"), t)
        v.baseline_plates = min(v.baseline_plates, tb.plates)  # piring sisa tamu lalu diangkat
        new = tb.plates - v.baseline_plates
        if new > v.plates_peak:
            v.plates_peak = new
            if v.first_food_at is None:
                v.first_food_at = at
            v.cleared_at = None  # ada piring baru lagi (tambah pesanan)
        elif v.plates_peak > 0 and new <= v.plates_peak // 2:
            if v.cleared_at is None:
                v.cleared_at = at
        elif v.cleared_at is not None:
            v.cleared_at = None  # piring terlihat lagi (tadi tertutup), belum benar-benar diangkat

    # ------------------------------------------------------------ estimasi
    def estimate(self, now: float, learned: dict[str, Any]) -> dict[str, Any] | None:
        v = self.visit
        if v is None or self.table.people == 0:
            return None
        r = self.rules
        food_wait = learned["food_wait_s"] or r.default_food_wait_min * 60
        post_food = learned["post_food_s"] or r.default_post_food_min * 60
        is_learned = learned["post_food_s"] is not None
        elapsed = now - v.start

        if v.phase == "menunggu_makanan":
            remaining = max(food_wait - elapsed, 120) + post_food
            conf = 35
            reason = "Belum ada makanan tersaji"
        elif v.phase == "makan":
            assert v.first_food_at is not None
            eating = now - v.first_food_at
            remaining = post_food - eating
            conf = 55
            reason = f"Makanan datang {eating / 60:.0f} menit lalu"
        else:
            assert v.cleared_at is not None
            since = now - v.cleared_at
            remaining = r.after_meal_min * 60 - since
            conf = 80
            reason = f"Piring diangkat {since / 60:.0f} menit lalu"

        if self.table.people < v.people_peak:
            remaining *= 0.7  # sebagian rombongan sudah pergi
            conf += 5
            reason += f", {v.people_peak - self.table.people} orang sudah pergi"
        if is_learned:
            conf += 10

        overdue = -remaining
        if overdue > 0:  # sudah lewat perkiraan: makin lama makin tidak pasti
            conf -= min(30, overdue / 60)
            reason += f", lewat perkiraan {overdue / 60:.0f} menit"
        remaining = max(remaining, 60)

        est_min = round(remaining / 60)
        return {
            "est_free_s": round(remaining),
            "est_free_min": est_min,
            "est_free_at": round(now + remaining),
            "confidence": int(max(10, min(95, conf))),
            "soon_free": est_min <= r.soon_free_min,
            "reason": reason,
        }


class TableOccupancyFeature:
    name = "table_occupancy"

    def __init__(self, perception: Perception, rules: OccupancyRules):
        self.rules = rules
        self.per_table = {tid: _TableOccupancy(ts, rules) for tid, ts in perception.tables.items()}
        self.visits: deque[dict[str, Any]] = deque(maxlen=1000)

    def on_step(self, t: float, perception: Perception, events: list[CoreEvent]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for to in self.per_table.values():
            out += to.step(t, events)
        for ev in out:
            if ev["type"] == "visit_end" and ev["visit"]["duration_s"] >= self.rules.min_visit_s:
                self.visits.append(ev["visit"])
        return out

    def learned(self) -> dict[str, Any]:
        """Median durasi dari riwayat kunjungan (None kalau datanya belum cukup)."""
        need = self.rules.learn_min_visits
        waits = [v["food_wait_s"] for v in self.visits if v["food_wait_s"] is not None]
        posts = [v["post_food_s"] for v in self.visits if v["post_food_s"] is not None]
        return {
            "food_wait_s": round(median(waits), 1) if len(waits) >= need else None,
            "post_food_s": round(median(posts), 1) if len(posts) >= need else None,
            "samples": len(posts),
        }

    def estimate(self, table_id: str, now: float) -> dict[str, Any] | None:
        return self.per_table[table_id].estimate(now, self.learned())

    def snapshot(self, perception: Perception) -> dict[str, Any]:
        now = perception.now
        learned = self.learned()
        tables = []
        for tid, ts in perception.tables.items():
            to = self.per_table[tid]
            core = ts.snapshot()
            est = to.estimate(now, learned)
            if ts.people > 0:
                status = "segera_kosong" if est and est["soon_free"] else "terisi"
            else:
                status = "perlu_dibersihkan" if ts.plates + ts.glasses > 0 else "kosong"
            tables.append(
                {
                    **core,
                    "status": status,
                    "seats_free": max(ts.zone.seats - ts.people, 0),
                    "visit": to.visit.to_dict(now) if to.visit else None,
                    "estimate": est,
                }
            )

        seats = sum(t["seats"] for t in tables)
        people = sum(t["people"] for t in tables)
        occupied = sum(1 for t in tables if t["people"] > 0)
        visits = list(self.visits)
        soon = sorted(
            (t for t in tables if t["estimate"]), key=lambda t: t["estimate"]["est_free_s"]
        )
        return {
            "now": now,
            "rules": asdict(self.rules),
            "tables": tables,
            "summary": {
                "people": people,
                "seats": seats,
                "seat_util_pct": round(100 * people / seats) if seats else 0,
                "tables_total": len(tables),
                "tables_occupied": occupied,
                "tables_free": len(tables) - occupied,
                "soon_free": sum(1 for t in tables if t["status"] == "segera_kosong"),
            },
            "soon_free": [
                {"id": t["id"], "name": t["name"], **t["estimate"]} for t in soon
            ],
            "learned": learned,
            "visits": list(reversed(visits))[:50],
            "stats": self._stats(visits),
        }

    def _stats(self, visits: list[dict[str, Any]]) -> dict[str, Any]:
        durs = [v["duration_s"] for v in visits]
        by_size: dict[int, list[float]] = {}
        for v in visits:
            by_size.setdefault(v["people_peak"], []).append(v["duration_s"])
        r = lambda x: round(x, 1)  # noqa: E731
        return {
            "count": len(visits),
            "avg_dwell_s": r(mean(durs)) if durs else None,
            "median_dwell_s": r(median(durs)) if durs else None,
            "max_dwell_s": r(max(durs)) if durs else None,
            "avg_group_size": r(mean(v["people_peak"] for v in visits)) if visits else None,
            "distribution": [
                {"rentang": label, "meja": sum(1 for d in durs if lo <= d / 60 < hi)}
                for label, lo, hi in DWELL_BUCKETS
            ],
            "by_group_size": [
                {"orang": n, "rata_menit": r(mean(v) / 60), "jumlah": len(v)} for n, v in sorted(by_size.items())
            ],
        }
