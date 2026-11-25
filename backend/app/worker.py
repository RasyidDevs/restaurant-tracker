"""Thread pemroses: sumber video meja & sumber video parkir berjalan paralel.

Sumber (`source` & `parking_source` di config):
  - path file video, "rtsp://...", angka webcam  -> YOLO asli
  - "simulate"                                   -> observasi buatan tanpa kamera/YOLO
"""

from __future__ import annotations

import logging
import random
import threading
import time

from .config import PARKING_GROUPS, RUNTIME_GROUPS, Config
from .core.geometry import box_center, iou, point_in_polygon
from .core.sources import is_file_source, iter_frames
from .core.zones import TableObs
from .features.parking import ParkingZone, SlotObs
from .hub import Hub

log = logging.getLogger("worker")

COLORS = {
    "person": (241, 102, 99),
    "plate": (94, 197, 34),
    "glass": (233, 165, 14),
    "car": (235, 160, 30),
    "motorcycle": (80, 190, 250),
}  # BGR

SLOT_COLORS = {
    "kosong": (160, 160, 160),
    "normal": (94, 197, 34),
    "mendekati": (14, 175, 245),
    "lewat": (68, 68, 239),
}  # BGR

_INFER_LOCK = threading.Lock()


def start_worker(cfg: Config, hub: Hub, stop: threading.Event) -> list[threading.Thread]:
    threads: list[threading.Thread] = []

    indoor_fn = run_simulation if cfg.source == "simulate" else run_video
    t1 = threading.Thread(
        target=_guard, args=(indoor_fn, cfg, hub, stop, hub.set_status), daemon=True, name="cv-worker"
    )
    t1.start()
    threads.append(t1)

    if cfg.parking_source is not None:
        park_fn = run_parking_simulation if cfg.parking_source == "simulate" else run_parking_video
        t2 = threading.Thread(
            target=_guard, args=(park_fn, cfg, hub, stop, hub.set_parking_status), daemon=True, name="cv-parking-worker"
        )
        t2.start()
        threads.append(t2)

    return threads


def _guard(fn, cfg: Config, hub: Hub, stop: threading.Event, set_status) -> None:
    try:
        fn(cfg, hub, stop)
    except Exception as e:  # tampilkan error di dashboard, jangan mati diam-diam
        log.exception("worker error")
        set_status("error", f"{type(e).__name__}: {e}")


