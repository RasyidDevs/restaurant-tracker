// Data dummy. Nanti diganti dengan data dari backend CV (REST / WebSocket).

export type TableStatus = 'kosong' | 'terisi' | 'reserved' | 'segera-kosong' | 'perlu-dibersihkan'

export interface DiningTable {
  id: string
  name: string
  seats: number
  zone: 'Indoor' | 'Outdoor' | 'VIP'
  status: TableStatus
  people: number // #4 jumlah orang
  durationMin: number // #2 lama di meja
  plates: number // #5 piring
  glasses: number // #5 gelas
  reservedFor?: string // #3
  reservedAt?: string
  estFreeMin?: number // #7 estimasi segera kosong (menit)
  estFreeConfidence?: number // 0-100
  estFreeReason?: string // alasan estimasi (dari backend)
  phase?: string // fase makan saat ini (dari backend)
  outsideFood?: boolean // #4 makanan dari luar
  idleDishesMin?: number // #8 piring tanpa orang (menit)
}

export const tables: DiningTable[] = [
  { id: 'T1', name: 'Meja 1', seats: 2, zone: 'Indoor', status: 'terisi', people: 2, durationMin: 34, plates: 2, glasses: 2, estFreeMin: 18, estFreeConfidence: 72 },
  { id: 'T2', name: 'Meja 2', seats: 4, zone: 'Indoor', status: 'segera-kosong', people: 3, durationMin: 72, plates: 3, glasses: 4, estFreeMin: 4, estFreeConfidence: 91 },
  { id: 'T3', name: 'Meja 3', seats: 4, zone: 'Indoor', status: 'kosong', people: 0, durationMin: 0, plates: 0, glasses: 0 },
  { id: 'T4', name: 'Meja 4', seats: 6, zone: 'Indoor', status: 'terisi', people: 5, durationMin: 51, plates: 3, glasses: 5, estFreeMin: 25, estFreeConfidence: 64, outsideFood: true },
  { id: 'T5', name: 'Meja 5', seats: 2, zone: 'Indoor', status: 'reserved', people: 0, durationMin: 0, plates: 0, glasses: 0, reservedFor: 'Bpk. Andi', reservedAt: '19:30' },
  { id: 'T6', name: 'Meja 6', seats: 4, zone: 'Indoor', status: 'perlu-dibersihkan', people: 0, durationMin: 0, plates: 4, glasses: 3, idleDishesMin: 7 },
  { id: 'T7', name: 'Meja 7', seats: 4, zone: 'Outdoor', status: 'terisi', people: 4, durationMin: 18, plates: 4, glasses: 4, estFreeMin: 40, estFreeConfidence: 58 },
  { id: 'T8', name: 'Meja 8', seats: 2, zone: 'Outdoor', status: 'kosong', people: 0, durationMin: 0, plates: 0, glasses: 0 },
  { id: 'T9', name: 'Meja 9', seats: 4, zone: 'Outdoor', status: 'segera-kosong', people: 2, durationMin: 88, plates: 2, glasses: 2, estFreeMin: 6, estFreeConfidence: 84 },
  { id: 'T10', name: 'Meja 10', seats: 6, zone: 'Outdoor', status: 'perlu-dibersihkan', people: 0, durationMin: 0, plates: 5, glasses: 6, idleDishesMin: 12 },
  { id: 'T11', name: 'VIP 1', seats: 8, zone: 'VIP', status: 'reserved', people: 0, durationMin: 0, plates: 0, glasses: 0, reservedFor: 'Ibu Sari (Arisan)', reservedAt: '20:00' },
  { id: 'T12', name: 'VIP 2', seats: 8, zone: 'VIP', status: 'terisi', people: 7, durationMin: 96, plates: 6, glasses: 8, estFreeMin: 15, estFreeConfidence: 69 },
]

export const tableStatusMeta: Record<
  TableStatus,
  { label: string; dot: string; ring: string; bg: string }
