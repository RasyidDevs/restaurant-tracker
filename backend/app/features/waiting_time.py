"""Fitur: waiting time dari pelanggan duduk sampai pesanan lengkap tersaji.

Memakai status inti meja (core.TableState): jumlah orang, piring, gelas,
occupied_since, empty_since. Fitur ini hanya berisi aturan sesi:

  KOSONG ──(meja terisi)──────────────────────────────────────► MENUNGGU
           START = occupied_since, baseline = piring/gelas minimum sejak START
  MENUNGGU ──(piring_baru >= orang DAN gelas_baru >= orang)───► DISAJIKAN  SELESAI = item terakhir
  MENUNGGU ──(waiter klik "sudah lengkap")───────────────────► DISAJIKAN  SELESAI = item terakhir
  MENUNGGU ──(meja kosong >= empty_grace_s)──────────────────► KOSONG     sesi "pelanggan pergi"
  DISAJIKAN ──(meja kosong >= empty_grace_s)─────────────────► KOSONG
  DISAJIKAN ──(rombongan baru duduk di meja yang sudah dibereskan)► MENUNGGU  sesi baru

Item dihitung per kenaikan jumlah (bukan puncak), jadi item yang diangkat tidak
menghalangi item berikutnya terhitung.

Alert dicek terus selama MENUNGGU:
  belum ada item setelah alert_no_item_min, item belum lengkap setelah alert_partial_min.
"""

from __future__ import annotations

import itertools
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from statistics import mean, median
from typing import Any

from ..core.perception import Perception
from ..core.table_state import CoreEvent, TableState


@dataclass
class WaitingRules:
    empty_grace_s: float = 120.0
    require_drinks: bool = True
    alert_no_item_min: float = 20.0
    alert_partial_min: float = 25.0
    target_min: float = 20.0
    new_group_gap_s: float = 30.0  # meja kosong minimal selama ini sebelum rombongan baru dihitung
    item_reappear_s: float = 60.0  # item hilang lalu muncul lagi dalam waktu ini = item yang sama

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "WaitingRules":
        d = d or {}
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


_ids = itertools.count(1)


def _fmt_elapsed(minutes: float) -> str:
    return f"{minutes * 60:.0f} detik" if minutes < 2 else f"{minutes:.0f} menit"


@dataclass
class Session:
    id: str
    table_id: str
    start: float
    baseline_plates: int
    baseline_glasses: int
    people_peak: int = 0
    plates_served: int = 0
    glasses_served: int = 0
    first_drink_at: float | None = None
    first_food_at: float | None = None
    last_item_at: float | None = None
    end: float | None = None
    status: str = "menunggu"  # menunggu | sebagian | lengkap | pergi
    end_reason: str | None = None  # otomatis | konfirmasi_waiter | pelanggan_pergi
    alerts: list[dict[str, Any]] = field(default_factory=list)
    items: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self, now: float, rules: WaitingRules) -> dict[str, Any]:
        d = asdict(self)
        d["waiting_s"] = round((self.end if self.end is not None else now) - self.start, 1)
        d["first_drink_s"] = round(self.first_drink_at - self.start, 1) if self.first_drink_at else None
        d["first_food_s"] = round(self.first_food_at - self.start, 1) if self.first_food_at else None
        d["target_s"] = rules.target_min * 60
        d["required_glasses"] = self.people_peak if rules.require_drinks else 0
        return d


