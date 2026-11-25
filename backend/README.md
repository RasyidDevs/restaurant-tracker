# Backend CV DineSight

Arsitekturnya dua lapis: **core** (metode pusat, dihitung sekali) dan **features** (aturan tiap fitur, hanya membaca hasil core). Semua fitur jadi memakai angka orang, piring, gelas, dan kursi yang sama.

```
                    ┌──────────────────────── CORE (app/core) ────────────────────────┐
 video/CCTV ──► sources ──► detection ──► zones ──► table_state ──► CoreEvent ──┐   │
 (timestamp     (frame +    (YOLO +       (meja,     (orang menetap,            │   │
  akurat)        waktu)      ByteTrack)    kursi,     piring, gelas, kursi,     │   │
                                           permukaan) occupied/empty since)     │   │
                 layout: deteksi meja & kursi otomatis (sekali, kalibrasi)      │   │
                    └───────────────────────────────────────────────────────────┼───┘
                                                                                ▼
                    ┌────────────────────── FEATURES (app/features) ──────────────────┐
                    │ waiting_time ✅   lama di meja · orang vs piring · piring tanpa  │
                    │                   orang · estimasi kosong · reserved · parkir …  │
                    └──────────────────────────────────────────────────────────────────┘
```

## Metode pusat (core)

| Modul | Metode | Dipakai fitur |
|---|---|---|
| `sources.py` | Frame + **timestamp akurat** (video: dari nomor frame; CCTV: jam dinding) | semua |
| `detection.py` | YOLO + ByteTrack, kelas dipetakan ke grup (`person`, `plate`, `glass`, `chair`, `table`, `car`, `motorcycle`) | semua |
| `layout.py` | **Deteksi meja & kursi otomatis**: deteksi di puluhan frame, clustering IoU, ambil objek yang konsisten, kursi dipasangkan ke meja terdekat | semua fitur meja |
| `zones.py` | Bagi deteksi ke meja: orang → `zone` (meja + kursi), piring/gelas → `surface`, **kursi terisi** jika pinggul orang di kotak kursi | semua fitur meja |
| `tracks.py` | **Dwell tracker**: lama tiap track ID di zona, menyaring orang lewat/waiter | jumlah orang, lama di meja, parkir |
| `smoothing.py` | **Penghitung stabil**: modus 3 dtk + bertahan 3 dtk, waktu perubahan dimundurkan ke kemunculan pertama | piring, gelas, orang |
| `table_state.py` | **Status meja**: `people`, `plates`, `glasses`, `seats_occupied`, `occupied_since`, `empty_since`, riwayat 10 menit, event `occupied/emptied/people/plates/glasses` | semua fitur meja |
| `perception.py` | Pengatur: frame → status meja → panggil setiap fitur | semua |

Cara fitur lain memakai core:
- **Jumlah orang di meja** → `table.people`
- **Lama pelanggan di meja** → `table.occupied_for_s()`
- **Orang vs piring & gelas** → `table.people`, `table.plates`, `table.glasses`
- **Piring tanpa orang > 5 menit** → `table.empty_for_s() >= 300 and table.plates > 0`
- **Estimasi kursi segera kosong** → `occupied_for_s`, tren `history` piring, `seat_flags`
- **Parkir terlalu lama** → `DwellTracker` per slot parkir + grup `car`/`motorcycle`

### Menambah fitur baru
Buat class dengan `name`, `on_step(t, perception, events)`, dan `snapshot(perception)` di `app/features/`, lalu daftarkan di `app/hub.py`:
```python
self.perception.add_feature(MyFeature(self.perception, ...))
```

## Fitur: waiting time (`features/waiting_time.py`)

| Kejadian | Aksi |
|---|---|
| Meja terisi (core `occupied`) | **START** = orang pertama terlihat; baseline = piring/gelas minimum sejak START |
| Piring/gelas bertambah dari baseline | catat waktu (nilai puncak, jadi item diangkat tidak mengurangi) |
| piring baru ≥ orang **dan** gelas baru ≥ orang | **SELESAI otomatis** = item terakhir tiba |
| Waiter klik "Sudah lengkap" | **SELESAI** = item terakhir tiba (bukan waktu klik) |
| Meja kosong ≥ 2 menit sebelum lengkap | sesi "pelanggan pergi" (tidak masuk rata-rata) |

Alert dicek terus: belum ada sajian > 20 menit, belum lengkap > 25 menit.
Metrik: waktu sampai minuman pertama, makanan pertama, dan lengkap.

