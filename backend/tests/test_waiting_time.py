"""Tes fitur waiting time di atas Perception (core)."""

import random

import pytest

from .helpers import Sim


def test_normal_flow_ends_on_last_item():
    s = Sim()
    s.run(750, [1, 2, 3], 0, 0)
    s.run(1090, [1, 2, 3], 0, 3)  # minuman 12m30d
    s.run(1300, [1, 2, 3], 1, 3)  # piring 1 18m10d
    s.run(1445, [1, 2, 3], 2, 3)
    s.run(1500, [1, 2, 3], 3, 3)  # piring 3 24m05d -> lengkap

    (end,) = s.ended()
    sess = end["session"]
    assert sess["start"] == pytest.approx(0, abs=0.5)
    assert (sess["status"], sess["end_reason"]) == ("lengkap", "otomatis")
    assert sess["first_drink_s"] == pytest.approx(750, abs=1)
    assert sess["first_food_s"] == pytest.approx(1090, abs=1)
    assert sess["waiting_s"] == pytest.approx(1445, abs=1)
    assert s.alerts() == []


def test_waiter_passing_does_not_start_session():
    s = Sim()
    s.run(10, [99], 0, 0)
    s.run(200, [], 0, 0)
    assert s.w.phase_of("T1") == "kosong"
    assert not [e for e in s.events if e["type"] == "session_start"]


def test_shared_plate_alert_then_waiter_confirms():
    s = Sim()
    s.run(600, [1, 2, 3], 0, 0)
    s.run(900, [1, 2, 3], 0, 3)
    s.run(25 * 60 + 5, [1, 2, 3], 2, 3)  # 2 piring untuk 3 orang

    assert [a["kind"] for a in s.alerts()] == ["belum_lengkap"]
    assert s.w.phase_of("T1") == "menunggu"

    sid = s.w.per_table["T1"].session.id
    sess = s.w.confirm(sid, s.t)
    assert sess["end_reason"] == "konfirmasi_waiter"
    assert sess["waiting_s"] == pytest.approx(900, abs=1)  # item terakhir, bukan waktu klik


def test_no_item_alert():
    s = Sim()
    s.run(20 * 60 + 5, [1, 2], 0, 0)
    assert [a["kind"] for a in s.alerts()] == ["belum_disajikan"]


def test_leftover_items_are_baseline():
    s = Sim()
    s.run(5, [], 2, 1)
    s.run(300, [1, 2], 2, 1)
    s.run(600, [1, 2], 2, 3)
    s.run(700, [1, 2], 4, 3)

    (end,) = s.ended()
    assert (end["session"]["plates_served"], end["session"]["glasses_served"]) == (2, 2)
    assert end["session"]["waiting_s"] == pytest.approx(595, abs=1)  # duduk detik 5, piring detik 600


def test_flicker_does_not_create_fake_items():
    rng = random.Random(0)

    def noise(t, p, g):
        if rng.random() < 0.15:
            p += rng.choice([-1, 1])
        if rng.random() < 0.15:
            g += rng.choice([-1, 1])
        return max(p, 0), max(g, 0)

    s = Sim()
    s.run(600, [1, 2, 3], 0, 0, noise)
    s.run(900, [1, 2, 3], 2, 0, noise)
    sess = s.w.per_table["T1"].session
    assert (sess.plates_served, sess.glasses_served) == (2, 0)
    assert sess.first_food_at == pytest.approx(600, abs=2)


def test_customers_leave_before_complete():
    s = Sim()
    s.run(300, [1, 2], 0, 0)
    s.run(800, [1, 2], 1, 0)
    s.run(1100, [], 1, 0)
    (end,) = s.ended()
    assert (end["session"]["status"], end["session"]["end_reason"]) == ("pergi", "pelanggan_pergi")
    assert s.w.phase_of("T1") == "kosong"


def test_person_joining_raises_requirement():
    s = Sim()
    s.run(300, [1, 2], 0, 0)
    s.run(600, [1, 2, 3], 0, 0)
    s.run(900, [1, 2, 3], 2, 2)
    assert s.w.phase_of("T1") == "menunggu"
    s.run(1000, [1, 2, 3], 3, 3)
    (end,) = s.ended()
    assert end["session"]["people_peak"] == 3


def test_new_group_right_after_previous_gets_own_session():
    s = Sim()
    s.run(300, [1, 2], 0, 0)
    s.run(400, [1, 2], 2, 2)  # lengkap -> disajikan
    s.run(1000, [1, 2], 2, 2)
    s.run(1060, [], 0, 0)  # pergi, meja dibereskan
    s.run(2000, [7, 8, 9], 0, 0)  # rombongan baru duduk 60 detik kemudian
    starts = [e for e in s.events if e["type"] == "session_start"]
    assert len(starts) == 2
    assert starts[1]["t"] == pytest.approx(1060, abs=1)
    assert s.w.phase_of("T1") == "menunggu"
    assert [a["kind"] for a in s.alerts()] == []
    s.run(2400, [7, 8, 9], 0, 0)  # 22 menit tanpa sajian -> alert untuk rombongan baru
    assert [a["kind"] for a in s.alerts()] == ["belum_disajikan"]


def test_group_returning_to_their_food_is_not_new_session():
    s = Sim()
    s.run(300, [1, 2], 0, 0)
    s.run(400, [1, 2], 2, 2)  # lengkap
    s.run(460, [], 2, 2)  # semua keluar sebentar, piring masih di meja
    s.run(800, [5, 6], 2, 2)  # kembali (ID baru)
    assert len([e for e in s.events if e["type"] == "session_start"]) == 1
    assert s.w.phase_of("T1") == "disajikan"


def test_item_cleared_then_next_item_still_counted():
    s = Sim()
    s.run(300, [1, 2], 0, 0)
    s.run(400, [1, 2], 0, 1)  # gelas 1
    s.run(500, [1, 2], 0, 0)  # gelas 1 diangkat
    s.run(600, [1, 2], 0, 1)  # gelas 2 datang
    assert s.w.per_table["T1"].session.glasses_served == 2


def test_briefly_hidden_item_is_not_counted_twice():
    s = Sim()
    s.run(300, [1, 2], 0, 0)
    s.run(400, [1, 2], 1, 0)
    s.run(420, [1, 2], 0, 0)  # piring tertutup 20 detik
    s.run(500, [1, 2], 1, 0)
    assert s.w.per_table["T1"].session.plates_served == 1
