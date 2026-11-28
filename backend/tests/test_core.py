"""Tes metode inti: penghalus, dwell, zona, status meja, layout meja & kursi."""

import random

import pytest

from app.core.detection import Detection
from app.core.layout import build_layout, cluster_static
from app.core.smoothing import StableCount
from app.core.tracks import DwellTracker
from app.core.zones import ZoneMap

from .helpers import ZONE, Sim


def test_stable_count_backdates_change():
    c = StableCount(window_s=3, hold_s=3)
    t, change = 0.0, None
    while t < 10:
        change = c.update(t, 2 if t >= 4 else 0) or change
        t = round(t + 0.2, 3)
    assert change is not None and change.new == 2
    assert change.at == pytest.approx(4, abs=0.3)


def test_dwell_filters_passers_by():
    d = DwellTracker(min_dwell_s=30, lost_grace_s=15)
    t = 0.0
    while t < 40:
        d.update(t, [1, 99] if t < 8 else [1])  # 99 = waiter lewat 8 detik
        t += 0.2
    assert set(d.settled()) == {1}


def test_zone_assignment_people_items_and_chairs():
    dets = [
        Detection("person", (2, 25, 18, 75), 0.9, 7),  # duduk di kursi kiri
        Detection("person", (200, 0, 220, 50), 0.9, 8),  # di luar meja
        Detection("plate", (30, 30, 45, 45), 0.8),
        Detection("glass", (60, 60, 66, 70), 0.8),
        Detection("plate", (85, 5, 95, 15), 0.8),  # di zona tapi bukan di permukaan meja (nampan waiter)
    ]
    obs = ZoneMap([ZONE]).assign(dets)["T1"]
    assert obs.person_ids == [7]
    assert (obs.plates, obs.glasses) == (1, 1)
    assert obs.seat_flags == [True, False, False, False]


def test_table_state_occupied_and_emptied_times():
    s = Sim()
    s.run(5, [], 0, 0)
    s.run(300, [1, 2], 0, 0)  # duduk mulai detik 5
    assert s.table.people == 2
    assert s.table.occupied_since == pytest.approx(5, abs=0.3)
    assert s.table.seats_occupied == 2
    s.run(400, [], 0, 0)  # pergi di detik 300
    assert s.table.people == 0
    assert s.table.empty_since == pytest.approx(300, abs=0.5)
    assert s.table.empty_for_s() == pytest.approx(100, abs=0.5)


def test_table_state_flicker_resistant():
    rng = random.Random(1)

    def noise(t, p, g):
        if rng.random() < 0.15:
            p = max(0, p + rng.choice([-1, 1]))
        return p, g

    s = Sim()
    s.run(120, [1], 3, 0, noise)
    values = [p for _, _, p, _ in s.table.history]
    changes = sum(a != b for a, b in zip(values, values[1:]))
    assert s.table.plates == 3
    assert changes == 1  # hanya 0 -> 3 sekali, tidak naik-turun mengikuti kedipan


def test_cluster_static_keeps_only_consistent_objects():
    table = (100, 100, 300, 200)
    frames = []
    rng = random.Random(0)
    for i in range(20):
        jitter = lambda b: tuple(v + rng.uniform(-3, 3) for v in b)  # noqa: E731
        boxes = [jitter(table)]
        if i == 3:
            boxes.append((500, 500, 600, 600))  # salah deteksi sesaat
        frames.append(boxes)
    out = cluster_static(frames, min_presence=0.5)
    assert len(out) == 1
    assert out[0] == pytest.approx(table, abs=3)


def test_build_layout_assigns_chairs_to_nearest_table():
    tables = [(100, 100, 300, 200), (600, 100, 800, 200)]
    chairs = [
        (40, 120, 95, 180), (305, 120, 360, 180),  # meja kiri
        (540, 120, 595, 180), (805, 120, 860, 180), (670, 205, 730, 260),  # meja kanan
        (1200, 900, 1250, 950),  # kursi jauh, tidak milik meja mana pun
    ]
    layout = build_layout(tables, chairs)
    assert [t["seats"] for t in layout] == [2, 3]
    assert layout[0]["name"] == "Meja 1" and layout[0]["surface"][0] == [100, 100]


def test_id_switch_keeps_table_occupied():
    # Tracker memberi ID baru ke orang yang sama (tertutup waiter) -> meja tetap terisi.
    s = Sim()
    s.run(600, [1], 0, 0)
    while s.t < 700:
        s.run(s.t + 1, [2], 0, 0)
        assert s.table.occupied
    assert s.table.occupied_since == pytest.approx(0, abs=0.3)
    assert s.table.occupied_for_s() == pytest.approx(700, abs=0.5)


def test_unsettled_track_does_not_keep_table_occupied_forever():
    # Setelah pelanggan pergi, ada orang lalu-lalang terus di zona: meja tetap jadi kosong.
    s = Sim()
    s.run(300, [1], 0, 0)
    t = 300.0
    pid = 1000
    while t < 500:  # orang lewat bergantian, masing-masing 10 detik
        s.run(t + 10, [pid], 0, 0)
        t += 10
        pid += 1
    assert not s.table.occupied
    assert s.table.empty_since == pytest.approx(300, abs=0.5)


def test_redact_source_hides_credentials():
    from app.core.sources import redact_source

    assert redact_source("rtsp://admin:rahasia@10.0.0.5:554/stream") == "rtsp://***@10.0.0.5:554/stream"
    assert redact_source("rtsp://10.0.0.5/stream") == "rtsp://10.0.0.5/stream"
    assert redact_source("videos/demo.mp4") == "videos/demo.mp4"
    assert redact_source(0) == "0"
