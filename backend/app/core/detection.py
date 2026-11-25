"""Deteksi + tracking YOLO (Ultralytics), dipakai semua fitur.

Kelas model dipetakan ke "grup" lewat config.classes, misalnya:
  person, plate, glass, chair, table, car, motorcycle, outside_food
Fitur tidak perlu tahu nama kelas asli model.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

TRACKER_YAML = Path(__file__).resolve().parent / "tracker.yaml"


@dataclass
class Detection:
    group: str
    box: tuple[float, float, float, float]
    conf: float
    track_id: int | None = None


class Detector:
    def __init__(
        self,
        model: str,
        classes: dict[str, list[str]],
        groups: list[str] | None = None,
        conf: float = 0.35,
        imgsz: int = 960,
        device: str = "0",
    ):
        import torch

        self.conf = conf
        self.imgsz = imgsz
        self.device = device if (device == "cpu" or torch.cuda.is_available()) else "cpu"
        wanted_groups = groups or list(classes)

        if "world" in Path(model).name.lower():
            # YOLO-World: kelas ditentukan lewat teks, jadi "plate" bisa dideteksi tanpa training.
            from ultralytics import YOLOWorld

            self.model = YOLOWorld(model)
            prompts = list(dict.fromkeys(c for g in wanted_groups for c in classes.get(g, [])))
            self.model.set_classes(prompts)
        else:
            from ultralytics import YOLO

            self.model = YOLO(model)

        names: dict[int, str] = self.model.names  # type: ignore[assignment]
        self.class_group: dict[int, str] = {}
        for group in wanted_groups:
            wanted = {w.lower() for w in classes.get(group, [])}
            for cid, cname in names.items():
                if cname.lower() in wanted:
                    self.class_group[cid] = group

        found = set(self.class_group.values())
        self.warnings = [
            f"Model '{model}' tidak punya kelas untuk grup '{g}' (dicari: {classes.get(g)})"
            for g in wanted_groups
            if g not in found
        ]

    def _parse(self, res: Any) -> list[Detection]:
        boxes = res.boxes
        if boxes is None or len(boxes) == 0:
            return []
        xyxy = boxes.xyxy.cpu().numpy()
        cls = boxes.cls.cpu().numpy().astype(int)
        conf = boxes.conf.cpu().numpy()
        ids = boxes.id.cpu().numpy().astype(int).tolist() if boxes.id is not None else [None] * len(cls)
        return [
            Detection(self.class_group[c], tuple(map(float, b)), float(cf), i)  # type: ignore[arg-type]
            for b, c, cf, i in zip(xyxy, cls, conf, ids)
            if c in self.class_group
        ]

    def track(self, frame) -> list[Detection]:
        """Deteksi semua kelas + tracking ID untuk orang/kendaraan. Untuk pemrosesan video.

        Benda (piring, gelas) diambil langsung dari deteksi frame ini, bukan dari
        tracker: ByteTrack membuang deteksi ber-confidence rendah (mis. piring dari
        YOLO-World skor ~0.2), padahal benda tidak butuh ID untuk dihitung.
        """
        dets = self.detect(frame)
        tracked_groups = {"person", "car", "motorcycle"}
        track_cls = [c for c, g in self.class_group.items() if g in tracked_groups]
        if not track_cls:
            return dets
        res = self.model.track(
            frame,
            persist=True,
            conf=self.conf,
            imgsz=self.imgsz,
            device=self.device,
            classes=track_cls,
            tracker=str(TRACKER_YAML),
            verbose=False,
        )[0]
        return [d for d in dets if d.group not in tracked_groups] + self._parse(res)

    def detect(self, frame) -> list[Detection]:
        """Deteksi saja tanpa tracking. Untuk kalibrasi layout (meja & kursi)."""
        res = self.model.predict(
            frame,
            conf=self.conf,
            imgsz=self.imgsz,
            device=self.device,
            classes=list(self.class_group),
            verbose=False,
        )[0]
        return self._parse(res)
