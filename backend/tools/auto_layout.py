"""Deteksi otomatis meja & kursi dari video, lalu tulis zona meja ke config.json.

Paling akurat kalau video diambil saat restoran sepi (kursi tidak tertutup orang).

  python tools/auto_layout.py --source videos/demo.mp4 [--frames 40] [--dry-run]

Hasil:
  config/config.json       -> bagian "tables" diganti (zone, surface, chairs, seats)
  config/layout_preview.jpg -> gambar untuk dicek; perbaiki manual dengan tools/zone_editor.py bila perlu
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from app.config import BACKEND_DIR, config_path, load_config  # noqa: E402
from app.core.detection import Detector  # noqa: E402
from app.core.layout import build_layout, cluster_static  # noqa: E402


def sample_frames(src: str, n: int) -> list[np.ndarray]:
    cap = cv2.VideoCapture(int(src) if src.isdigit() else src)
    if not cap.isOpened():
        sys.exit(f"Tidak bisa membuka {src}")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frames = []
    if total > 0:  # file video: ambil merata sepanjang video
        for idx in np.linspace(0, total - 1, n).astype(int):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ok, f = cap.read()
            if ok:
                frames.append(f)
    else:  # stream: ambil n frame berturut-turut dengan jeda
        while len(frames) < n:
            for _ in range(10):
                cap.grab()
            ok, f = cap.read()
            if not ok:
                break
            frames.append(f)
    cap.release()
    return frames


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--frames", type=int, default=40)
    p.add_argument("--conf", type=float, default=0.25)
    p.add_argument("--dry-run", action="store_true", help="jangan tulis config, hanya preview")
    a = p.parse_args()

    cfg = load_config()
    det = Detector(cfg.model, cfg.classes, ["table", "chair"], a.conf, cfg.imgsz, cfg.device)
    for w in det.warnings:
        print("PERINGATAN:", w)

    frames = sample_frames(a.source, a.frames)
    if not frames:
        sys.exit(f"Tidak ada frame yang berhasil dibaca dari {a.source}")
    print(f"Mendeteksi meja & kursi pada {len(frames)} frame ...")
    table_boxes, chair_boxes = [], []
    for f in frames:
        dets = det.detect(f)
        table_boxes.append([d.box for d in dets if d.group == "table"])
        chair_boxes.append([d.box for d in dets if d.group == "chair"])

    tables = cluster_static(table_boxes, min_presence=0.5)
    chairs = cluster_static(chair_boxes, min_presence=0.3)  # kursi sering tertutup orang
    layout = build_layout(tables, chairs)
    print(f"Ditemukan {len(tables)} meja, {len(chairs)} kursi:")
    for t in layout:
        print(f"  {t['id']} {t['name']}: {len(t['chairs'])} kursi")

    preview = frames[len(frames) // 2].copy()
    for t in layout:
        cv2.polylines(preview, [np.array(t["zone"], np.int32)], True, (0, 200, 255), 2)
        cv2.polylines(preview, [np.array(t["surface"], np.int32)], True, (0, 255, 0), 2)
        for ch in t["chairs"]:
            cv2.rectangle(preview, tuple(ch[:2]), tuple(ch[2:]), (255, 0, 255), 2)
        x, y = t["surface"][0]
        cv2.putText(preview, f"{t['name']} ({t['seats']})", (x, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    out_img = BACKEND_DIR / "config" / "layout_preview.jpg"
    cv2.imwrite(str(out_img), preview)
    print(f"Preview: {out_img}")

    if a.dry_run:
        return
    path = config_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    data["tables"] = layout
    data["source"] = a.source
    target = BACKEND_DIR / "config" / "config.json"
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Tersimpan ke {target}")


if __name__ == "__main__":
    main()