> = {
  kosong: { label: 'Kosong', dot: 'bg-emerald-500', ring: 'border-emerald-300 dark:border-emerald-500/40', bg: 'bg-emerald-50 dark:bg-emerald-500/5' },
  terisi: { label: 'Terisi', dot: 'bg-indigo-500', ring: 'border-indigo-300 dark:border-indigo-500/40', bg: 'bg-indigo-50 dark:bg-indigo-500/5' },
  reserved: { label: 'Reserved', dot: 'bg-violet-500', ring: 'border-violet-300 border-dashed dark:border-violet-500/50', bg: 'bg-violet-50 dark:bg-violet-500/5' },
  'segera-kosong': { label: 'Segera Kosong', dot: 'bg-amber-500', ring: 'border-amber-300 dark:border-amber-500/50', bg: 'bg-amber-50 dark:bg-amber-500/5' },
  'perlu-dibersihkan': { label: 'Perlu Dibersihkan', dot: 'bg-rose-500', ring: 'border-rose-300 dark:border-rose-500/50', bg: 'bg-rose-50 dark:bg-rose-500/5' },
}

// #1 Waiting time setelah pesan
export type OrderStatus = 'menunggu' | 'dimasak' | 'diantar'

export interface Order {
  id: string
  table: string
  items: string[]
  orderedAt: string
  waitMin: number
  targetMin: number
  status: OrderStatus
}

export const orders: Order[] = [
  { id: 'ORD-1042', table: 'VIP 2', items: ['Nasi Goreng Spesial x3', 'Es Teh x4'], orderedAt: '18:42', waitMin: 27, targetMin: 20, status: 'dimasak' },
  { id: 'ORD-1043', table: 'Meja 4', items: ['Ayam Bakar x2', 'Jus Alpukat x2'], orderedAt: '18:50', waitMin: 19, targetMin: 20, status: 'dimasak' },
  { id: 'ORD-1044', table: 'Meja 7', items: ['Mie Ayam x4', 'Es Jeruk x4'], orderedAt: '18:55', waitMin: 14, targetMin: 15, status: 'menunggu' },
  { id: 'ORD-1045', table: 'Meja 1', items: ['Sate Ayam x1', 'Kopi Susu x2'], orderedAt: '19:01', waitMin: 8, targetMin: 15, status: 'menunggu' },
  { id: 'ORD-1041', table: 'Meja 2', items: ['Soto Betawi x3'], orderedAt: '18:31', waitMin: 12, targetMin: 15, status: 'diantar' },
  { id: 'ORD-1040', table: 'Meja 9', items: ['Bakso x2', 'Teh Manis x2'], orderedAt: '18:20', waitMin: 9, targetMin: 15, status: 'diantar' },
]

export const waitingTrend = [
  { jam: '11:00', rata: 9, target: 15 },
  { jam: '12:00', rata: 16, target: 15 },
  { jam: '13:00', rata: 18, target: 15 },
  { jam: '14:00', rata: 11, target: 15 },
  { jam: '15:00', rata: 8, target: 15 },
  { jam: '16:00', rata: 10, target: 15 },
  { jam: '17:00', rata: 13, target: 15 },
  { jam: '18:00', rata: 17, target: 15 },
  { jam: '19:00', rata: 21, target: 15 },
]

export const occupancyTrend = [
  { jam: '11:00', okupansi: 35 },
  { jam: '12:00', okupansi: 82 },
  { jam: '13:00', okupansi: 90 },
  { jam: '14:00', okupansi: 55 },
  { jam: '15:00', okupansi: 30 },
  { jam: '16:00', okupansi: 38 },
  { jam: '17:00', okupansi: 60 },
  { jam: '18:00', okupansi: 78 },
  { jam: '19:00', okupansi: 83 },
]

export const dwellDistribution = [
  { rentang: '<15m', meja: 3 },
  { rentang: '15-30m', meja: 9 },
  { rentang: '30-45m', meja: 14 },
  { rentang: '45-60m', meja: 11 },
  { rentang: '60-90m', meja: 6 },
  { rentang: '>90m', meja: 2 },
]

// Alerts (#4 makanan luar, #8 piring tanpa orang, #9 parkir)
export type AlertType = 'makanan-luar' | 'piring-tanpa-orang' | 'parkir-lama' | 'waiting-lama' | 'reservasi'
export type Severity = 'tinggi' | 'sedang' | 'rendah'

export interface AlertItem {
  id: string
  type: AlertType
  severity: Severity
  title: string
  description: string
  location: string
  time: string
  camera: string
  resolved?: boolean
}

