"""Memuat config.json: sumber video, model, kelas, aturan inti, aturan fitur, layout meja."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .core.table_state import CoreRules
from .core.zones import TableZone

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = BACKEND_DIR / "config" / "config.json"
EXAMPLE_CONFIG = BACKEND_DIR / "config" / "config.example.json"

# Grup kelas yang dideteksi setiap frame saat runtime. Kursi & meja tidak perlu:
# posisinya statis dan sudah dikalibrasi ke layout (tools/auto_layout.py).
RUNTIME_GROUPS = ["person", "plate", "glass"]


@dataclass
class Config:
    source: str | int
    model: str
    device: str
    conf: float
    imgsz: int
    process_fps: float
    realtime_playback: bool
    loop_video: bool
    sim_speed: float
    classes: dict[str, list[str]]
    core: CoreRules
    features: dict[str, dict[str, Any]]
    tables: list[TableZone]
    path: Path | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def config_path(path: str | os.PathLike | None = None) -> Path:
    p = Path(path or os.environ.get("CV_CONFIG") or DEFAULT_CONFIG)
    return p if p.exists() else EXAMPLE_CONFIG


def load_config(path: str | os.PathLike | None = None) -> Config:
    p = config_path(path)
    data = json.loads(p.read_text(encoding="utf-8"))

    source = data.get("source", "simulate")
    if isinstance(source, str) and source.isdigit():
        source = int(source)  # index webcam

    return Config(
        source=source,
        model=data.get("model", "yolo11s.pt"),
        device=str(data.get("device", "0")),
        conf=float(data.get("conf", 0.35)),
        imgsz=int(data.get("imgsz", 960)),
        process_fps=float(data.get("process_fps", 5)),
        realtime_playback=bool(data.get("realtime_playback", True)),
        loop_video=bool(data.get("loop_video", False)),
        sim_speed=float(data.get("sim_speed", 10)),
        classes=data.get("classes", {}),
        core=CoreRules.from_dict(data.get("core")),
        features=data.get("features", {}),
        tables=[TableZone.from_dict(t) for t in data.get("tables", [])],
        path=p,
        raw=data,
    )