> Karena START = saat duduk, waiting time **sudah termasuk waktu baca menu dan memesan**. Kalau nanti ada data kasir, cukup ganti START ke waktu pesanan.

## Menjalankan

```bash
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
.venv\Scripts\python -m pip install -r requirements.txt
copy config\config.example.json config\config.json
```

**Tanpa kamera (simulasi):** `.venv\Scripts\python -m app.main --source simulate`

**Demo dengan YOLO sungguhan (video komposit ±3 menit, berulang):**
```bash
.venv\Scripts\python tools\make_demo_video.py          # sekali: unduh klip Mixkit, buat videos/demo_waiting.mp4 + config/demo.json
.venv\Scripts\python -m app.main --config config/demo.json
```
Video demo menempel potongan foto asli (orang, cangkir, piring dari klip gratis Mixkit) ke adegan 2 meja dengan kamera diam. Ambang waktunya dipercepat (duduk 5 dtk, alert 45/75 dtk, target 1 menit).
Skenario: Meja 1 (2 orang) dilayani normal dan selesai otomatis ±49 dtk. Meja 2 (3 orang) dapur lambat, sehingga muncul alert "belum disajikan", lalu hanya 2 dari 3 piring tiba, sehingga muncul alert "belum lengkap" (coba klik **Sudah lengkap** di dashboard).
Ini video **rekayasa** untuk menunjukkan alur. Untuk lomba, rekam video asli dari sudut kamera yang akan dipakai.

**Dengan 2 video rekaman berbeda (meja + parkiran):**
```bash
# 1. kalibrasi meja (opsional otomatis / manual)
.venv\Scripts\python tools\auto_layout.py --source videos\demo_meja.mp4
# 2. kalibrasi slot parkir (opsional; jika dilewati, kendaraan diam dideteksi otomatis sebagai auto-slot)
.venv\Scripts\python tools\zone_editor.py --mode parking --source videos\demo_parkir.mp4
# 3. jalankan kedua video sekaligus
.venv\Scripts\python -m app.main --source videos\demo_meja.mp4 --parking-source videos\demo_parkir.mp4
```
CCTV: `--source rtsp://... --parking-source rtsp://...`

Dashboard: `npm run dev` di folder root, lalu buka halaman **Waiting Time**, **Parkiran**, atau **Alert** (Vite mem-proxy `/api` dan `/ws` ke port 8000).

Kecepatan terukur: YOLO11s ±57 ms/frame di RTX 4050 (±17 fps), sedangkan pipeline memakai 5 fps.

### Endpoint
| | |
|---|---|
| `GET /api/core/tables`, `WS /ws/core` | status inti tiap meja |
| `GET /api/stream.mjpg` | video meja beranotasi (zona, kursi, deteksi, timer) |
| `GET /api/waiting`, `WS /ws/waiting` | waiting time: sesi aktif, riwayat, alert, statistik |
| `POST /api/sessions/{id}/confirm` | waiter menandai sudah lengkap |
| `GET /api/parking`, `WS /ws/parking` | parkiran: slot mobil/motor, peringatan mendekati & lewat batas, riwayat |
| `GET /api/parking/stream.mjpg` | video parkiran beranotasi (slot, kendaraan, timer) |
| `POST /api/parking/slots/{id}/notify` | kirim peringatan ke juru parkir |
| `GET /api/alerts`, `WS /ws/alerts`, `POST /api/alerts/{id}/resolve` | pusat alert gabungan live |

### Tes
`.venv\Scripts\python -m pytest -q tests`. Isinya `test_core.py` (penghalus, dwell, zona, kursi, status meja, clustering layout) dan `test_waiting_time.py` (8 skenario waiting time).

## Model: kelas `plate`

YOLO COCO bawaan **tidak punya kelas `plate`**. Sementara dipakai `bowl`, sedangkan `cup` dan `wine glass` dipakai untuk gelas. Untuk akurasi:
1. Rekam dari sudut kamera yang akan dipakai (dari atas, agak miring).
2. Anotasi 300–500 frame untuk `person`, `plate`, `glass` (Roboflow / CVAT).
3. `yolo detect train model=yolo11s.pt data=data.yaml epochs=80 imgsz=960`
4. Ubah `"model"` di `config.json` ke `runs/detect/train/weights/best.pt`.

## Pengaturan (`config/config.json`)

`core`: `seated_min_s` (30), `lost_grace_s` (15), `count_window_s` / `count_hold_s` (3/3)
`features.waiting_time`: `empty_grace_s` (120), `require_drinks` (true), `alert_no_item_min` (20), `alert_partial_min` (25), `target_min` (20)
