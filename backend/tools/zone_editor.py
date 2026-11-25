"""Gambar zona meja MANUAL di atas frame video, lalu simpan ke config.json.

Alternatif dari tools/auto_layout.py (deteksi meja & kursi otomatis). Zona hasil
alat ini tidak punya data kursi, jadi status kursi terisi/kosong tidak tersedia.

Pemakaian:
  python tools/zone_editor.py --source videos/demo.mp4 [--frame 100]

Kontrol (klik jendela dulu):
  klik kiri   tambah titik polygon
  z           batalkan titik terakhir
  t           ganti mode: ZONE (meja + kursi, untuk orang) / SURFACE (permukaan meja, untuk piring & gelas)
  n           selesai meja ini, lanjut meja berikutnya
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


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, help="video / rtsp / webcam index / gambar")
    p.add_argument("--frame", type=int, default=0, help="nomor frame yang dipakai sebagai latar")
    a = p.parse_args()

    src = int(a.source) if a.source.isdigit() else a.source
    if isinstance(src, str) and Path(src).suffix.lower() in {".jpg", ".jpeg", ".png"}:
        frame = cv2.imread(src)
    else:
        cap = cv2.VideoCapture(src)
        if a.frame:
            cap.set(cv2.CAP_PROP_POS_FRAMES, a.frame)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            sys.exit(f"Tidak bisa membaca frame dari {a.source}")

    tables: list[dict] = []
    cur = {"zone": [], "surface": []}
    mode = ["zone"]

    def on_mouse(event, x, y, *_):
        if event == cv2.EVENT_LBUTTONDOWN:
            cur[mode[0]].append([x, y])

    win = "Zone editor - klik titik, t=mode, n=meja berikutnya, s=simpan"
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
        info = f"Meja {len(tables) + 1} | mode: {mode[0].upper()} | titik zone={len(cur['zone'])} surface={len(cur['surface'])}"
        cv2.putText(img, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
        cv2.putText(img, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.imshow(win, img)

        k = cv2.waitKey(30) & 0xFF
        if k in (ord("q"), 27):
            break
        if k == ord("z") and cur[mode[0]]:
            cur[mode[0]].pop()
        elif k == ord("t"):
            mode[0] = "surface" if mode[0] == "zone" else "zone"
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
                mode[0] = "zone"
            if k == ord("s"):
                base = json.loads((CONFIG if CONFIG.exists() else EXAMPLE).read_text(encoding="utf-8"))
                base["tables"] = tables
                base["source"] = a.source
                CONFIG.write_text(json.dumps(base, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"Tersimpan {len(tables)} meja ke {CONFIG}. Ubah nama/jumlah kursi di file itu bila perlu.")
                break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
