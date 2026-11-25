"""Tes rule engine saran tindakan & fallback tanpa API key."""

import pytest

from app.features.recommendations import RecommendationEngine
from app.features.recommendations.llm import LLMSummarizer
from app.features.recommendations.providers import MockParking, MockReservations
from app.features.recommendations.rules import RecRules, generate
from app.features.recommendations.signals import (
    OutsideSignal,
    ParkingSignal,
    ReservationSignal,
    TableSignal,
    TeamSignals,
    WaitingSignal,
)

NOW = 100_000.0
R = RecRules()


def table(tid, people=0, plates=0, glasses=0, occupied_min=0, empty_min=0, seats=4):
    return TableSignal(tid, f"Meja {tid[1:]}", seats, people, plates, glasses, occupied_min * 60, empty_min * 60)


def sig(**kw) -> TeamSignals:
    kw.setdefault("tables", [table("T1"), table("T2")])
    return TeamSignals(now=NOW, data_sources={"reservasi": "mock", "parkir": "cv"}, **kw)


def ids(recs):
    return [r.id for r in recs]


def test_leftover_dishes_after_5_minutes():
    s = sig(tables=[table("T4", plates=3, glasses=2, empty_min=6), table("T5", plates=2, empty_min=4), table("T6", empty_min=30)])
    (rec,) = generate(s, R)
    assert rec.id == "bersihkan:T4" and rec.priority == "tinggi"
    assert rec.title == "Meja 4 kosong 6 menit dan piring belum diangkat → kirim staf untuk bersihkan"


def test_waiting_no_item_and_partial():
    s = sig(
        waiting=[
            WaitingSignal("T2", "S1", 21 * 60, "menunggu", 3, 0, 0),
            WaitingSignal("T1", "S2", 26 * 60, "sebagian", 2, 1, 2),
            WaitingSignal("T1", "S3", 10 * 60, "menunggu", 2, 0, 0),  # masih wajar
        ]
    )
    recs = generate(s, R)
    assert ids(recs) == ["waiting:S1", "waiting:S2"]
    assert recs[0].title == "Waiting time Meja 2 lebih dari 20 menit → cek dapur"
    assert [r.priority for r in recs] == ["tinggi", "sedang"]


def test_outside_food_grouped_per_table_and_mock_flag():
    s = sig(
        outside=[
            OutsideSignal("T1", "OF1", "Cup minuman (takeaway)", "minuman", 0.72, 120, "mock"),
            OutsideSignal("T1", "OF2", "Kantong makanan", "makanan", 0.6, 30, "mock"),
        ]
    )
    (rec,) = generate(s, R)
    assert rec.id == "makanan_luar:T1" and rec.priority == "sedang" and rec.mock
    assert "72%" in rec.reason and "kantong makanan" in rec.reason


def test_reservation_variants():
    s = sig(
        tables=[table("T1", people=2, occupied_min=50), table("T2", plates=1, empty_min=2), table("T3")],
        reservations=[
            ReservationSignal("T1", "Bpk. Andi", NOW + 10 * 60, 2),
            ReservationSignal("T2", "Ibu Sari", NOW + 5 * 60, 4),
            ReservationSignal("T3", "Bpk. Rudi", NOW + 12 * 60, 2),
            ReservationSignal("T3", "Nanti", NOW + 60 * 60, 2),  # masih lama
        ],
    )
    kinds = {r.kind: r for r in generate(s, R)}
    assert set(kinds) == {"reservasi_bentrok", "reservasi_belum_siap", "reservasi_siap"}
    assert kinds["reservasi_bentrok"].priority == "tinggi" and kinds["reservasi_bentrok"].mock
    assert kinds["reservasi_siap"].priority == "rendah"


def test_parking_over_limit_only():
    s = sig(parking=[ParkingSignal("C-03", "mobil", "B 1234 XYZ", 252, 180), ParkingSignal("M-01", "motor", "B 1", 60, 120)])
    (rec,) = generate(s, R)
    assert rec.id == "parkir:C-03" and "4j 12m" in rec.title and not rec.mock


