"""Zona meja + kursi dan pembagian deteksi ke tiap meja.

Setiap meja:
  zone    : polygon meja + kursi        -> tempat menghitung orang
  surface : polygon permukaan meja      -> tempat menghitung piring & gelas
  chairs  : kotak kursi (statis)        -> status tiap kursi terisi/kosong
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .detection import Detection
from .geometry import Box, Polygon, box_center, expand_box, point_in_box, point_in_polygon


@dataclass
class TableZone:
    id: str
    name: str
    seats: int
    zone: Polygon
    surface: Polygon
    chairs: list[Box] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TableZone":
        chairs = [tuple(map(float, c)) for c in d.get("chairs", [])]
        return cls(
            id=d["id"],
            name=d.get("name", d["id"]),
            seats=int(d.get("seats") or len(chairs) or 4),
            zone=d["zone"],
            surface=d.get("surface") or d["zone"],
            chairs=chairs,  # type: ignore[arg-type]
        )


@dataclass
class TableObs:
    """Observasi mentah satu meja pada satu frame."""

    person_ids: list[int] = field(default_factory=list)
    plates: int = 0
    glasses: int = 0
    seat_flags: list[bool] = field(default_factory=list)  # per kursi: ada orang?


class ZoneMap:
    def __init__(self, tables: list[TableZone]):
        self.tables = tables

    def assign(self, dets: list[Detection]) -> dict[str, TableObs]:
        out = {t.id: TableObs(seat_flags=[False] * len(t.chairs)) for t in self.tables}
        for d in dets:
            c = box_center(d.box)
            for t in self.tables:
                if d.group == "person":
                    if d.track_id is None or not point_in_polygon(c, t.zone):
                        continue
                    obs = out[t.id]
                    obs.person_ids.append(d.track_id)
                    # Kursi terisi kalau titik bawah-tengah badan orang ada di kotak kursi (diperbesar sedikit).
                    hip = (c[0], d.box[1] + (d.box[3] - d.box[1]) * 0.75)
                    for i, chair in enumerate(t.chairs):
                        if point_in_box(hip, expand_box(chair, 0.25)):
                            obs.seat_flags[i] = True
                    break
                if d.group in ("plate", "glass") and point_in_polygon(c, t.surface):
                    if d.group == "plate":
                        out[t.id].plates += 1
                    else:
                        out[t.id].glasses += 1
                    break
        return out
