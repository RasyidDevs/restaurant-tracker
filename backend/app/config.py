"""Memuat config.json: sumber video meja & parkir, model, kelas, aturan inti, aturan fitur, layout."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .core.table_state import CoreRules
from .core.zones import TableZone
from .features.parking import ParkingZone

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = BACKEND_DIR / "config" / "config.json"
EXAMPLE_CONFIG = BACKEND_DIR / "config" / "config.example.json"

# Grup kelas yang dideteksi setiap frame saat runtime. Kursi & meja statis (kalibrasi).
RUNTIME_GROUPS = ["person", "plate", "glass"]
PARKING_GROUPS = ["car", "motorcycle"]


def _resolve_source(src: str | int | None) -> str | int | None:
    if src is None or isinstance(src, int):
        return src
    s = src.strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if s == "simulate" or "://" in s:
        return s
    p = Path(s)
    if p.exists():
        return str(p)
    rel = BACKEND_DIR / s
    return str(rel) if rel.exists() else s


def _resolve_model(model: str) -> str:
    p = Path(model)
    if p.exists():
        return str(p)
    rel = BACKEND_DIR / model
    return str(rel) if rel.exists() else model


@dataclass
class Config:
    source: str | int
    parking_source: str | int | None
    model: str
    parking_model: str
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
    parking_slots: list[ParkingZone] = field(default_factory=list)
    path: Path | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def config_path(path: str | os.PathLike | None = None) -> Path:
    p = Path(path or os.environ.get("CV_CONFIG") or DEFAULT_CONFIG)
    return p if p.exists() else EXAMPLE_CONFIG


def load_config(path: str | os.PathLike | None = None) -> Config:
    p = config_path(path)
    data = json.loads(p.read_text(encoding="utf-8"))

    source = _resolve_source(data.get("source", "simulate")) or "simulate"
    if "parking_source" in data:
        parking_source = _resolve_source(data.get("parking_source"))
    else:
        parking_source = "simulate" if source == "simulate" else None

    return Config(
        source=source,
        parking_source=parking_source,
        model=_resolve_model(data.get("model", "yolo11s.pt")),
        parking_model=_resolve_model(data.get("parking_model", "yolo11n.pt")),
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
        parking_slots=[ParkingZone.from_dict(s) for s in data.get("parking_slots", [])],
        path=p,
        raw=data,
    )