def test_long_stay_priority_rises_when_busy():
    quiet = sig(tables=[table("T1", people=2, occupied_min=95), table("T2"), table("T3")])
    (rec,) = generate(quiet, R)
    assert rec.id == "bill:T1" and rec.priority == "rendah"

    busy = sig(tables=[table("T1", people=2, occupied_min=95), table("T2", people=1, occupied_min=5)])
    (rec,) = generate(busy, R)
    assert rec.priority == "sedang"

    serving = sig(tables=[table("T1", people=2, occupied_min=95)], waiting=[WaitingSignal("T1", "S9", 300, "sebagian", 2, 1, 1)])
    assert generate(serving, R) == []  # masih menunggu pesanan -> jangan tawarkan bill


def test_sorted_by_priority_then_urgency():
    s = sig(
        tables=[table("T1", plates=1, empty_min=6), table("T2", plates=1, empty_min=15), table("T3", people=2, occupied_min=120)],
        parking=[ParkingSignal("C-01", "mobil", "B 2", 400, 180)],
        waiting=[WaitingSignal("T3", "S1", 22 * 60, "menunggu", 2, 0, 0)],
    )
    recs = generate(s, R)
    assert [r.priority for r in recs] == sorted([r.priority for r in recs], key=["tinggi", "sedang", "rendah"].index)
    assert ids(recs)[:2] == ["bersihkan:T2", "waiting:S1"]  # 15 menit kosong lebih mendesak
    assert all(a.score >= b.score for a, b in zip(recs, recs[1:]))


def test_engine_falls_back_to_rules_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("app.features.recommendations.llm._load_env", lambda: None)
    llm = LLMSummarizer()
    assert not llm.enabled and llm.reason == "ANTHROPIC_API_KEY tidak diisi"

    snap = RecommendationEngine(R, llm).snapshot(sig(tables=[table("T1", plates=2, empty_min=7)]))
    assert snap["engine"] == "rules"
    assert snap["summary"].startswith("Okupansi 0% (0/1 meja). Ada 1 saran")
    assert snap["counts"] == {"tinggi": 1, "sedang": 0, "rendah": 0}
    assert snap["llm"]["enabled"] is False


def test_engine_uses_llm_summary_when_available():
    class FakeLLM:
        def summary(self, sig, recs):
            return "Ringkasan dari LLM."

        def status(self):
            return {"enabled": True}

    snap = RecommendationEngine(R, FakeLLM()).snapshot(sig())  # type: ignore[arg-type]
    assert (snap["engine"], snap["summary"]) == ("rules+llm", "Ringkasan dari LLM.")


def test_mock_providers_are_labelled_and_deterministic():
    tables = [table("T1"), table("T2")]
    res = MockReservations().reservations(NOW, tables)
    assert MockReservations.source == "mock" and len(res) == 2 and all(r.at > NOW for r in res)
    park = MockParking()
    first = park.parking(NOW)
    later = park.parking(NOW + 600)
    assert later[0].duration_min == pytest.approx(first[0].duration_min + 10)


def test_llm_path_with_fake_client(monkeypatch):
    """Jalur LLM tanpa jaringan: client palsu, cek kwargs, cache, dan refusal tidak merusak."""
    import threading
    from types import SimpleNamespace

    calls = []

    class FakeMessages:
        def __init__(self, stop_reason="end_turn"):
            self.stop_reason = stop_reason

        def create(self, **kw):
            calls.append(kw)
            return SimpleNamespace(stop_reason=self.stop_reason, content=[SimpleNamespace(type="text", text=" Ringkasan. ")])

    monkeypatch.setattr("app.features.recommendations.llm._load_env", lambda: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    llm = LLMSummarizer()
    llm._client = SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages()), messages=FakeMessages())
    llm._sdk = SimpleNamespace(AuthenticationError=type("FakeAuthError", (Exception,), {}))

    def wait():
        for th in threading.enumerate():
            if th.name == "llm-summary":
                th.join(10)

    s = sig(tables=[table("T1", plates=2, empty_min=7)])
    recs = generate(s, R)
    assert llm.summary(s, recs) is None  # panggilan pertama jalan di latar
    wait()
    assert llm.summary(s, recs) == "Ringkasan."
    assert len(calls) == 1  # daftar saran sama & masih dalam MIN_GAP -> tidak memanggil lagi
    assert calls[0]["model"] == "claude-opus-5-5" and calls[0]["fallbacks"] == "default"

    llm._client.beta.messages = FakeMessages("refusal")
    llm._last_call = 0.0
    llm.summary(s, [])
    wait()
    assert "refusal" in llm.status()["error"]
    assert llm.summary(s, recs) == "Ringkasan."  # ringkasan lama tetap dipakai
