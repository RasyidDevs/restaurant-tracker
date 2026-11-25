"""API FastAPI.

Jalankan:  python -m app.main                       (pakai config/config.json)
           python -m app.main --source video.mp4    (override sumber)
           python -m app.main --source simulate     (tanpa kamera)

Endpoint inti (dipakai semua fitur):
  GET  /api/core/tables                 status inti tiap meja: orang, piring, gelas, kursi, lama terisi/kosong
  GET  /api/stream.mjpg                 video beranotasi
  WS   /ws/core                         status inti tiap 1 detik

Fitur waiting time:
  GET  /api/waiting                     sesi aktif, riwayat, alert, statistik
  POST /api/sessions/{id}/confirm       waiter menandai pesanan sudah lengkap
  WS   /ws/waiting                      snapshot waiting tiap 1 detik

Fitur makanan/minuman dari luar:
  GET  /api/outside-food                alert aktif, riwayat, aturan, statistik
  POST /api/outside-food/{id}/resolve   staf menandai alert sudah ditangani
  WS   /ws/outside-food                 snapshot tiap 1 detik

Saran tindakan AI (rule-based + ringkasan LLM opsional):
  GET  /api/recommendations             saran terurut prioritas, ringkasan, sumber data
  WS   /ws/recommendations              snapshot tiap 1 detik
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

from .config import load_config
from .hub import Hub
from .worker import start_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

cfg = load_config()
if os.environ.get("CV_SOURCE"):
    src = os.environ["CV_SOURCE"]
    cfg.source = int(src) if src.isdigit() else src

hub = Hub(cfg)
stop = threading.Event()


@asynccontextmanager
async def lifespan(_: FastAPI):
    start_worker(cfg, hub, stop)
    yield
    stop.set()


app = FastAPI(title="DineSight CV", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ------------------------------------------------------------------- core
@app.get("/api/core/tables")
def core_tables():
    return hub.core_snapshot()


@app.get("/api/stream.mjpg")
async def stream():
    async def gen():
        last = None
        while not stop.is_set():
            jpg = hub.latest_jpeg
            if jpg is not None and jpg is not last:
                last = jpg
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
            await asyncio.sleep(0.05)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


async def _push(ws: WebSocket, snap: Callable[[], dict[str, Any]]) -> None:
    await ws.accept()
    try:
        while True:
            await ws.send_json(snap())
            await asyncio.sleep(1)
    except (WebSocketDisconnect, RuntimeError):
        pass


@app.websocket("/ws/core")
async def ws_core(ws: WebSocket):
    await _push(ws, hub.core_snapshot)


# ------------------------------------------------------- fitur: waiting time
@app.get("/api/waiting")
def get_waiting():
    return hub.waiting_snapshot()


@app.post("/api/sessions/{session_id}/confirm")
def confirm(session_id: str):
    s = hub.confirm_waiting(session_id)
    if s is None:
        raise HTTPException(404, "Sesi tidak ditemukan atau sudah selesai")
    return s


@app.websocket("/ws/waiting")
async def ws_waiting(ws: WebSocket):
    await _push(ws, hub.waiting_snapshot)


# --------------------------------------------- fitur: makanan/minuman dari luar
@app.get("/api/outside-food")
def get_outside_food():
    return hub.outside_snapshot()


@app.post("/api/outside-food/{alert_id}/resolve")
def resolve_outside_food(alert_id: str):
    a = hub.resolve_outside(alert_id)
    if a is None:
        raise HTTPException(404, "Alert tidak ditemukan atau sudah selesai")
    return a


@app.websocket("/ws/outside-food")
async def ws_outside_food(ws: WebSocket):
    await _push(ws, hub.outside_snapshot)


# ------------------------------------------------- fitur: saran tindakan AI
@app.get("/api/recommendations")
def get_recommendations():
    return hub.recommendations_snapshot()


@app.websocket("/ws/recommendations")
async def ws_recommendations(ws: WebSocket):
    await _push(ws, hub.recommendations_snapshot)


def cli() -> None:
    import uvicorn

    p = argparse.ArgumentParser(description="Backend CV DineSight")
    p.add_argument("--config", help="path config.json")
    p.add_argument("--source", help="video file / rtsp url / webcam index / simulate")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    a = p.parse_args()
    if a.config:
        os.environ["CV_CONFIG"] = a.config
    if a.source:
        os.environ["CV_SOURCE"] = a.source
    uvicorn.run("app.main:app", host=a.host, port=a.port, reload=False)


if __name__ == "__main__":
    cli()
