"""Penghalus hitungan objek per meja.

Hitungan mentah per frame naik-turun karena objek tertutup tangan/orang
atau deteksi yang berkedip. StableCount hanya menerima angka baru kalau
angka itu menjadi modus jendela waktu dan bertahan selama `hold_s` detik.
Waktu perubahan dimundurkan ke saat angka baru pertama kali dominan,
supaya timestamp kedatangan piring/gelas tetap akurat.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass


@dataclass
class Change:
    old: int
    new: int
    at: float  # waktu (detik) angka baru mulai dominan


class StableCount:
    def __init__(self, window_s: float = 3.0, hold_s: float = 3.0, initial: int = 0):
        self.window_s = window_s
        self.hold_s = hold_s
        self.samples: deque[tuple[float, int]] = deque()
        self.value = initial
        self._candidate = initial
        self._candidate_since: float | None = None

    def update(self, t: float, raw: int) -> Change | None:
        self.samples.append((t, raw))
        while self.samples and t - self.samples[0][0] > self.window_s:
            self.samples.popleft()

        counts = Counter(v for _, v in self.samples)
        top = max(counts.values())
        # Kalau seri, pilih angka yang sama dengan nilai stabil sekarang (lebih konservatif).
        mode = self.value if counts.get(self.value) == top else max(
            (v for v, c in counts.items() if c == top)
        )

        if mode != self._candidate or self._candidate_since is None:
            self._candidate = mode
            # Sampel paling awal di jendela yang sudah menunjukkan angka ini.
            self._candidate_since = min(ts for ts, v in self.samples if v == mode)

        if self._candidate == self.value:
            self._candidate_since = None
            return None

        since = self._candidate_since if self._candidate_since is not None else t
        if t - since >= self.hold_s:
            change = Change(old=self.value, new=self._candidate, at=since)
            self.value = self._candidate
            self._candidate_since = None
            return change
        return None
