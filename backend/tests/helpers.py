from __future__ import annotations

from app.core.perception import Perception
from app.core.table_state import CoreRules
from app.core.zones import TableObs, TableZone
from app.features.waiting_time import WaitingRules, WaitingTimeFeature

FPS = 5

ZONE = TableZone(
    id="T1",
    name="Meja 1",
    seats=4,
    zone=[[0, 0], [100, 0], [100, 100], [0, 100]],
    surface=[[20, 20], [80, 20], [80, 80], [20, 80]],
    chairs=[(0, 30, 20, 70), (80, 30, 100, 70), (30, 0, 70, 20), (30, 80, 70, 100)],
)


class Sim:
    """Menjalankan Perception + fitur waiting time dengan observasi buatan pada 5 fps."""

    def __init__(self, waiting: WaitingRules | None = None, core: CoreRules | None = None):
        self.p = Perception([ZONE], core or CoreRules())
        self.w = WaitingTimeFeature(self.p, waiting or WaitingRules())
        self.p.add_feature(self.w)
        self.t = 0.0
        self.events: list[dict] = []
        self.core_events: list = []

    @property
    def table(self):
        return self.p.tables["T1"]

    def run(self, until: float, ids: list[int], plates: int, glasses: int, noise=None):
        while self.t < until:
            p, g = plates, glasses
            if noise:
                p, g = noise(self.t, p, g)
            obs = TableObs(list(ids), p, g, [i < len(ids) for i in range(4)])
            self.events += self.p.step(self.t, {"T1": obs})
            self.t = round(self.t + 1 / FPS, 3)

    def ended(self):
        return [e for e in self.events if e["type"] == "session_end"]

    def alerts(self):
        return [e for e in self.events if e["type"] == "alert"]
