"""Thread pemroses: sumber frame -> Detector -> Perception (core) -> fitur.

Sumber (config "source"):
  - path file video, "rtsp://...", angka webcam  -> YOLO asli
  - "simulate"                                   -> observasi buatan tanpa kamera/YOLO
"""

from __future__ import annotations

import logging
import random
import threading
import time

from .config import RUNTIME_GROUPS, Config
from .core.sources import is_file_source, iter_frames
from .core.zones import TableObs
from .hub import Hub

log = logging.getLogger("worker")

COLORS = {"person": (241, 102, 99), "plate": (94, 197, 34), "glass": (233, 165, 14)}  # BGR


def start_worker(cfg: Config, hub: Hub, stop: threading.Event) -> threading.Thread:
    target = run_simulation if cfg.source == "simulate" else run_video
    th = threading.Thread(target=_guard, args=(target, cfg, hub, stop), daemon=True, name="cv-worker")
    th.start()
    return th


def _guard(fn, cfg: Config, hub: Hub, stop: threading.Event) -> None:
    try:
        fn(cfg, hub, stop)
    except Exception as e:  # tampilkan error di dashboard, jangan mati diam-diam
        log.exception("worker error")
        hub.set_status("error", f"{type(e).__name__}: {e}")


# --------------------------------------------------------------------- video
def run_video(cfg: Config, hub: Hub, stop: threading.Event) -> None:
    import cv2

    from .core.detection import Detector

    hub.set_status("loading", f"Memuat model {cfg.model}")
    det = Detector(cfg.model, cfg.classes, RUNTIME_GROUPS, cfg.conf, cfg.imgsz, cfg.device)
    for w in det.warnings:
        log.warning(w)
    detail = f"{cfg.source} · {det.device} · {cfg.process_fps:g} fps"
    if det.warnings:
        detail += " · " + "; ".join(det.warnings)
    hub.set_status("running", detail)

    for t, frame in iter_frames(cfg.source, cfg.process_fps, cfg.realtime_playback, cfg.loop_video, stop):
        dets = det.track(frame)
        hub.step_detections(t, dets)
        ok, jpg = cv2.imencode(".jpg", _annotate(frame, dets, hub), [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ok:
            hub.latest_jpeg = jpg.tobytes()

    if not stop.is_set():
        hub.set_status("finished" if is_file_source(cfg.source) else "error",
                       "Video selesai" if is_file_source(cfg.source) else "Stream terputus")


def _annotate(frame, dets, hub: Hub):
    import cv2
    import numpy as np

    img = frame.copy()
    snap = hub.waiting_snapshot()
    tables = {t["id"]: t for t in snap["tables"]}
    for z in hub.cfg.tables:
        cv2.polylines(img, [np.array(z.zone, np.int32)], True, (200, 200, 200), 1)
        cv2.polylines(img, [np.array(z.surface, np.int32)], True, (255, 255, 255), 2)
        s = tables.get(z.id)
        for i, ch in enumerate(z.chairs):
            occ = bool(s and s["seat_flags"] and s["seat_flags"][i])
            cv2.rectangle(img, (int(ch[0]), int(ch[1])), (int(ch[2]), int(ch[3])), (0, 0, 255) if occ else (0, 200, 0), 1)
        if not s:
            continue
        label = f"{z.name}: {s['people']} org {s['plates']} piring {s['glasses']} gelas"
        if s["session"] and s["phase"] == "menunggu":
            m, sec = divmod(int(s["session"]["waiting_s"]), 60)
            label += f" | tunggu {m:02d}:{sec:02d}"
        x, y = map(int, z.zone[0])
        cv2.putText(img, label, (x, max(20, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
        cv2.putText(img, label, (x, max(20, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    for d in dets:
        x1, y1, x2, y2 = map(int, d.box)
        color = COLORS.get(d.group, (255, 255, 255))
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        tag = d.group + (f"#{d.track_id}" if d.group == "person" and d.track_id is not None else "")
        cv2.putText(img, f"{tag} {d.conf:.2f}", (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
    return img


# ---------------------------------------------------------------- simulasi
class _SimTable:
    """Skenario acak satu meja: kosong -> duduk -> minum -> makan -> pergi -> dibersihkan."""

    def __init__(self, rng: random.Random, seats: int, n_chairs: int, t: float):
        self.rng = rng
        self.seats = seats
        self.n_chairs = n_chairs
        self.next_id = rng.randint(1, 10_000) * 100
        self._new_cycle(t + rng.uniform(0, 400))

    def _new_cycle(self, start: float) -> None:
        r = self.rng
        n = r.randint(1, self.seats)
        self.ids = [self.next_id + i for i in range(n)]
        self.next_id += 100
        self.sit = start
        shared = r.random() < 0.2  # berbagi piring -> perlu konfirmasi waiter
        slow = r.random() < 0.2  # dapur lambat -> memicu alert
        base = r.uniform(6, 14) * 60 * (1.8 if slow else 1)
        self.drinks = sorted(self.sit + r.uniform(3, 8) * 60 for _ in range(n))
        n_plates = max(1, n - 1) if shared and n > 1 else n
        self.plates = sorted(self.sit + base + r.uniform(0, 6) * 60 for _ in range(n_plates))
        self.leave = self.plates[-1] + r.uniform(15, 35) * 60
        self.cleared = self.leave + r.uniform(1, 9) * 60
        self.next_cycle = self.cleared + r.uniform(2, 15) * 60

    def obs(self, t: float) -> TableObs:
        if t >= self.next_cycle:
            self._new_cycle(t)
        if t < self.sit or t >= self.cleared:
            return TableObs(seat_flags=[False] * self.n_chairs)
        ids = list(self.ids) if t < self.leave else []
        plates = sum(p <= t for p in self.plates)
        glasses = sum(d <= t for d in self.drinks)
        seat_flags = [i < len(ids) for i in range(self.n_chairs)]
        # gangguan: kadang tertutup tangan / deteksi berkedip
        if ids and self.rng.random() < 0.08:
            ids = ids[:-1]
        if plates and self.rng.random() < 0.1:
            plates -= 1
        if glasses and self.rng.random() < 0.1:
            glasses -= 1
        return TableObs(ids, plates, glasses, seat_flags)


def run_simulation(cfg: Config, hub: Hub, stop: threading.Event) -> None:
    rng = random.Random(42)
    sim_start = time.time() - 90 * 60  # mulai 90 menit lalu supaya riwayat langsung terisi
    sims = {z.id: _SimTable(rng, z.seats, len(z.chairs), sim_start) for z in cfg.tables}
    hub.set_status("running", f"Mode simulasi ({len(sims)} meja, {cfg.sim_speed:g}x)")

    tick = 0.5
    t = sim_start
    while not stop.is_set() and t < time.time():  # kejar 90 menit secepatnya
        hub.step(t, {tid: s.obs(t) for tid, s in sims.items()})
        t += tick

    wall_prev = time.time()
    while not stop.is_set():
        now = time.time()
        target = t + (now - wall_prev) * cfg.sim_speed
        wall_prev = now
        while t < target:
            hub.step(t, {tid: s.obs(t) for tid, s in sims.items()})
            t += tick
        time.sleep(0.1)
