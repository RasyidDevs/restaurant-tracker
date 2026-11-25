"""Deteksi layout statis: meja & kursi -> zona meja otomatis.

Meja dan kursi tidak bergerak, jadi cukup dideteksi pada puluhan frame lalu
dikelompokkan (clustering IoU). Objek yang muncul konsisten di banyak frame
dianggap meja/kursi asli; deteksi sesaat (orang lewat membawa kursi, salah
deteksi) terbuang.

Hasilnya dipakai semua fitur meja:
  surface = kotak meja          -> hitung piring & gelas
  zone    = meja + kursinya     -> hitung orang
  chairs  = kotak tiap kursi    -> kursi terisi/kosong, jumlah kursi = kapasitas
"""

from __future__ import annotations

from statistics import median
from typing import Any

from .geometry import Box, box_center, box_to_polygon, convex_hull, expand_box, iou, point_in_box


def _median_box(boxes: list[Box]) -> Box:
    return tuple(median(b[i] for b in boxes) for i in range(4))  # type: ignore[return-value]


def cluster_static(frames: list[list[Box]], iou_thr: float = 0.45, min_presence: float = 0.4) -> list[Box]:
    """Kelompokkan kotak dari banyak frame; kembalikan kotak median yang cukup sering muncul."""
    clusters: list[dict[str, Any]] = []
    for fi, boxes in enumerate(frames):
        for b in boxes:
            best, best_iou = None, iou_thr
            for c in clusters:
                v = iou(b, c["ref"])
                if v >= best_iou:
                    best, best_iou = c, v
            if best is None:
                clusters.append({"boxes": [b], "frames": {fi}, "ref": b})
            else:
                best["boxes"].append(b)
                best["frames"].add(fi)
                best["ref"] = _median_box(best["boxes"])
    n = max(1, len(frames))
    return [c["ref"] for c in clusters if len(c["frames"]) / n >= min_presence]


def build_layout(tables: list[Box], chairs: list[Box], chair_reach: float = 0.6) -> list[dict[str, Any]]:
    """Pasangkan kursi ke meja terdekat dan bentuk zona tiap meja."""
    # urutkan meja: per baris (atas -> bawah), lalu kiri -> kanan
    row_h = max(1.0, median(b[3] - b[1] for b in tables)) if tables else 1.0
    tables = sorted(tables, key=lambda b: (round(box_center(b)[1] / row_h), box_center(b)[0]))
    assigned: dict[int, list[Box]] = {i: [] for i in range(len(tables))}
    for ch in chairs:
        cx, cy = box_center(ch)
        best, best_d = None, float("inf")
        for i, tb in enumerate(tables):
            if not point_in_box((cx, cy), expand_box(tb, chair_reach)):
                continue
            tx, ty = box_center(tb)
            d = (cx - tx) ** 2 + (cy - ty) ** 2
            if d < best_d:
                best, best_d = i, d
        if best is not None:
            assigned[best].append(ch)

    out = []
    for i, tb in enumerate(tables):
        chs = assigned[i]
        pts = [tuple(p) for p in box_to_polygon(expand_box(tb, 0.15))]
        for ch in chs:
            pts += [tuple(p) for p in box_to_polygon(expand_box(ch, 0.1))]
        zone = convex_hull(pts) if chs else box_to_polygon(expand_box(tb, 0.5))
        out.append(
            {
                "id": f"T{i + 1}",
                "name": f"Meja {i + 1}",
                "seats": len(chs) or 4,
                "zone": [[round(x), round(y)] for x, y in zone],
                "surface": [[round(x), round(y)] for x, y in box_to_polygon(tb)],
                "chairs": [[round(v) for v in ch] for ch in chs],
            }
        )
    return out