class _TableWaiting:
    """Aturan sesi untuk satu meja."""

    def __init__(self, table: TableState, rules: WaitingRules):
        self.table = table
        self.rules = rules
        self.phase = "kosong"  # kosong | menunggu | disajikan
        self.session: Session | None = None
        self._missing: dict[str, list[float]] = {"plates": [], "glasses": []}  # waktu item hilang
        self._emptied_at: float | None = None
        self._items_at_empty = 0

    @property
    def name(self) -> str:
        return self.table.zone.name

    def step(self, t: float, events: list[CoreEvent]) -> list[dict[str, Any]]:
        tb = self.table
        out: list[dict[str, Any]] = []
        for e in events:
            if e.table == tb.id and e.type == "emptied":
                self._emptied_at = e.t
                self._items_at_empty = tb.plates + tb.glasses

        if self.phase == "kosong":
            if tb.people > 0:
                out += self._start_session(t)

        elif self.phase == "menunggu":
            s = self.session
            assert s is not None
            s.people_peak = max(s.people_peak, tb.people)
            out += self._track_items(t, events)
            out += self._check_complete()
            if self.phase == "menunggu":
                out += self._check_alerts(t)
                out += self._check_left(t)

        elif self.phase == "disajikan":
            if self._new_group_seated(events):
                out += self._start_session(t)  # sesi lama sudah tercatat selesai
            else:
                out += self._check_left(t)
        return out

    def _start_session(self, t: float) -> list[dict[str, Any]]:
        tb = self.table
        start = tb.occupied_since if tb.occupied_since is not None else t
        bp, bg = tb.min_items_since(start)
        self.session = Session(
            id=f"S{next(_ids):04d}",
            table_id=tb.id,
            start=start,
            baseline_plates=bp,
            baseline_glasses=bg,
            people_peak=tb.people,
        )
        self._missing = {"plates": [], "glasses": []}
        self.phase = "menunggu"
        out: list[dict[str, Any]] = [{"type": "session_start", "table": tb.id, "t": start}]
        # Item yang sudah datang antara START dan sesi dibuat (jarang) langsung dihitung.
        for kind, current, base in (("plates", tb.plates, bp), ("glasses", tb.glasses, bg)):
            if current > base:
                out.append(self._add_items(kind, current - base, t))
        return out

    def _new_group_seated(self, events: list[CoreEvent]) -> bool:
        """Rombongan baru duduk sebelum empty_grace_s habis: meja sempat kosong cukup lama
        dan sudah dibereskan (piring/gelas berkurang). Rombongan lama yang kembali dari
        toilet tidak memicu sesi baru karena piring mereka masih di meja."""
        tb = self.table
        occ = next((e for e in events if e.table == tb.id and e.type == "occupied"), None)
        if occ is None or self._emptied_at is None:
            return False
        items = tb.plates + tb.glasses
        cleared = items == 0 or items < self._items_at_empty
        return occ.t - self._emptied_at >= self.rules.new_group_gap_s and cleared

    def _track_items(self, t: float, events: list[CoreEvent]) -> list[dict[str, Any]]:
        """Hitung setiap kenaikan jumlah piring/gelas sebagai item baru.

        Item yang hilang lalu muncul lagi dalam item_reappear_s dianggap item yang sama
        (tertutup tangan/orang), bukan item baru. Item yang sudah diangkat lebih lama dari
        itu tidak menghalangi item baru terhitung (mis. gelas 1 diangkat, gelas 2 datang).
        """
        tb = self.table
        out = []
        for e in events:
            if e.table != tb.id or e.type not in ("plates", "glasses"):
                continue
            missing = self._missing[e.type]
            if e.new < e.old:
                missing.extend([e.t] * (e.old - e.new))
            elif e.new > e.old:
                missing[:] = [m for m in missing if e.t - m <= self.rules.item_reappear_s]
                back = min(e.new - e.old, len(missing))
                del missing[len(missing) - back :]
                if e.new - e.old > back:
                    out.append(self._add_items(e.type, e.new - e.old - back, e.t))
        return out

    def _add_items(self, kind: str, n: int, at: float) -> dict[str, Any]:
        s = self.session
        assert s is not None
        label = "piring" if kind == "plates" else "gelas"
        served_attr = "plates_served" if kind == "plates" else "glasses_served"
        first_attr = "first_food_at" if kind == "plates" else "first_drink_at"
        served = getattr(s, served_attr)
        for k in range(served + 1, served + n + 1):
            s.items.append({"kind": label, "n": k, "t": at})
        setattr(s, served_attr, served + n)
        if getattr(s, first_attr) is None:
            setattr(s, first_attr, at)
        s.last_item_at = max(s.last_item_at or at, at)
        if s.status == "menunggu":
            s.status = "sebagian"
        return {"type": "item", "table": self.table.id, "kind": label, "count": served + n, "t": at}

    def _check_complete(self) -> list[dict[str, Any]]:
        s = self.session
        assert s is not None
        if s.people_peak <= 0 or s.last_item_at is None:
            return []
        food_ok = s.plates_served >= s.people_peak
        drink_ok = (not self.rules.require_drinks) or s.glasses_served >= s.people_peak
        return [self.finish(s.last_item_at, "otomatis")] if food_ok and drink_ok else []

    def _check_alerts(self, t: float) -> list[dict[str, Any]]:
        s = self.session
        assert s is not None
        elapsed_min = (t - s.start) / 60
        kinds = {a["kind"] for a in s.alerts}
        out = []
        if not s.items and elapsed_min >= self.rules.alert_no_item_min and "belum_disajikan" not in kinds:
            msg = f"{self.name}: belum ada yang disajikan ({_fmt_elapsed(elapsed_min)})"
            out.append(self._alert(s, "belum_disajikan", t, msg))
        if s.items and elapsed_min >= self.rules.alert_partial_min and "belum_lengkap" not in kinds:
            need_g = s.people_peak if self.rules.require_drinks else 0
            msg = (
                f"{self.name}: baru {s.plates_served}/{s.people_peak} piring, "
                f"{s.glasses_served}/{need_g} gelas ({_fmt_elapsed(elapsed_min)})"
            )
            out.append(self._alert(s, "belum_lengkap", t, msg))
        return out

    def _alert(self, s: Session, kind: str, t: float, msg: str) -> dict[str, Any]:
        alert = {"kind": kind, "t": t, "message": msg}
        s.alerts.append(alert)
        return {"type": "alert", "table": self.table.id, **alert}

    def _check_left(self, t: float) -> list[dict[str, Any]]:
        tb = self.table
        if tb.people > 0 or tb.empty_since is None or t - tb.empty_since < self.rules.empty_grace_s:
            return []
        out = []
        if self.phase == "menunggu":
            s = self.session
            assert s is not None
            end = s.last_item_at if s.last_item_at is not None else tb.empty_since
            out.append(self.finish(end, "pelanggan_pergi", status="pergi"))
        self.phase = "kosong"
        self.session = None
        return out

    def finish(self, end: float, reason: str, status: str = "lengkap") -> dict[str, Any]:
        s = self.session
        assert s is not None
        s.end, s.end_reason, s.status = end, reason, status
        if status == "lengkap":
            self.phase = "disajikan"
        return {"type": "session_end", "table": self.table.id, "session": s.to_dict(end, self.rules)}


