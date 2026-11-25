"""MOCK: observasi makanan/minuman dari luar untuk mode simulasi.

Belum ada model yang dilatih untuk membedakan barang restoran vs barang dari
luar, jadi mode `--source simulate` memakai generator ini. Semua alert dari
sumber ini diberi label source="mock" oleh OutsideFoodFeature.

Skenario acak per meja (hanya saat ada orang):
  - kadang pelanggan membawa cup/botol/kantong; objek terlihat beberapa menit,
    berkedip ~25% frame (tertutup tangan), confidence ~0.55-0.85
  - salah deteksi sesaat (1-3 detik) -> harus tersaring oleh min_persist_s
  - deteksi ber-confidence rendah    -> harus tersaring oleh conf_threshold

Untuk model asli tidak perlu file ini: tambahkan grup outside_* di
config.classes dan worker meneruskan deteksinya ke OutsideFoodFeature.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .outside_food import KINDS, OutsideObs


@dataclass
class _Episode:
    kind: str
    start: float
    end: float
    conf: float
    flicker: float


class OutsideFoodMock:
    def __init__(self, table_ids: list[str], seed: int = 7, rate_per_hour: float = 1.2):
        self.rng = random.Random(seed)
        self.rate = rate_per_hour / 3600  # peluang episode per detik saat meja terisi
        self.episodes: dict[str, list[_Episode]] = {tid: [] for tid in table_ids}
        self.last_t: float | None = None

    def obs(self, t: float, people: dict[str, int]) -> dict[str, list[OutsideObs]]:
        dt = 0.0 if self.last_t is None else max(0.0, t - self.last_t)
        self.last_t = t
        r = self.rng
        out: dict[str, list[OutsideObs]] = {}
        for tid, eps in self.episodes.items():
            eps[:] = [e for e in eps if e.end > t]
            if people.get(tid, 0) > 0 and r.random() < self.rate * dt:
                kind = r.choice(list(KINDS))
                if r.random() < 0.35:  # salah deteksi sesaat
                    eps.append(_Episode(kind, t, t + r.uniform(1, 3), r.uniform(0.5, 0.8), 0.1))
                else:
                    eps.append(_Episode(kind, t, t + r.uniform(3, 15) * 60, r.uniform(0.55, 0.85), 0.25))
            seen = [
                OutsideObs(e.kind, max(0.05, min(0.99, r.gauss(e.conf, 0.06))))
                for e in eps
                if e.start <= t and r.random() >= e.flicker
            ]
            if people.get(tid, 0) > 0 and r.random() < 0.01:  # derau confidence rendah
                seen.append(OutsideObs(r.choice(list(KINDS)), r.uniform(0.1, 0.35)))
            if seen:
                out[tid] = seen
        return out
