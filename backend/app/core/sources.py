"""Sumber frame dengan timestamp yang akurat (dipakai semua fitur).

  - file video : t = waktu mulai + nomor_frame / fps_video (durasi akurat walau
                 pemrosesan lebih lambat/cepat dari real-time)
  - CCTV/webcam: t = jam dinding, frame dibuang supaya tetap ~process_fps
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def is_file_source(src: str | int) -> bool:
    return isinstance(src, str) and Path(src).exists()


def redact_source(src: str | int) -> str:
    """Sembunyikan user:password di URL kamera sebelum ditampilkan di dashboard/log.

    rtsp://admin:rahasia@10.0.0.5:554/stream -> rtsp://***@10.0.0.5:554/stream
    """
    s = str(src)
    try:
        u = urlsplit(s)
    except ValueError:
        return s
    if "@" not in u.netloc:
        return s
    return urlunsplit((u.scheme, "***@" + u.netloc.rsplit("@", 1)[1], u.path, u.query, u.fragment))


def iter_frames(
    src: str | int,
    process_fps: float,
    realtime: bool = True,
    loop: bool = False,
    stop: threading.Event | None = None,
) -> Iterator[tuple[float, object]]:
    import cv2

    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        raise RuntimeError(f"Tidak bisa membuka sumber video: {redact_source(src)}")

    is_file = is_file_source(src)
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, round(video_fps / process_fps)) if is_file else 1
    min_interval = 1.0 / process_fps
    t0 = wall0 = time.time()
    idx = -1
    offset = 0.0  # akumulasi durasi saat video diulang
    last = 0.0

    try:
        while not (stop and stop.is_set()):
            ok, frame = cap.read()
            if not ok:
                if is_file and loop:
                    offset += (idx + 1) / video_fps
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    idx = -1
                    continue
                return
            idx += 1
            if is_file:
                if idx % step:
                    continue
                vt = offset + idx / video_fps
                if realtime:
                    delay = vt - (time.time() - wall0)
                    if delay > 0:
                        time.sleep(delay)
                yield t0 + vt, frame
            else:
                now = time.time()
                if now - last < min_interval:
                    continue
                last = now
                yield now, frame
    finally:
        cap.release()
