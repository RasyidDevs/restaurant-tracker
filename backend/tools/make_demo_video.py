"""Buat video demo waiting time (komposit) + config demo.

Klip stok gratis (Mixkit) terlalu pendek dan kameranya bergerak, jadi tidak bisa
menunjukkan satu siklus waiting time penuh. Alat ini menempel potongan foto ASLI
(orang, gelas, piring) dari klip Mixkit ke adegan 2 meja dengan kamera diam,
mengikuti skenario berwaktu. Deteksinya tetap dilakukan YOLO sungguhan.

Ini video REKAYASA untuk demo alur. Untuk lomba, rekam video asli (lihat README).

  python tools/make_demo_video.py

Hasil:
  videos/demo_waiting.mp4      video demo ±3 menit
  videos/demo_sprites/*.png    potongan objek yang dipakai
  config/demo.json             config dengan zona meja & ambang waktu dipercepat
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
VIDEOS = BACKEND / "videos"
SPRITES = VIDEOS / "demo_sprites"
W, H, FPS = 1280, 720, 10
DURATION = 190

CLIPS = {  # klip gratis Mixkit (lisensi Mixkit Free License)
    "4385": "https://assets.mixkit.co/videos/4385/4385-720.mp4",
    "43248": "https://assets.mixkit.co/videos/43248/43248-720.mp4",
    "4672": "https://assets.mixkit.co/videos/4672/4672-720.mp4",
    "205": "https://assets.mixkit.co/videos/205/205-720.mp4",
}


# --------------------------------------------------------------- aset sumber
def ensure_clips() -> None:
    VIDEOS.mkdir(exist_ok=True)
    for cid, url in CLIPS.items():
        p = VIDEOS / f"mixkit-{cid}.mp4"
        if not p.exists():
            print(f"Mengunduh {url}")
            urllib.request.urlretrieve(url, p)


def frame_at(cid: str, frac: float) -> np.ndarray:
    c = cv2.VideoCapture(str(VIDEOS / f"mixkit-{cid}.mp4"))
    n = int(c.get(cv2.CAP_PROP_FRAME_COUNT))
    c.set(cv2.CAP_PROP_POS_FRAMES, int(n * frac))
    ok, f = c.read()
    c.release()
    if not ok:
        sys.exit(f"Gagal membaca frame mixkit-{cid}")
    return f


def _cutout(img: np.ndarray, mask: np.ndarray, box) -> np.ndarray:
    """Potong objek dengan alpha dari mask segmentasi -> BGRA."""
    x1, y1, x2, y2 = (int(v) for v in box)
    m = cv2.GaussianBlur((mask[y1:y2, x1:x2] * 255).astype(np.uint8), (5, 5), 0)
    return np.dstack([img[y1:y2, x1:x2], m])


def _ellipse_cutout(img: np.ndarray, box) -> np.ndarray:
    """Piring berbentuk elips: potong kotak lalu beri mask elips."""
    x1, y1, x2, y2 = (int(v) for v in box)
    c = img[y1:y2, x1:x2]
    h, w = c.shape[:2]
    m = np.zeros((h, w), np.uint8)
    cv2.ellipse(m, (w // 2, h // 2), (w // 2 - 2, h // 2 - 2), 0, 0, 360, 255, -1)
    return np.dstack([c, cv2.GaussianBlur(m, (7, 7), 0)])


def extract_sprites() -> dict[str, list[np.ndarray]]:
    """Potong orang & cangkir dengan segmentasi (YOLO-seg), piring dengan YOLO-World."""
    from ultralytics import YOLO, YOLOWorld

    seg = YOLO("yolo11s-seg.pt")

    def segment(img, want: set[str]):
        r = seg.predict(img, conf=0.3, imgsz=1280, retina_masks=True, verbose=False)[0]
        out = []
        if r.masks is None:
            return out
        for b, c, mk in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.cls.cpu().numpy(), r.masks.data.cpu().numpy()):
            name = seg.names[int(c)]
            if name in want:
                out.append((name, b, mk))
        return out

    sprites: dict[str, list[np.ndarray]] = {"person": [], "plate": [], "glass": []}

    # Orang: wanita di klip 43248 (orang paling kanan), dipotong persis mengikuti siluetnya.
    # Bagian bawah (tangan + piring kue) dibuang supaya tidak terhitung sebagai piring di meja.
    f = frame_at("43248", 0.5)
    people = [d for d in segment(f, {"person"}) if (d[1][2] - d[1][0]) * (d[1][3] - d[1][1]) > 40_000]
    _, b, mk = max(people, key=lambda d: d[1][0])
    woman = _cutout(f, mk, b)
    woman = woman[: int(woman.shape[0] * 0.78)]
    darker = woman.copy()
    darker[..., :3] = cv2.convertScaleAbs(darker[..., :3], alpha=0.8, beta=-5)
    sprites["person"] = [woman, darker]

    # Gelas/cangkir: cangkir putih di meja (klip 205) + gelas minuman (klip 43248, yang tidak dipegang).
    f = frame_at("205", 0.5)
    sprites["glass"] += [_cutout(f, mk, b) for _, b, mk in segment(f, {"cup"}) if b[1] > 250]
    f = frame_at("43248", 0.5)
    sprites["glass"] += [_cutout(f, mk, b) for _, b, mk in segment(f, {"cup", "wine glass"}) if b[0] > 1000]

    # Piring: COCO tidak punya kelas piring, pakai YOLO-World lalu mask elips.
    world = YOLOWorld("yolov8s-worldv2.pt")
    world.set_classes(["plate"])
    f = frame_at("4672", 0.6)
    r = world.predict(f, conf=0.2, imgsz=960, verbose=False)[0]
    sprites["plate"] = [_ellipse_cutout(f, b) for b in r.boxes.xyxy.cpu().numpy()]

    SPRITES.mkdir(parents=True, exist_ok=True)
    for k, lst in sprites.items():
        print(f"  sprite {k}: {len(lst)}")
        if not lst:
            sys.exit(f"Tidak menemukan sprite '{k}'")
        for i, s in enumerate(lst):
            cv2.imwrite(str(SPRITES / f"{k}_{i}.png"), s)
    return sprites


# ------------------------------------------------------------------ adegan
def paste(dst: np.ndarray, src: np.ndarray, cx: int, cy_or_bottom: int, *, height=None, width=None, anchor="bottom"):
    """Tempel sprite BGRA dengan alpha. Skala menurut tinggi atau lebar."""
    scale = height / src.shape[0] if height else width / src.shape[1]
    s = cv2.resize(src, (max(1, int(src.shape[1] * scale)), max(1, int(src.shape[0] * scale))))
    h, w = s.shape[:2]
    x1 = cx - w // 2
    y1 = cy_or_bottom - h if anchor == "bottom" else cy_or_bottom - h // 2
    x1c, y1c, x2c, y2c = max(0, x1), max(0, y1), min(W, x1 + w), min(H, y1 + h)
    s = s[y1c - y1 : y2c - y1, x1c - x1 : x2c - x1]
    a = (s[..., 3:4].astype(np.float32)) / 255.0
    roi = dst[y1c:y2c, x1c:x2c].astype(np.float32)
    dst[y1c:y2c, x1c:x2c] = (a * s[..., :3] + (1 - a) * roi).astype(np.uint8)


TABLES = [
    {"id": "T1", "name": "Meja 1", "rect": (30, 330, 480, 600), "seats": [140, 370]},
    {"id": "T2", "name": "Meja 2", "rect": (520, 330, 1250, 600), "seats": [640, 885, 1130]},
]
PERSON_H, PERSON_BOTTOM = 175, 375  # orang duduk di belakang meja, badan bawah tertutup meja

# Skenario (detik). Orang: (datang, pergi, sprite). Item: (muncul, diangkat, jenis, x, y-tengah)
SCRIPT = {
    "T1": {  # 2 orang, pelayanan normal -> selesai otomatis
        "people": [(3, 120, 0), (3, 120, 1)],
        "items": [
            (20, 135, "glass", 110, 420), (20, 135, "glass", 400, 420),
            (38, 135, "plate", 160, 520), (52, 135, "plate", 350, 520),
        ],
        "people2": [(150, DURATION, 1)],  # pelanggan berikutnya datang
    },
    "T2": {  # 3 orang, dapur lambat + 2 piring untuk 3 orang -> alert & konfirmasi waiter
        "people": [(8, 165, 1), (8, 165, 0), (8, 165, 1)],
        "items": [
            (62, 180, "glass", 620, 420), (62, 180, "glass", 885, 420), (62, 180, "glass", 1150, 420),
            (78, 180, "plate", 720, 520), (92, 180, "plate", 1040, 520),
        ],
    },
}


def build_background() -> tuple[np.ndarray, np.ndarray]:
    room = cv2.resize(frame_at("4385", 0.02), (W, H))
    room = cv2.GaussianBlur(room, (0, 0), 6)
    room = cv2.convertScaleAbs(room, alpha=0.55, beta=10)
    wood_src = frame_at("205", 0.02)[470:720, 0:640]  # permukaan meja kayu
    return room, wood_src


def render(sprites) -> list[dict]:
    room, wood = build_background()
    out = cv2.VideoWriter(str(VIDEOS / "demo_waiting.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    persons, plates, glasses = sprites["person"], sprites["plate"], sprites["glass"]
    for fi in range(DURATION * FPS):
        t = fi / FPS
        img = room.copy()
        for tb in TABLES:
            x1, y1, x2, y2 = tb["rect"]
            sc = SCRIPT[tb["id"]]
            people = sc["people"] + sc.get("people2", [])
            for i, (t_in, t_out, sp) in enumerate(people):
                if t_in <= t < t_out:
                    seat = tb["seats"][i % len(tb["seats"])]
                    p = persons[sp % len(persons)]
                    if i % 2:
                        p = cv2.flip(p, 1)
                    paste(img, p, seat, PERSON_BOTTOM, height=PERSON_H)
            img[y1:y2, x1:x2] = cv2.resize(wood, (x2 - x1, y2 - y1))
            cv2.rectangle(img, (x1, y1), (x2, y2), (40, 60, 80), 3)
            for k, (t_in, t_out, kind, cx, cy) in enumerate(sc["items"]):
                if t_in <= t < t_out:
                    if kind == "plate":
                        paste(img, plates[k % len(plates)], cx, cy, width=170, anchor="center")
                    else:
                        g = glasses[0]  # cangkir yang paling konsisten terdeteksi
                        paste(img, cv2.flip(g, 1) if k % 2 else g, cx, cy, height=110, anchor="center")
        cv2.putText(img, f"DEMO REKAYASA  t={int(t // 60):02d}:{int(t % 60):02d}", (20, H - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        out.write(img)
    out.release()

    tables = []
    for tb in TABLES:
        x1, y1, x2, y2 = tb["rect"]
        seats = tb["seats"]
        tables.append(
            {
                "id": tb["id"],
                "name": tb["name"],
                "seats": len(seats),
                "zone": [[x1 - 10, 60], [x2 + 10, 60], [x2 + 10, y2 + 10], [x1 - 10, y2 + 10]],
                # permukaan mulai sedikit di bawah tepi atas meja (tepi tertimpa badan orang)
                "surface": [[x1, y1 + 30], [x2, y1 + 30], [x2, y2], [x1, y2]],
                # kursi = area pinggul orang duduk (bagian badan yang terlihat di atas meja)
                "chairs": [[s - 90, 250, s + 90, 345] for s in seats],
            }
        )
    return tables


def write_demo_config(tables: list[dict]) -> None:
    base = json.loads((BACKEND / "config" / "config.example.json").read_text(encoding="utf-8"))
    base.update(
        {
            "source": "videos/demo_waiting.mp4",
            "conf": 0.2,
            "realtime_playback": True,
            "loop_video": True,  # demo berulang terus
            # ambang waktu dipercepat supaya satu siklus selesai dalam ±3 menit
            "core": {"seated_min_s": 5, "lost_grace_s": 5, "count_window_s": 1.5, "count_hold_s": 1.5},
            "features": {
                "waiting_time": {
                    "empty_grace_s": 15,
                    "require_drinks": True,
                    "alert_no_item_min": 0.75,
                    "alert_partial_min": 1.25,
                    "target_min": 1,
                }
            },
            "tables": tables,
        }
    )
    p = BACKEND / "config" / "demo.json"
    p.write_text(json.dumps(base, indent=2), encoding="utf-8")
    print(f"Config demo: {p}")


def main() -> None:
    ensure_clips()
    print("Memotong sprite dari klip Mixkit ...")
    sprites = extract_sprites()
    print("Merender video demo ...")
    tables = render(sprites)
    write_demo_config(tables)
    print(f"Video demo: {VIDEOS / 'demo_waiting.mp4'} ({DURATION} detik)")


if __name__ == "__main__":
    main()