# --------------------------------------------------------------- video meja
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
        with _INFER_LOCK:
            dets = det.track(frame)
        hub.step_detections(t, dets)
        ok, jpg = cv2.imencode(".jpg", _annotate(frame, dets, hub), [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ok:
            hub.latest_jpeg = jpg.tobytes()

    if not stop.is_set():
        hub.set_status(
            "finished" if is_file_source(cfg.source) else "error",
            "Video selesai" if is_file_source(cfg.source) else "Stream terputus",
        )


def _draw_pill(img, text: str, x: int, y: int, bg: tuple[int, int, int], scale: float = 0.48) -> None:
    import cv2

    h_img, w_img = img.shape[:2]
    (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    pad = 4
    x = max(2, min(x, w_img - tw - pad * 2 - 2))
    y = max(th + pad * 2, min(y, h_img - base - 2))
    cv2.rectangle(img, (x, y - th - pad * 2), (x + tw + pad * 2, y + base), bg, -1)
    cv2.putText(img, text, (x + pad, y - pad), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1, cv2.LINE_AA)


def _annotate(frame, dets, hub: Hub):
    import cv2
    import numpy as np

    img = frame.copy()
    scale = max(0.42, min(0.6, img.shape[1] / 1280 * 0.6))
    snap = hub.waiting_snapshot()
    tables = {t["id"]: t for t in snap["tables"]}
    for d in dets:
        x1, y1, x2, y2 = map(int, d.box)
        color = COLORS.get(d.group, (255, 255, 255))
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        tag = d.group + (f"#{d.track_id}" if d.group == "person" and d.track_id is not None else "")
        _draw_pill(img, f"{tag} {d.conf:.2f}", x1, y1 - 2, (35, 35, 35), scale * 0.85)
    for z in hub.cfg.tables:
        cv2.polylines(img, [np.array(z.zone, np.int32)], True, (190, 190, 190), 1)
        cv2.polylines(img, [np.array(z.surface, np.int32)], True, (255, 255, 255), 2)
        s = tables.get(z.id)
        for i, ch in enumerate(z.chairs):
            occ = bool(s and s["seat_flags"] and s["seat_flags"][i])
            cv2.rectangle(img, (int(ch[0]), int(ch[1])), (int(ch[2]), int(ch[3])), (0, 0, 255) if occ else (0, 200, 0), 1)
        if not s:
            continue
        label = f"{z.name}: {s['people']} org, {s['plates']} piring, {s['glasses']} gelas"
        if s["session"] and s["phase"] == "menunggu":
            m, sec = divmod(int(s["session"]["waiting_s"]), 60)
            label += f" | {m:02d}:{sec:02d}"
        x, y = map(int, z.zone[0])
        _draw_pill(img, label, x, y - 4, (20, 20, 20), scale)
    return img


# ------------------------------------------------------------- video parkir
def run_parking_video(cfg: Config, hub: Hub, stop: threading.Event) -> None:
    import cv2

    from .core.detection import Detector

    assert cfg.parking_source is not None
    hub.set_parking_status("loading", f"Memuat model parkir {cfg.parking_model}")
    park_conf = max(cfg.conf, 0.35)
    det = Detector(cfg.parking_model, cfg.classes, PARKING_GROUPS, park_conf, cfg.imgsz, cfg.device)
    for w in det.warnings:
        log.warning(w)
    mode = "auto-slot" if hub.parking.auto_mode else f"{len(cfg.parking_slots)} slot"
    detail = f"{cfg.parking_source} · {mode} · {det.device} · {cfg.process_fps:g} fps"
    if det.warnings:
        detail += " · " + "; ".join(det.warnings)
    hub.set_parking_status("running", detail)

    for t, frame in iter_frames(cfg.parking_source, cfg.process_fps, cfg.realtime_playback, cfg.loop_video, stop):
        with _INFER_LOCK:
            dets = det.track(frame)
        hub.step_parking_detections(t, dets, (frame.shape[0], frame.shape[1]))
        ok, jpg = cv2.imencode(".jpg", _annotate_parking(frame, dets, hub), [cv2.IMWRITE_JPEG_QUALITY, 75])
        if ok:
            hub.latest_parking_jpeg = jpg.tobytes()

    if not stop.is_set():
        hub.set_parking_status(
            "finished" if is_file_source(cfg.parking_source) else "error",
            "Video parkir selesai" if is_file_source(cfg.parking_source) else "Stream parkir terputus",
        )


def _annotate_parking(frame, dets, hub: Hub):
    import cv2
    import numpy as np

    img = frame.copy()
    scale = max(0.4, min(0.55, img.shape[1] / 1280 * 0.55))
    snap = hub.parking_snapshot()
    slots = snap["slots"]
    auto_boxes = [tuple(s["box"]) for s in slots if s.get("box")]

    # Kendaraan yang baru masuk / sedang berjalan melintas (belum menetap di slot)
    for d in dets:
        if d.group not in ("car", "motorcycle"):
            continue
        if auto_boxes and any(iou(d.box, sb) >= 0.35 for sb in auto_boxes):
            continue
        if not auto_boxes and any(point_in_polygon(box_center(d.box), s["zone"]) for s in slots if len(s["zone"]) >= 3):
            continue
        x1, y1, x2, y2 = map(int, d.box)
        cv2.rectangle(img, (x1, y1), (x2, y2), (210, 180, 60), 1)
        _draw_pill(img, "melintas", x1, y1 - 2, (90, 75, 25), scale * 0.85)

    # Satu kotak + satu label bersih untuk tiap slot parkir
    for s in slots:
        poly = s.get("zone") or []
        if len(poly) < 3:
            continue
        color = SLOT_COLORS.get(s["level"], (160, 160, 160))
        cv2.polylines(img, [np.array(poly, np.int32)], True, color, 2)
        x, y = map(int, poly[0])
        if s["occupied"]:
            m, sec = divmod(int(s["duration_s"]), 60)
            h, m = divmod(m, 60)
            dur_txt = f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"
            label = f"{s['id']} {dur_txt}" + (" LEWAT" if s["level"] == "lewat" else "")
            bg = (35, 35, 180) if s["level"] == "lewat" else (15, 115, 185) if s["level"] == "mendekati" else (35, 115, 35)
        else:
            label = f"{s['id']} kosong"
            bg = (70, 70, 70)
        _draw_pill(img, label, x, y - 2, bg, scale)
    return img


# ------------------------------------------------------------ simulasi meja
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
        if ids and self.rng.random() < 0.08:
            ids = ids[:-1]
        if plates and self.rng.random() < 0.1:
            plates -= 1
        if glasses and self.rng.random() < 0.1:
            glasses -= 1
        return TableObs(ids, plates, glasses, seat_flags)


def run_simulation(cfg: Config, hub: Hub, stop: threading.Event) -> None:
    rng = random.Random(42)
    sim_start = time.time() - 90 * 60
    sims = {z.id: _SimTable(rng, z.seats, len(z.chairs), sim_start) for z in cfg.tables}
    hub.set_status("running", f"Mode simulasi ({len(sims)} meja, {cfg.sim_speed:g}x)")

    tick = 0.5
    t = sim_start
    while not stop.is_set() and t < time.time():
        hub.step(t, {tid: s.obs(t) for tid, s in sims.items()})
        t += tick

    wall_prev = time.time()
    while not stop.is_set():
        now = time.time()
        dt = min(now - wall_prev, 5.0)  # cegah lonjakan panjang setelah laptop sleep
        target = t + dt * cfg.sim_speed
        wall_prev = now
        while not stop.is_set() and t < target:
            hub.step(t, {tid: s.obs(t) for tid, s in sims.items()})
            t += tick
        time.sleep(0.1)


# ---------------------------------------------------------- simulasi parkir
class _SimSlot:
    """Skenario satu slot parkir: kosong -> kendaraan masuk -> parkir (sebagian lewat batas) -> keluar."""

    def __init__(self, rng: random.Random, zone: ParkingZone, limit_s: float, t: float):
        self.rng = rng
        self.zone = zone
        self.limit_s = limit_s
        self.next_id = rng.randint(1, 900)
        self._new_cycle(t + rng.uniform(0, limit_s * 0.6))

    def _new_cycle(self, start: float) -> None:
        r = self.rng
        self.tid = self.next_id
        self.next_id += 1
        self.arrive = start
        roll = r.random()
        if roll < 0.22:  # lewat batas
            stay = self.limit_s * r.uniform(1.08, 1.45)
        elif roll < 0.42:  # mendekati batas
            stay = self.limit_s * r.uniform(0.86, 0.99)
        else:  # normal
            stay = self.limit_s * r.uniform(0.2, 0.78)
        self.leave = self.arrive + stay
        self.next_cycle = self.leave + self.limit_s * r.uniform(0.1, 0.35)

    def obs(self, t: float) -> SlotObs:
        if t >= self.next_cycle:
            self._new_cycle(t)
        if self.arrive <= t < self.leave:
            if self.rng.random() < 0.04:  # tertutup sesaat (< lost_grace_s)
                return SlotObs()
            return SlotObs([self.tid], self.zone.type)
        return SlotObs()


def run_parking_simulation(cfg: Config, hub: Hub, stop: threading.Event) -> None:
    rng = random.Random(77)
    with hub.lock:
        zones = hub.parking.ensure_sim_slots()
        rules = hub.parking.rules
    max_limit_s = max((rules.limit_s_for(z.type, z.limit_min) for z in zones), default=180 * 60)
    sim_start = time.time() - max_limit_s * 1.4
    sims = {z.id: _SimSlot(rng, z, rules.limit_s_for(z.type, z.limit_min), sim_start) for z in zones}
    hub.set_parking_status("running", f"Mode simulasi ({len(sims)} slot parkir, {cfg.sim_speed:g}x)")

    tick = 2.0
    t = sim_start
    while not stop.is_set() and t < time.time():
        hub.step_parking(t, {sid: s.obs(t) for sid, s in sims.items()})
        t += tick

    wall_prev = time.time()
    while not stop.is_set():
        now = time.time()
        dt = min(now - wall_prev, 5.0)
        target = t + dt * cfg.sim_speed
        wall_prev = now
        while not stop.is_set() and t < target:
            hub.step_parking(t, {sid: s.obs(t) for sid, s in sims.items()})
            t += tick
        time.sleep(0.2)
