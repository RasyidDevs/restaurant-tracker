"""API FastAPI.

Jalankan:  python -m app.main                                                     (pakai config/config.json)
           python -m app.main --source meja.mp4 --parking-source parkir.mp4       (2 file video berbeda)
           python -m app.main --source simulate                                   (tanpa kamera)

Endpoint inti (dipakai semua fitur):
  GET  /api/core/tables                   status inti tiap meja
  GET  /api/stream.mjpg                   video meja beranotasi
  WS   /ws/core                           status inti tiap 1 detik

Fitur waiting time:
  GET  /api/waiting                       sesi aktif, riwayat, alert, statistik
  POST /api/sessions/{id}/confirm         waiter menandai pesanan sudah lengkap
  WS   /ws/waiting                        snapshot waiting tiap 1 detik

Fitur parkiran:
  GET  /api/parking                       slot mobil & motor, peringatan, riwayat, statistik
  GET  /api/parking/stream.mjpg           video parkiran beranotasi
  POST /api/parking/slots/{id}/notify     kirim peringatan ke juru parkir
  WS   /ws/parking                        snapshot parkiran tiap 1 detik

Pusat alert gabungan:
  GET  /api/alerts                        semua alert live (waiting + parkir)
  POST /api/alerts/{id}/resolve           tandai alert selesai/diabaikan
  WS   /ws/alerts                         alert live tiap 1 detik
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import threading
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .config import _resolve_source, load_config
from .hub import Hub
from .worker import start_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

_hub: Hub | None = None
_stop = threading.Event()


def _build_hub() -> Hub:
    cfg = load_config()
    if os.environ.get("CV_SOURCE"):
        cfg.source = _resolve_source(os.environ["CV_SOURCE"]) or "simulate"
    if os.environ.get("CV_PARKING_SOURCE"):
        cfg.parking_source = _resolve_source(os.environ["CV_PARKING_SOURCE"])
    elif cfg.source == "simulate" and cfg.parking_source is None:
        cfg.parking_source = "simulate"
    return Hub(cfg)


def get_hub() -> Hub:
    global _hub
    if _hub is None:
        _hub = _build_hub()
    return _hub


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _hub, _stop
    _stop = threading.Event()
    _hub = _build_hub()
    start_worker(_hub.cfg, _hub, _stop)
    yield
    _stop.set()


app = FastAPI(title="DineSight CV", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173", "http://127.0.0.1:4173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _mjpeg_stream(get_jpg: Callable[[], bytes | None]) -> StreamingResponse:
    async def gen():
        last = None
        while not _stop.is_set():
            jpg = get_jpg()
            if jpg is not None and jpg is not last:
                last = jpg
                header = f"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpg)}\r\n\r\n".encode("ascii")
                yield header + jpg + b"\r\n"
            await asyncio.sleep(0.05)

    return StreamingResponse(
        gen(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


async def _push(ws: WebSocket, snap: Callable[[], dict[str, Any]]) -> None:
    await ws.accept()
    try:
        while not _stop.is_set():
            await ws.send_json(snap())
            await asyncio.sleep(1)
    except (WebSocketDisconnect, RuntimeError):
        pass


# ------------------------------------------------------------------- core
@app.get("/api/core/tables")
def core_tables():
    return get_hub().core_snapshot()


@app.get("/api/stream.mjpg")
async def stream():
    return _mjpeg_stream(lambda: get_hub().latest_jpeg)


@app.websocket("/ws/core")
async def ws_core(ws: WebSocket):
    await _push(ws, lambda: get_hub().core_snapshot())


# ------------------------------------------------------- fitur: waiting time
@app.get("/api/waiting")
def get_waiting():
    return get_hub().waiting_snapshot()


@app.post("/api/sessions/{session_id}/confirm")
def confirm(session_id: str):
    s = get_hub().confirm_waiting(session_id)
    if s is None:
        raise HTTPException(404, "Sesi tidak ditemukan atau sudah selesai")
    return s


@app.websocket("/ws/waiting")
async def ws_waiting(ws: WebSocket):
    await _push(ws, lambda: get_hub().waiting_snapshot())


# ---------------------------------------------------------- fitur: parkiran
@app.get("/api/parking")
def get_parking():
    return get_hub().parking_snapshot()


@app.get("/api/parking/stream.mjpg")
async def parking_stream():
    return _mjpeg_stream(lambda: get_hub().latest_parking_jpeg)


@app.post("/api/parking/slots/{slot_id}/notify")
def notify_parking_slot(slot_id: str):
    s = get_hub().notify_parking(slot_id)
    if s is None:
        raise HTTPException(404, "Slot parkir kosong atau tidak ditemukan")
    return s


@app.websocket("/ws/parking")
async def ws_parking(ws: WebSocket):
    await _push(ws, lambda: get_hub().parking_snapshot())


# ----------------------------------------------------------- pusat alert
@app.get("/api/alerts")
def get_alerts():
    return get_hub().alerts_snapshot()


@app.post("/api/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: str):
    get_hub().resolve_alert(alert_id)
    return {"ok": True, "id": alert_id}


@app.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket):
    await _push(ws, lambda: get_hub().alerts_snapshot())


def cli() -> None:
    import uvicorn

    p = argparse.ArgumentParser(description="Backend CV DineSight")
    p.add_argument("--config", help="path config.json")
    p.add_argument("--source", help="video meja / rtsp url / webcam index / simulate")
    p.add_argument("--parking-source", help="video parkiran / rtsp url / webcam index / simulate")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    a = p.parse_args()
    if a.config:
        os.environ["CV_CONFIG"] = a.config
    if a.source:
        os.environ["CV_SOURCE"] = a.source
    if a.parking_source:
        os.environ["CV_PARKING_SOURCE"] = a.parking_source
    uvicorn.run("app.main:app", host=a.host, port=a.port, reload=False)


if __name__ == "__main__":
    cli()