export const alerts: AlertItem[] = [
  { id: 'A1', type: 'piring-tanpa-orang', severity: 'tinggi', title: 'Piring tanpa orang > 5 menit', description: '5 piring & 6 gelas terdeteksi, tidak ada orang selama 12 menit.', location: 'Meja 10', time: '19:08', camera: 'CAM-03' },
  { id: 'A2', type: 'makanan-luar', severity: 'sedang', title: 'Makanan/minuman dari luar', description: 'Terdeteksi 1 cup minuman bermerek lain dan 1 kantong plastik makanan.', location: 'Meja 4', time: '19:05', camera: 'CAM-01' },
  { id: 'A3', type: 'parkir-lama', severity: 'tinggi', title: 'Mobil parkir terlalu lama', description: 'B 1234 XYZ sudah parkir 4j 12m (batas 3 jam) tanpa terdeteksi masuk restoran.', location: 'Slot C-03', time: '19:02', camera: 'CAM-P1' },
  { id: 'A4', type: 'piring-tanpa-orang', severity: 'sedang', title: 'Piring tanpa orang > 5 menit', description: '4 piring & 3 gelas, tidak ada orang selama 7 menit.', location: 'Meja 6', time: '19:03', camera: 'CAM-01' },
  { id: 'A5', type: 'waiting-lama', severity: 'sedang', title: 'Waiting time melewati target', description: 'Pesanan ORD-1042 sudah menunggu 27 menit (target 20 menit).', location: 'VIP 2', time: '19:09', camera: 'CAM-04' },
  { id: 'A6', type: 'parkir-lama', severity: 'rendah', title: 'Motor parkir mendekati batas', description: 'D 4567 AB sudah parkir 1j 50m (batas 2 jam).', location: 'Slot M-07', time: '18:58', camera: 'CAM-P2' },
  { id: 'A7', type: 'reservasi', severity: 'rendah', title: 'Reservasi 15 menit lagi', description: 'Meja 5 untuk Bpk. Andi pukul 19:30. Meja sudah siap.', location: 'Meja 5', time: '19:15', camera: 'CAM-01' },
  { id: 'A8', type: 'makanan-luar', severity: 'rendah', title: 'Makanan/minuman dari luar', description: 'Botol air mineral dari luar terdeteksi.', location: 'Meja 7', time: '18:40', camera: 'CAM-02', resolved: true },
]

// #9 Parkiran
export interface ParkingSlot {
  id: string
  type: 'mobil' | 'motor'
  plate?: string
  durationMin: number
  limitMin: number
}

export const parkingSlots: ParkingSlot[] = [
  { id: 'C-01', type: 'mobil', plate: 'B 2201 KLM', durationMin: 45, limitMin: 180 },
  { id: 'C-02', type: 'mobil', plate: 'B 8812 TRA', durationMin: 102, limitMin: 180 },
  { id: 'C-03', type: 'mobil', plate: 'B 1234 XYZ', durationMin: 252, limitMin: 180 },
  { id: 'C-04', type: 'mobil', durationMin: 0, limitMin: 180 },
  { id: 'C-05', type: 'mobil', plate: 'D 1999 QW', durationMin: 160, limitMin: 180 },
  { id: 'C-06', type: 'mobil', durationMin: 0, limitMin: 180 },
  { id: 'C-07', type: 'mobil', plate: 'B 7070 OP', durationMin: 22, limitMin: 180 },
  { id: 'C-08', type: 'mobil', plate: 'F 3321 GH', durationMin: 195, limitMin: 180 },
  { id: 'M-01', type: 'motor', plate: 'B 3456 UJ', durationMin: 30, limitMin: 120 },
  { id: 'M-02', type: 'motor', plate: 'B 9012 IK', durationMin: 64, limitMin: 120 },
  { id: 'M-03', type: 'motor', durationMin: 0, limitMin: 120 },
  { id: 'M-04', type: 'motor', plate: 'B 1122 LL', durationMin: 12, limitMin: 120 },
  { id: 'M-05', type: 'motor', plate: 'B 5544 MN', durationMin: 140, limitMin: 120 },
  { id: 'M-06', type: 'motor', durationMin: 0, limitMin: 120 },
  { id: 'M-07', type: 'motor', plate: 'D 4567 AB', durationMin: 110, limitMin: 120 },
  { id: 'M-08', type: 'motor', plate: 'B 6677 OP', durationMin: 55, limitMin: 120 },
  { id: 'M-09', type: 'motor', plate: 'B 8899 QR', durationMin: 8, limitMin: 120 },
  { id: 'M-10', type: 'motor', durationMin: 0, limitMin: 120 },
  { id: 'M-11', type: 'motor', plate: 'B 2468 ST', durationMin: 92, limitMin: 120 },
  { id: 'M-12', type: 'motor', plate: 'B 1357 UV', durationMin: 40, limitMin: 120 },
]