class WaitingTimeFeature:
    name = "waiting_time"

    def __init__(self, perception: Perception, rules: WaitingRules):
        self.rules = rules
        self.per_table = {tid: _TableWaiting(ts, rules) for tid, ts in perception.tables.items()}
        self.completed: deque[dict[str, Any]] = deque(maxlen=500)
        self.alerts: deque[dict[str, Any]] = deque(maxlen=200)

    def on_step(self, t: float, perception: Perception, events: list[CoreEvent]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for tw in self.per_table.values():
            out += tw.step(t, events)
        for ev in out:
            self._record(ev)
        return out

    def _record(self, ev: dict[str, Any]) -> None:
        if ev["type"] == "session_end":
            self.completed.append(ev["session"])
        elif ev["type"] == "alert":
            self.alerts.append(ev)

    def confirm(self, session_id: str, now: float) -> dict[str, Any] | None:
        """Waiter menandai pesanan lengkap. Waktu selesai = item terakhir tiba (bukan waktu klik)."""
        for tw in self.per_table.values():
            if tw.phase == "menunggu" and tw.session and tw.session.id == session_id:
                end = tw.session.last_item_at if tw.session.last_item_at is not None else now
                ev = tw.finish(end, "konfirmasi_waiter")
                self._record(ev)
                return ev["session"]
        return None

    def phase_of(self, table_id: str) -> str:
        return self.per_table[table_id].phase

    def snapshot(self, perception: Perception) -> dict[str, Any]:
        now = perception.now
        tables = []
        for tid, ts in perception.tables.items():
            tw = self.per_table[tid]
            core = ts.snapshot()
            tables.append(
                {
                    **core,
                    "phase": tw.phase,
                    "session": tw.session.to_dict(now, self.rules) if tw.session else None,
                }
            )
        completed = list(self.completed)
        return {
            "now": now,
            "rules": asdict(self.rules),
            "tables": tables,
            "active": [t["session"] for t in tables if t["session"] and t["phase"] == "menunggu"],
            "completed": list(reversed(completed))[:50],
            "alerts": list(reversed(self.alerts))[:30],
            "stats": self._stats(completed),
        }

    def _stats(self, completed: list[dict[str, Any]]) -> dict[str, Any]:
        done = [s for s in completed if s["status"] == "lengkap"]
        waits = [s["waiting_s"] for s in done]
        drinks = [s["first_drink_s"] for s in done if s["first_drink_s"] is not None]
        foods = [s["first_food_s"] for s in done if s["first_food_s"] is not None]
        target = self.rules.target_min * 60
        by_hour: dict[int, list[float]] = {}
        for s in done:
            by_hour.setdefault(time.localtime(s["start"]).tm_hour, []).append(s["waiting_s"])
        r = lambda v: round(v, 1)  # noqa: E731
        return {
            "count": len(done),
            "left_count": sum(1 for s in completed if s["status"] == "pergi"),
            "avg_wait_s": r(mean(waits)) if waits else None,
            "median_wait_s": r(median(waits)) if waits else None,
            "max_wait_s": r(max(waits)) if waits else None,
            "avg_first_drink_s": r(mean(drinks)) if drinks else None,
            "avg_first_food_s": r(mean(foods)) if foods else None,
            "on_target_pct": round(100 * sum(w <= target for w in waits) / len(waits)) if waits else None,
            "by_hour": [
                {"jam": f"{h:02d}:00", "rata_menit": r(mean(v) / 60), "jumlah": len(v)}
                for h, v in sorted(by_hour.items())
            ],
        }
