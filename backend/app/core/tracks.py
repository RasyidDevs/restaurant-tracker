"""Pelacak lama keberadaan (dwell) tiap track ID di dalam satu zona.

Dipakai bersama oleh banyak fitur:
  - orang di meja   -> jumlah orang, lama di meja, waiting time, estimasi kosong
  - kendaraan di slot -> peringatan parkir terlalu lama
"""

from __future__ import annotations


class DwellTracker:
    def __init__(self, min_dwell_s: float, lost_grace_s: float):
        self.min_dwell_s = min_dwell_s  # dianggap "menetap" setelah selama ini (menyaring yang lewat)
        self.lost_grace_s = lost_grace_s  # hilang lebih lama dari ini dianggap pergi
        self.tracks: dict[int, list[float]] = {}  # id -> [first_seen, last_seen]
        self.last_seen_any: float | None = None
        self.last_settled_seen: float | None = None  # terakhir kali orang yang sudah menetap terlihat

    def update(self, t: float, ids: list[int]) -> None:
        if ids:
            self.last_seen_any = t
        for tid in ids:
            if tid in self.tracks:
                self.tracks[tid][1] = t
            else:
                self.tracks[tid] = [t, t]
            first, last = self.tracks[tid]
            if last - first >= self.min_dwell_s:
                self.last_settled_seen = t
        for tid in [k for k, (_, last) in self.tracks.items() if t - last > self.lost_grace_s]:
            del self.tracks[tid]

    def settled(self) -> dict[int, float]:
        """Track yang sudah menetap: {id: first_seen}."""
        return {tid: first for tid, (first, last) in self.tracks.items() if last - first >= self.min_dwell_s}

    def dwell_s(self, tid: int) -> float:
        first, last = self.tracks[tid]
        return last - first