// #6 AI untuk action dari data AI
export interface Insight {
  id: string
  priority: Severity
  title: string
  reason: string
  actions: string[]
  sources: string[]
  impact: string
}

export const insights: Insight[] = [
  {
    id: 'I1',
    priority: 'tinggi',
    title: 'Bersihkan Meja 10 & Meja 6 sekarang',
    reason: 'Piring terdeteksi tanpa orang selama 12 dan 7 menit. Ada 3 grup sedang antre di pintu masuk.',
    actions: ['Kirim waiter ke Meja 10 (prioritas)', 'Lanjut ke Meja 6', 'Arahkan antrean grup 4–6 orang ke Meja 10'],
    sources: ['Piring tanpa orang', 'Jumlah orang', 'Okupansi'],
    impact: 'Potensi +2 meja tersedia dalam 5 menit',
  },
  {
    id: 'I2',
    priority: 'tinggi',
    title: 'Dapur kewalahan: waiting time naik 31%',
    reason: 'Rata-rata waktu tunggu jam 19:00 adalah 21 menit (target 15). 2 pesanan melewati target.',
    actions: ['Prioritaskan ORD-1042 (VIP 2)', 'Tambah 1 staf dapur di jam 18:00–20:00', 'Tawarkan minuman gratis ke VIP 2'],
    sources: ['Waiting time', 'Jumlah orang'],
    impact: 'Estimasi turun ke 16 menit dalam 30 menit',
  },
  {
    id: 'I3',
    priority: 'sedang',
    title: 'Meja 2 & Meja 9 segera kosong',
    reason: 'Pelanggan sudah >70 menit, piring habis, dan pola gerakan menunjukkan bersiap pergi (confidence 84–91%).',
    actions: ['Siapkan bill untuk Meja 2 & 9', 'Beri tahu antrean: estimasi 5 menit'],
    sources: ['Estimasi bangku kosong', 'Lama di meja', 'Piring & gelas'],
    impact: 'Waktu tunggu antrean -6 menit',
  },
  {
    id: 'I4',
    priority: 'sedang',
    title: 'Upsell minuman di Meja 4',
    reason: 'Jumlah gelas (5) sama dengan jumlah orang, tapi ada minuman dari luar. Piring 3 untuk 5 orang.',
    actions: ['Tawarkan menu minuman/dessert', 'Ingatkan kebijakan makanan dari luar dengan sopan'],
    sources: ['Orang vs piring & gelas', 'Makanan dari luar'],
    impact: 'Potensi +Rp85.000',
  },
  {
    id: 'I5',
    priority: 'rendah',
    title: 'Mobil B 1234 XYZ melewati batas parkir',
    reason: 'Parkir 4j 12m, tidak ada pelanggan terkait yang terdeteksi di meja.',
    actions: ['Minta juru parkir verifikasi', 'Terapkan tarif parkir tambahan'],
    sources: ['Parkiran'],
    impact: '1 slot mobil kembali tersedia',
  },
]

export const cameras = [
  { id: 'CAM-01', name: 'Area Indoor A', status: 'online', fps: 24, detections: 14 },
  { id: 'CAM-02', name: 'Area Outdoor', status: 'online', fps: 22, detections: 9 },
  { id: 'CAM-03', name: 'Area Indoor B', status: 'online', fps: 25, detections: 11 },
  { id: 'CAM-04', name: 'Ruang VIP', status: 'online', fps: 20, detections: 15 },
  { id: 'CAM-P1', name: 'Parkir Mobil', status: 'online', fps: 15, detections: 6 },
  { id: 'CAM-P2', name: 'Parkir Motor', status: 'offline', fps: 0, detections: 0 },
] as const
