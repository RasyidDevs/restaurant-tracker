# Makanan/minuman dari luar & AI saran tindakan

Fitur ini dikerjakan oleh Thoriq. Kodenya ada di `app/features/outside_food*.py` dan `app/features/recommendations/`.

## 1. Indikasi makanan & minuman dari luar (`features/outside_food.py`)

```
deteksi outside_* ─► dibagi ke meja (polygon zona) ─► per (meja, jenis objek):
   conf < conf_threshold                     → diabaikan
   terlihat ≥ min_persist_s dan muncul di
   ≥ min_hit_ratio sampel jendela itu        → ALERT (meja, waktu, jenis, confidence)
   tidak terlihat ≥ clear_after_s            → selesai ("objek hilang")
   staf klik "Sudah ditangani"               → selesai, objek yang sama tidak di-alert lagi selama masih terlihat
   alert ulang meja+objek yang sama          → ditahan cooldown_s
   require_occupied                          → kandidat baru hanya kalau ada orang di meja
```

**Sumber deteksi.** Fitur hanya menerima `OutsideObs(kind, conf)` per meja, jadi sumbernya bisa diganti:

| Mode | Sumber | Label |
|---|---|---|
| `--source simulate` | `features/outside_food_mock.py` (episode acak + salah deteksi sesaat + derau confidence rendah) | `source: "mock"` |
| video / CCTV | grup YOLO `outside_*` di `config.classes`, otomatis ikut dideteksi (`config.runtime_groups`) | `source: "cv"` |

Grup bawaan: `outside_bottle`, `outside_cup` (kategori *minuman*), dan `outside_bag`, `outside_box` (kategori *makanan*). Grup baru cukup ditambah di config dengan awalan `outside_`.

> **Batasan model.** YOLO-World/COCO bawaan sulit membedakan cup milik restoran dari cup takeaway luar. Prompt khusus (`takeaway cup`, `plastic bag`, dll.) dan aturan konsistensi di atas mengurangi false alarm, tapi untuk akurasi sebenarnya perlu fine-tune dengan foto dari restoran sendiri (cara melatihnya sama seperti kelas `plate` di README utama). Barang yang memang dijual restoran (mis. air mineral botol) bisa dikecualikan lewat `ignore_kinds`.

**Endpoint**

| | |
|---|---|
| `GET /api/outside-food`, `WS /ws/outside-food` | alert aktif, riwayat, aturan, status meja, statistik |
| `POST /api/outside-food/{id}/resolve` | staf menandai alert sudah ditangani |

**Pengaturan** `features.outside_food`: `conf_threshold` (0.45), `min_persist_s` (8), `min_hit_ratio` (0.6), `clear_after_s` (30), `cooldown_s` (300), `require_occupied` (true), `ignore_kinds` ([]).

## 2. AI saran tindakan (`features/recommendations/`)

| File | Isi |
|---|---|
| `signals.py` | Menggabungkan data tim ke `TeamSignals`: meja dari core (orang, lama duduk, lama kosong, piring, gelas), sesi waiting time, alert makanan luar, reservasi, parkir |
| `rules.py` | Rule engine murni dan deterministik, diurutkan berdasarkan skor (tinggi 300+, sedang 200+, rendah 100+, ditambah urgensi) |
| `llm.py` | Lapisan LLM **opsional** yang hanya menulis ringkasan. Tidak menambah atau mengubah tindakan |
| `providers.py` | Data reservasi & parkir. Backend-nya belum ada, jadi mode simulasi memakai **mock** (`source: "mock"`) |

| Rule | Kondisi | Prioritas |
|---|---|---|
| Bersihkan meja | kosong ≥ `leftover_min` dan masih ada piring/gelas | tinggi |
| Cek dapur | waiting ≥ `waiting_no_item_min`, belum ada sajian | tinggi |
| Lengkapi pesanan | sebagian tersaji, waiting ≥ `waiting_partial_min` | sedang |
| Makanan luar | ada alert aktif di meja | sedang |
| Reservasi | ≤ `reservation_lead_min` lagi: meja terisi / kotor / siap | tinggi / tinggi / rendah |
| Parkir | durasi > batas | sedang |
| Tawarkan bill | duduk ≥ `long_stay_min`, pesanan sudah tersaji | rendah (sedang kalau okupansi ≥ `busy_occupancy`) |

**LLM opsional.** Salin `backend/.env.example` ke `backend/.env`, lalu isi `ANTHROPIC_API_KEY`. `.env` tidak ikut di-commit karena sudah ada di `.gitignore`.
- Model diatur lewat `LLM_MODEL` (default `claude-opus-5-5`; `claude-haiku-5-5` jauh lebih murah).
- API dipanggil di thread latar, paling sering tiap 15 detik dan hanya kalau daftar saran berubah atau sudah lewat `LLM_REFRESH_S`.
- Tanpa key, tanpa paket `anthropic`, atau kalau API error/ditolak, `engine` tetap `"rules"` dan ringkasan rule-based yang dipakai. Status LLM terlihat di `llm` pada respons.
- Matikan sepenuhnya dengan `features.recommendations.llm_enabled: false`.

**Endpoint:** `GET /api/recommendations`, `WS /ws/recommendations`.

**Menyambung fitur Micheal (reservasi/parkir).** Buat class dengan `source` dan `reservations(now, tables)` / `parking(now)` yang mengembalikan `ReservationSignal` / `ParkingSignal`, lalu ganti `MockReservations`/`MockParking` di `hub.py`.

## Dashboard

- **Makanan Luar** (`/makanan-luar`): alert aktif per meja (jenis objek, kategori, confidence, waktu pertama terlihat, badge *mock*), tombol *Sudah ditangani*, status meja, aturan yang aktif, dan riwayat.
- **AI Insight** (`/ai-insight`): ringkasan (rule engine atau + LLM), sumber data per fitur (cv / simulasi / mock / tidak ada), dan saran terurut prioritas. Kalau backend offline, halaman menampilkan contoh dari `data/mock.ts` dengan label mock.

## Tes

`.venv\Scripts\python -m pytest -q tests`:
- `test_outside_food.py`: threshold, kedipan, objek hilang, cooldown, meja kosong, pengecualian, resolve staf, pembagian ke zona.
- `test_recommendations.py`: setiap rule, urutan prioritas, fallback tanpa API key, dan jalur LLM dengan client palsu (tanpa jaringan).
