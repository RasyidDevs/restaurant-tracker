"""Rule engine saran tindakan untuk staf.

Setiap rule adalah fungsi murni: (TeamSignals, RecRules) -> list[Recommendation].
Tidak ada I/O, tidak ada waktu dari jam dinding: semua dari `signals.now`,
jadi mudah dites.

Prioritas: tinggi (skor 300+), sedang (200+), rendah (100+). Di dalam satu
prioritas skor bertambah sesuai urgensi (mis. menit lewat batas), lalu
hasil diurutkan dari skor terbesar.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from .signals import TeamSignals

BASE = {"tinggi": 300, "sedang": 200, "rendah": 100}


@dataclass
class RecRules:
    leftover_min: float = 5.0  # meja kosong + piring/gelas tertinggal
    waiting_no_item_min: float = 20.0  # belum ada sajian
    waiting_partial_min: float = 25.0  # sajian belum lengkap
    reservation_lead_min: float = 15.0  # siapkan meja sebelum reservasi
    long_stay_min: float = 90.0  # pelanggan sudah lama, tawarkan bill
    busy_occupancy: float = 0.85  # restoran dianggap ramai

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "RecRules":
        d = d or {}
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Recommendation:
    id: str  # stabil: "<jenis>:<kunci>", supaya UI bisa melacak saran yang sama
    kind: str
    priority: str  # tinggi | sedang | rendah
    score: float
    title: str
    reason: str
    actions: list[str]
    sources: list[str]
    impact: str
    table: str | None = None
    mock: bool = False  # True kalau saran berasal dari data mock
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rec(priority: str, urgency: float, **kw: Any) -> Recommendation:
    return Recommendation(priority=priority, score=round(BASE[priority] + min(99.0, max(0.0, urgency)), 1), **kw)


def _min(s: float) -> int:
    return int(s // 60)


# ------------------------------------------------------------------- rules
def rule_leftover_dishes(sig: TeamSignals, r: RecRules) -> list[Recommendation]:
    """Meja kosong >= leftover_min dan masih ada piring/gelas -> bersihkan."""
    out = []
    reserved_soon = {
        x.table for x in sig.reservations if 0 <= x.at - sig.now <= r.reservation_lead_min * 60 * 2
    }
    busy = sig.occupancy >= r.busy_occupancy
    for t in sig.tables:
        items = t.plates + t.glasses
        if t.people > 0 or items == 0 or t.empty_s < r.leftover_min * 60:
            continue
        m = _min(t.empty_s)
        why = f"Tidak ada orang selama {m} menit, masih ada {t.plates} piring & {t.glasses} gelas."
        if busy:
            why += f" Restoran ramai ({sig.occupancy:.0%} meja terisi)."
        if t.id in reserved_soon:
            why += " Meja ini akan dipakai reservasi."
        out.append(
            _rec(
                "tinggi",
                m + (20 if busy else 0) + (20 if t.id in reserved_soon else 0),
                id=f"bersihkan:{t.id}",
                kind="bersihkan_meja",
                title=f"{t.name} kosong {m} menit dan piring belum diangkat → kirim staf untuk bersihkan",
                reason=why,
                actions=[f"Kirim staf ke {t.name} untuk mengangkat piring & gelas", f"Lap meja lalu tandai {t.name} siap dipakai"],
                sources=["Piring tanpa orang", "Jumlah orang"],
                impact="+1 meja tersedia untuk tamu berikutnya",
                table=t.id,
            )
        )
    return out


def rule_waiting_time(sig: TeamSignals, r: RecRules) -> list[Recommendation]:
    """Waiting time melewati batas -> cek dapur."""
    out = []
    for w in sig.waiting:
        t = sig.table(w.table)
        name = t.name if t else w.table
        m = _min(w.waiting_s)
        if w.status == "menunggu" and w.waiting_s >= r.waiting_no_item_min * 60:
            out.append(
                _rec(
                    "tinggi",
                    m - r.waiting_no_item_min + 10,
                    id=f"waiting:{w.session_id}",
                    kind="cek_dapur",
                    title=f"Waiting time {name} lebih dari {int(r.waiting_no_item_min)} menit → cek dapur",
                    reason=f"{w.people} orang sudah menunggu {m} menit dan belum ada sajian sama sekali.",
                    actions=[f"Cek status pesanan {name} ke dapur", "Beri tahu pelanggan perkiraan waktu saji", "Tawarkan minuman/camilan sambil menunggu"],
                    sources=["Waiting time", "Jumlah orang"],
                    impact="Mencegah komplain & pelanggan pergi",
                    table=w.table,
                    data={"waiting_s": w.waiting_s},
                )
            )
        elif w.status == "sebagian" and w.waiting_s >= r.waiting_partial_min * 60:
            out.append(
                _rec(
                    "sedang",
                    m - r.waiting_partial_min + 10,
                    id=f"waiting:{w.session_id}",
                    kind="lengkapi_pesanan",
                    title=f"Pesanan {name} belum lengkap setelah {m} menit → cek sisa pesanan",
                    reason=f"Baru {w.plates_served}/{w.people} piring dan {w.glasses_served}/{w.people} gelas tersaji.",
                    actions=[f"Cek sisa pesanan {name} di dapur", "Kalau memang berbagi piring, tandai 'Sudah lengkap' di halaman Waiting Time"],
                    sources=["Waiting time", "Orang vs piring & gelas"],
                    impact="Waiting time kembali ke target",
                    table=w.table,
                    data={"waiting_s": w.waiting_s},
                )
            )
    return out


def rule_outside_food(sig: TeamSignals, r: RecRules) -> list[Recommendation]:
    """Alert makanan/minuman dari luar aktif -> dekati dengan sopan."""
    by_table: dict[str, list] = {}
    for o in sig.outside:
        by_table.setdefault(o.table, []).append(o)
    out = []
    for tid, items in by_table.items():
        t = sig.table(tid)
        name = t.name if t else tid
        labels = ", ".join(f"{o.label.lower()} ({o.confidence:.0%})" for o in items)
        out.append(
            _rec(
                "sedang",
                _min(max(o.since_s for o in items)) + 10 * (len(items) - 1),
                id=f"makanan_luar:{tid}",
                kind="makanan_luar",
                title=f"{name} terindikasi membawa makanan/minuman dari luar → dekati dengan sopan",
                reason=f"Terdeteksi konsisten: {labels}.",
                actions=[f"Datangi {name}, cek langsung (deteksi bisa keliru)", "Ingatkan kebijakan makanan dari luar dengan sopan", "Tawarkan menu minuman/dessert restoran"],
                sources=["Makanan dari luar"],
                impact="Kebijakan restoran terjaga, potensi upsell",
                table=tid,
                mock=any(o.source == "mock" for o in items),
            )
        )
    return out


def rule_reservations(sig: TeamSignals, r: RecRules) -> list[Recommendation]:
    """Reservasi dalam reservation_lead_min -> pastikan meja siap."""
    out = []
    mock = sig.data_sources.get("reservasi") == "mock"
    for x in sig.reservations:
        until = x.at - sig.now
        if not 0 <= until <= r.reservation_lead_min * 60:
            continue
        t = sig.table(x.table)
        if t is None:
            continue
        m = max(0, _min(until))
        base = dict(sources=["Reservasi", "Jumlah orang"], table=t.id, mock=mock, data={"at": x.at})
        if t.people > 0:
            out.append(
                _rec(
                    "tinggi",
                    r.reservation_lead_min - m + 10,
                    id=f"reservasi:{t.id}:{int(x.at)}",
                    kind="reservasi_bentrok",
                    title=f"Reservasi {x.guest} di {t.name} {m} menit lagi, meja masih terisi → siapkan meja lain",
                    reason=f"{t.people} orang masih duduk di {t.name} ({_min(t.occupied_s)} menit). Reservasi untuk {x.party_size} orang.",
                    actions=[f"Siapkan meja alternatif untuk {x.party_size} orang", f"Tawarkan bill ke {t.name} dengan sopan"],
                    impact="Tamu reservasi tidak menunggu",
                    **base,
                )
            )
        elif t.plates + t.glasses > 0:
            out.append(
                _rec(
                    "tinggi",
                    r.reservation_lead_min - m + 5,
                    id=f"reservasi:{t.id}:{int(x.at)}",
                    kind="reservasi_belum_siap",
                    title=f"Reservasi {x.guest} di {t.name} {m} menit lagi, meja belum dibersihkan",
                    reason=f"Masih ada {t.plates} piring & {t.glasses} gelas di {t.name}.",
                    actions=[f"Bersihkan {t.name} sekarang", f"Tata meja untuk {x.party_size} orang"],
                    impact="Meja siap saat tamu datang",
                    **base,
                )
            )
        else:
            out.append(
                _rec(
                    "rendah",
                    r.reservation_lead_min - m,
                    id=f"reservasi:{t.id}:{int(x.at)}",
                    kind="reservasi_siap",
                    title=f"Reservasi {x.guest} di {t.name} {m} menit lagi",
                    reason=f"Meja kosong dan bersih. Reservasi untuk {x.party_size} orang.",
                    actions=[f"Pasang tanda 'Reserved' di {t.name}", "Siapkan menu di meja"],
                    impact="Pengalaman tamu reservasi lebih baik",
                    **base,
                )
            )
    return out


def rule_parking(sig: TeamSignals, r: RecRules) -> list[Recommendation]:
    """Kendaraan melewati batas parkir."""
    mock = sig.data_sources.get("parkir") == "mock"
    out = []
    for p in sig.parking:
        if p.duration_min <= p.limit_min:
            continue
        over = p.duration_min - p.limit_min
        h, m = divmod(int(p.duration_min), 60)
        out.append(
            _rec(
                "sedang",
                over / 6,
                id=f"parkir:{p.slot}",
                kind="parkir_lama",
                title=f"{p.kind.capitalize()} {p.plate} parkir {h}j {m}m (batas {int(p.limit_min // 60)} jam) → minta juru parkir cek",
                reason=f"Slot {p.slot} sudah lewat batas {int(over)} menit.",
                actions=["Minta juru parkir verifikasi pemilik kendaraan", "Terapkan aturan parkir tambahan bila bukan pelanggan"],
                sources=["Parkiran"],
                impact="Slot parkir kembali tersedia",
                mock=mock,
            )
        )
    return out


def rule_long_stay(sig: TeamSignals, r: RecRules) -> list[Recommendation]:
    """Pelanggan lama duduk & pesanan sudah tersaji -> tawarkan bill (lebih penting saat ramai)."""
    waiting_tables = {w.table for w in sig.waiting}
    busy = sig.occupancy >= r.busy_occupancy
    out = []
    for t in sig.tables:
        if t.people == 0 or t.id in waiting_tables or t.occupied_s < r.long_stay_min * 60:
            continue
        m = _min(t.occupied_s)
        out.append(
            _rec(
                "sedang" if busy else "rendah",
                (m - r.long_stay_min) / 3,
                id=f"bill:{t.id}",
                kind="tawarkan_bill",
                title=f"{t.name} sudah duduk {m} menit → siapkan bill",
                reason=f"{t.people} orang, pesanan sudah tersaji." + (f" Restoran ramai ({sig.occupancy:.0%})." if busy else ""),
                actions=[f"Tanyakan ke {t.name} apakah ingin pesan lagi atau minta bill", "Siapkan bill"],
                sources=["Lama di meja", "Jumlah orang", "Okupansi"],
                impact="Perputaran meja lebih cepat",
                table=t.id,
            )
        )
    return out


RULES: list[Callable[[TeamSignals, RecRules], list[Recommendation]]] = [
    rule_leftover_dishes,
    rule_waiting_time,
    rule_outside_food,
    rule_reservations,
    rule_parking,
    rule_long_stay,
]


def generate(sig: TeamSignals, rules: RecRules) -> list[Recommendation]:
    """Jalankan semua rule, buang duplikat id, urutkan dari prioritas tertinggi."""
    seen: dict[str, Recommendation] = {}
    for rule in RULES:
        for rec in rule(sig, rules):
            if rec.id not in seen or rec.score > seen[rec.id].score:
                seen[rec.id] = rec
    return sorted(seen.values(), key=lambda x: (-x.score, x.id))


def rule_summary(sig: TeamSignals, recs: list[Recommendation]) -> str:
    occ = sum(1 for t in sig.tables if t.people > 0)
    high = sum(1 for x in recs if x.priority == "tinggi")
    text = f"Okupansi {sig.occupancy:.0%} ({occ}/{len(sig.tables)} meja). "
    if not recs:
        return text + "Tidak ada tindakan yang perlu dilakukan saat ini."
    text += f"Ada {len(recs)} saran tindakan, {high} prioritas tinggi. "
    return text + f"Utamakan: {recs[0].title}."
