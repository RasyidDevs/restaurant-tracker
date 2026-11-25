"""Tes fitur okupansi meja: jumlah orang, lama duduk, estimasi kosong."""

import pytest

from app.core.perception import Perception
from app.core.table_state import CoreRules
from app.core.zones import TableObs
from app.features.table_occupancy import OccupancyRules, TableOccupancyFeature

from .helpers import FPS, ZONE


class OccSim:
    def __init__(self, rules: OccupancyRules | None = None):
        self.p = Perception([ZONE], CoreRules())
        self.f = TableOccupancyFeature(self.p, rules or OccupancyRules())
        self.p.add_feature(self.f)
        self.t = 0.0
        self.events: list[dict] = []

    def run(self, until: float, ids: list[int], plates: int = 0, glasses: int = 0):
        while self.t < until:
            obs = TableObs(list(ids), plates, glasses, [i < len(ids) for i in range(4)])
            self.events += self.p.step(self.t, {"T1": obs})
            self.t = round(self.t + 1 / FPS, 3)

    def table(self):
        return self.f.snapshot(self.p)["tables"][0]

    def ended(self):
        return [e["visit"] for e in self.events if e["type"] == "visit_end"]


def meal(s: OccSim, t0: float, people: list[int], food_at: float, cleared_at: float, leave_at: float, gone: float):
    """Satu kunjungan lengkap mulai t0 (detik relatif)."""
    n = len(people)
    s.run(t0 + food_at, people, 0, n)
    s.run(t0 + cleared_at, people, n, n)
    s.run(t0 + leave_at, people, 0, n)
    s.run(t0 + gone, [], 0, 0)


def test_people_count_and_seats():
    s = OccSim()
    s.run(60, [1, 2, 3])
    t = s.table()
    assert t["people"] == 3
    assert t["seats_free"] == 1
    assert t["status"] in ("terisi", "segera_kosong")
    summary = s.f.snapshot(s.p)["summary"]
    assert (summary["people"], summary["seats"], summary["seat_util_pct"]) == (3, 4, 75)
    assert summary["tables_occupied"] == 1


def test_waiter_passing_is_not_a_visit():
    s = OccSim()
    s.run(10, [99])
    s.run(120, [])
    assert s.table()["people"] == 0
    assert s.table()["visit"] is None
    assert not [e for e in s.events if e["type"] == "visit_start"]


def test_dwell_measured_from_first_seen_to_last_seen():
    s = OccSim()
    s.run(5, [])
    s.run(40 * 60, [1, 2])  # duduk detik 5 sampai menit 40
    assert s.table()["occupied_s"] == pytest.approx(40 * 60 - 5, abs=1)
    s.run(40 * 60 + 120, [])
    (v,) = s.ended()
    assert v["duration_s"] == pytest.approx(40 * 60 - 5, abs=1)
    assert v["people_peak"] == 2
    stats = s.f.snapshot(s.p)["stats"]
    assert stats["count"] == 1
    assert {d["rentang"]: d["meja"] for d in stats["distribution"]}["30-45m"] == 1


def test_phases_and_estimate_shrink():
    s = OccSim()
    s.run(5 * 60, [1, 2], 0, 0)
    e0 = s.table()["estimate"]
    assert s.table()["visit"]["phase"] == "menunggu_makanan"
    # default: tunggu 15m + 35m setelah makanan -> sisa ~45m pada menit 5
    assert e0["est_free_min"] == pytest.approx(45, abs=1)

    s.run(25 * 60, [1, 2], 2, 2)  # makanan datang menit 5, sudah makan 20m
    e1 = s.table()["estimate"]
    assert s.table()["visit"]["phase"] == "makan"
    assert e1["est_free_min"] == pytest.approx(15, abs=1)
    assert e1["confidence"] > e0["confidence"]

    s.run(28 * 60, [1, 2], 0, 2)  # piring diangkat menit 25
    e2 = s.table()["estimate"]
    assert s.table()["visit"]["phase"] == "selesai_makan"
    assert e2["est_free_min"] == pytest.approx(7, abs=1)
    assert e2["soon_free"] and s.table()["status"] == "segera_kosong"
    assert e2["confidence"] > e1["confidence"]


def test_leftover_plates_do_not_count_as_food():
    s = OccSim()
    s.run(5, [], 3, 0)  # piring sisa tamu sebelumnya
    s.run(10 * 60, [1, 2], 3, 0)
    assert s.table()["visit"]["phase"] == "menunggu_makanan"
    s.run(12 * 60, [1, 2], 5, 0)
    assert s.table()["visit"]["phase"] == "makan"


def test_plate_hidden_then_visible_again_is_not_cleared():
    s = OccSim()
    s.run(5 * 60, [1], 0, 0)
    s.run(10 * 60, [1], 1, 1)
    s.run(10 * 60 + 20, [1], 0, 1)  # piring tertutup 20 detik
    assert s.table()["visit"]["phase"] == "selesai_makan"
    s.run(12 * 60, [1], 1, 1)  # terlihat lagi
    assert s.table()["visit"]["phase"] == "makan"


def test_part_of_group_leaving_shortens_estimate():
    s = OccSim()
    s.run(5 * 60, [1, 2, 3], 0, 0)
    s.run(20 * 60, [1, 2, 3], 3, 3)
    full = s.table()["estimate"]["est_free_s"]
    s.run(21 * 60, [1], 3, 3)
    e = s.table()["estimate"]
    assert e["est_free_s"] < full - 60
    assert "sudah pergi" in e["reason"]


def test_learns_from_history():
    s = OccSim(OccupancyRules(learn_min_visits=3))
    t0 = 0.0
    for _ in range(3):  # tiap kunjungan: makanan menit 10, pergi menit 30 -> setelah makanan 20m
        meal(s, t0, [1, 2], food_at=10 * 60, cleared_at=25 * 60, leave_at=30 * 60, gone=33 * 60)
        t0 = s.t
    learned = s.f.learned()
    assert learned["post_food_s"] == pytest.approx(20 * 60, abs=30)
    assert learned["food_wait_s"] == pytest.approx(10 * 60, abs=30)

    s.run(t0 + 12 * 60, [7, 8], 0, 0)
    s.run(t0 + 15 * 60, [7, 8], 2, 0)  # makanan menit 12, sekarang menit 15
    e = s.table()["estimate"]
    assert e["est_free_min"] == pytest.approx(17, abs=1)  # 20m - 3m, bukan default 35m


def test_overdue_lowers_confidence_but_stays_positive():
    s = OccSim()
    s.run(5 * 60, [1, 2], 0, 0)
    s.run(10 * 60, [1, 2], 2, 0)
    c_on_time = s.table()["estimate"]["confidence"]
    s.run(70 * 60, [1, 2], 2, 0)  # makan 60m, default 35m -> lewat 25m
    e = s.table()["estimate"]
    assert e["est_free_min"] >= 1
    assert e["confidence"] < c_on_time
    assert "lewat perkiraan" in e["reason"]


def test_empty_with_dishes_needs_cleaning():
    s = OccSim()
    s.run(5 * 60, [1, 2], 0, 0)
    s.run(20 * 60, [1, 2], 2, 2)
    s.run(23 * 60, [], 2, 2)
    t = s.table()
    assert t["status"] == "perlu_dibersihkan"
    assert t["estimate"] is None
