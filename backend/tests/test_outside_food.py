"""Tes fitur indikasi makanan/minuman dari luar di atas Perception (core)."""

import random

import pytest

from app.core.detection import Detection
from app.core.perception import Perception
from app.core.table_state import CoreRules
from app.core.zones import TableObs
from app.features.outside_food import OutsideFoodFeature, OutsideObs, OutsideRules

from .helpers import FPS, ZONE

FAST_CORE = CoreRules(seated_min_s=2, lost_grace_s=5, count_window_s=1, count_hold_s=1)


class OSim:
    def __init__(self, rules: OutsideRules | None = None):
        self.p = Perception([ZONE], FAST_CORE)
        self.f = OutsideFoodFeature(self.p, rules or OutsideRules(), source="mock")
        self.p.add_feature(self.f)
        self.t = 0.0
        self.events: list[dict] = []

    def run(self, until: float, people: int, items=None, flicker: float = 0.0, rng=None):
        """items: list[(kind, conf)] yang terlihat tiap frame (bisa berkedip)."""
        rng = rng or random.Random(0)
        while self.t < until:
            seen = [OutsideObs(k, c) for k, c in (items or []) if rng.random() >= flicker]
            self.f.observe({"T1": seen})
            obs = TableObs(list(range(1, people + 1)), 0, 0, [i < people for i in range(4)])
            self.events += self.p.step(self.t, {"T1": obs})
            self.t = round(self.t + 1 / FPS, 3)

    def raised(self):
        return [e for e in self.events if e["type"] == "alert"]

    def ended(self):
        return [e for e in self.events if e["type"] == "alert_end"]


def seated(rules=None) -> OSim:
    s = OSim(rules)
    s.run(10, people=2)  # pelanggan duduk & menetap dulu
    assert s.p.tables["T1"].people == 2
    return s


def test_alert_after_consistent_detection():
    s = seated()
    s.run(30, 2, [("outside_cup", 0.7)])
    (a,) = s.raised()
    assert (a["table"], a["table_name"], a["kind"], a["category"]) == ("T1", "Meja 1", "outside_cup", "minuman")
    assert a["confidence"] == pytest.approx(0.7)
    assert a["source"] == "mock"
    assert a["t"] - a["first_seen"] == pytest.approx(8, abs=0.3)  # min_persist_s


def test_short_glimpse_is_not_alerted():
    s = seated()
    s.run(14, 2, [("outside_bottle", 0.8)])  # cuma 4 detik
    s.run(60, 2)
    assert s.raised() == []


def test_low_confidence_ignored():
    s = seated(OutsideRules(conf_threshold=0.5))
    s.run(60, 2, [("outside_bag", 0.4)])
    assert s.raised() == []
    assert s.f.tracks == {}


def test_flicker_is_tolerated_but_sparse_hits_are_not():
    s = seated()
    s.run(40, 2, [("outside_cup", 0.6)], flicker=0.25, rng=random.Random(1))  # ~75% frame
    assert len(s.raised()) == 1

    s2 = seated()
    s2.run(60, 2, [("outside_cup", 0.6)], flicker=0.7, rng=random.Random(2))  # ~30% frame
    assert s2.raised() == []


def test_alert_clears_when_object_gone_and_cooldown_blocks_repeat():
    s = seated(OutsideRules(clear_after_s=10, cooldown_s=120))
    s.run(30, 2, [("outside_cup", 0.7)])
    s.run(45, 2)  # hilang 15 detik
    (end,) = s.ended()
    assert end["reason"] == "objek_hilang"
    assert s.f.active() == []

    s.run(80, 2, [("outside_cup", 0.7)])  # muncul lagi dalam masa cooldown
    assert len(s.raised()) == 1
    s.run(200, 2, [("outside_cup", 0.7)])  # cooldown habis (selesai di ~40 + 120)
    assert len(s.raised()) == 2


def test_empty_table_is_ignored_when_required():
    s = OSim()
    s.run(60, 0, [("outside_box", 0.9)])
    assert s.raised() == []

    s2 = OSim(OutsideRules(require_occupied=False))
    s2.run(60, 0, [("outside_box", 0.9)])
    assert len(s2.raised()) == 1


def test_ignored_kind_and_multiple_kinds_per_table():
    s = seated(OutsideRules(ignore_kinds=["outside_bottle"]))
    s.run(30, 2, [("outside_bottle", 0.9), ("outside_bag", 0.6), ("outside_cup", 0.8)])
    assert sorted(a["kind"] for a in s.raised()) == ["outside_bag", "outside_cup"]


def test_staff_resolve_suppresses_until_object_leaves():
    s = seated(OutsideRules(clear_after_s=10, cooldown_s=0))
    s.run(30, 2, [("outside_cup", 0.7)])
    (a,) = s.raised()
    done = s.f.resolve(a["id"], s.t)
    assert done["end_reason"] == "ditangani_staf"
    s.run(90, 2, [("outside_cup", 0.7)])  # masih terlihat -> tidak di-alert lagi
    assert len(s.raised()) == 1
    assert s.f.resolve("OF9999", s.t) is None
    snap = s.f.snapshot(s.p)
    assert snap["stats"]["handled_count"] == 1 and snap["active"] == []


def test_real_detections_are_assigned_to_table_zone():
    s = seated()
    while s.t < 30:
        s.f.observe_detections(
            [
                Detection("outside_cup", (40, 40, 50, 55), 0.8),  # di permukaan meja
                Detection("outside_bag", (300, 300, 320, 320), 0.9),  # di luar semua meja
                Detection("glass", (60, 60, 66, 70), 0.9),  # gelas restoran, bukan outside
            ]
        )
        obs = TableObs([1, 2], 0, 0, [True, True, False, False])
        s.events += s.p.step(s.t, {"T1": obs})
        s.t = round(s.t + 1 / FPS, 3)
    assert [a["kind"] for a in s.raised()] == ["outside_cup"]
    assert s.f.snapshot(s.p)["tables"][0]["flagged"] is True
