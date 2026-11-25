"""Gambar zona meja ATAU slot parkir secara manual di atas frame video, lalu simpan ke config.json.

Pemakaian:
  # Kalibrasi meja restoran:
  python tools/zone_editor.py --source videos/meja.mp4 [--frame 100]

  # Kalibrasi slot parkir (untuk video demo parkiran terpisah):
  python tools/zone_editor.py --mode parking --source videos/parkir.mp4 [--frame 50]

Kontrol (klik jendela dulu):
  klik kiri   tambah titik polygon
  z           batalkan titik terakhir
  t           mode tables : ganti ZONE (meja+kursi) / SURFACE (permukaan meja)
              mode parking: ganti jenis slot MOBIL (C-xx) / MOTOR (M-xx)
  n           selesai objek ini, lanjut berikutnya
  s           simpan ke config/config.json lalu keluar
  q / Esc     keluar tanpa simpan
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
CONFIG = BACKEND / "config" / "config.json"
EXAMPLE = BACKEND / "config" / "config.example.json"


def _read_frame(source: str, frame_idx: int) -> np.ndarray:
    src: str | int = int(source) if source.isdigit() else source
    if isinstance(src, str) and Path(src).suffix.lower() in {".jpg", ".jpeg", ".png"}:
        frame = cv2.imread(src)
        if frame is None:
            sys.exit(f"Tidak bisa membaca gambar dari {source}")
        return frame
    cap = cv2.VideoCapture(src)
    if frame_idx:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        sys.exit(f"Tidak bisa membaca frame dari {source}")
    return frame


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, help="video / rtsp / webcam index / gambar")
    p.add_argument("--mode", choices=("tables", "parking"), default="tables", help="jenis zona yang digambar")
    p.add_argument("--frame", type=int, default=0, help="nomor frame yang dipakai sebagai latar")
    a = p.parse_args()

    frame = _read_frame(a.source, a.frame)

    if a.mode == "parking":
        _edit_parking(frame, a.source)
    else:
        _edit_tables(frame, a.source)


def _edit_tables(frame: np.ndarray, source: str) -> None:
    tables: list[dict] = []
    cur: dict[str, list[list[int]]] = {"zone": [], "surface": []}
    submode = ["zone"]

    def on_mouse(event, x, y, *_):
        if event == cv2.EVENT_LBUTTONDOWN:
            cur[submode[0]].append([x, y])

    win = "Zone editor (MEJA) - klik titik, t=zone/surface, n=berikutnya, s=simpan"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(win, on_mouse)

    while True:
        img = frame.copy()
        for t in tables:
            cv2.polylines(img, [np.array(t["zone"], np.int32)], True, (200, 200, 200), 2)
            cv2.polylines(img, [np.array(t["surface"], np.int32)], True, (0, 255, 0), 2)
            cv2.putText(img, t["name"], tuple(t["zone"][0]), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        for key, color in (("zone", (0, 200, 255)), ("surface", (0, 255, 0))):
            pts = cur[key]
            if pts:
                cv2.polylines(img, [np.array(pts, np.int32)], len(pts) > 2, color, 2)
                for pt in pts:
                    cv2.circle(img, tuple(pt), 4, color, -1)
        info = f"Meja {len(tables) + 1} | mode: {submode[0].upper()} | titik zone={len(cur['zone'])} surface={len(cur['surface'])}"
        cv2.putText(img, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
        cv2.putText(img, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.imshow(win, img)

        k = cv2.waitKey(30) & 0xFF
        if k in (ord("q"), 27):
            break
        if k == ord("z") and cur[submode[0]]:
            cur[submode[0]].pop()
        elif k == ord("t"):
            submode[0] = "surface" if submode[0] == "zone" else "zone"
        elif k in (ord("n"), ord("s")):
            if len(cur["zone"]) >= 3:
                n = len(tables) + 1
                tables.append(
                    {
                        "id": f"T{n}",
                        "name": f"Meja {n}",
                        "seats": 4,
                        "zone": cur["zone"],
                        "surface": cur["surface"] if len(cur["surface"]) >= 3 else cur["zone"],
                    }
                )
                cur = {"zone": [], "surface": []}
                submode[0] = "zone"
            if k == ord("s"):
                base = json.loads((CONFIG if CONFIG.exists() else EXAMPLE).read_text(encoding="utf-8"))
                base["tables"] = tables
                base["source"] = source
                CONFIG.write_text(json.dumps(base, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"Tersimpan {len(tables)} meja ke {CONFIG}.")
                break
    cv2.destroyAllWindows()


def _edit_parking(frame: np.ndarray, source: str) -> None:
    slots: list[dict] = []
    pts: list[list[int]] = []
    vtype = ["mobil"]
    seq = {"mobil": 0, "motor": 0}

    def on_mouse(event, x, y, *_):
        if event == cv2.EVENT_LBUTTONDOWN:
            pts.append([x, y])

    win = "Zone editor (PARKIR) - klik titik, t=mobil/motor, n=slot berikutnya, s=simpan"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(win, on_mouse)

    while True:
        img = frame.copy()
        for s in slots:
            col = (235, 160, 30) if s["type"] == "mobil" else (80, 190, 250)
            cv2.polylines(img, [np.array(s["zone"], np.int32)], True, col, 2)
            cv2.putText(img, f"{s['id']} ({s['type']})", tuple(s["zone"][0]), cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
        if pts:
            col = (235, 160, 30) if vtype[0] == "mobil" else (80, 190, 250)
            cv2.polylines(img, [np.array(pts, np.int32)], len(pts) > 2, col, 2)
            for pt in pts:
                cv2.circle(img, tuple(pt), 4, col, -1)
        info = f"Slot #{len(slots) + 1} | jenis (t): {vtype[0].upper()} | titik={len(pts)}"
        cv2.putText(img, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
        cv2.putText(img, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.imshow(win, img)

        k = cv2.waitKey(30) & 0xFF
        if k in (ord("q"), 27):
            break
        if k == ord("z") and pts:
            pts.pop()
        elif k == ord("t"):
            vtype[0] = "motor" if vtype[0] == "mobil" else "mobil"
        elif k in (ord("n"), ord("s")):
            if len(pts) >= 3:
                seq[vtype[0]] += 1
                prefix = "C" if vtype[0] == "mobil" else "M"
                slots.append({"id": f"{prefix}-{seq[vtype[0]]:02d}", "type": vtype[0], "zone": list(pts)})
                pts.clear()
            if k == ord("s"):
                base = json.loads((CONFIG if CONFIG.exists() else EXAMPLE).read_text(encoding="utf-8"))
                base["parking_slots"] = slots
                base["parking_source"] = source
                CONFIG.write_text(json.dumps(base, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"Tersimpan {len(slots)} slot parkir & parking_source='{source}' ke {CONFIG}.")
                break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
