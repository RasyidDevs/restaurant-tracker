"""Lapisan LLM OPSIONAL: ringkasan saran tindakan untuk manajer shift.

  - API key dibaca dari backend/.env (ANTHROPIC_API_KEY). Tidak pernah di-hardcode.
  - Tanpa key, paket `anthropic` tidak terpasang, atau API error -> None,
    dan engine memakai ringkasan rule-based.
  - LLM hanya MERINGKAS saran dari rule engine; tindakan tidak ditambah/diubah.
  - Tidak memblokir: panggilan API jalan di thread latar, hasil di-cache.
    Panggilan baru hanya kalau daftar saran berubah atau sudah LLM_REFRESH_S detik.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

from .rules import Recommendation
from .signals import TeamSignals

log = logging.getLogger("recommendations.llm")

ENV_FILE = Path(__file__).resolve().parents[3] / ".env"  # backend/.env
DEFAULT_MODEL = "claude-opus-5-5"
# Model yang mendukung fallback server-side saat permintaan ditolak (refusal).
FALLBACK_MODELS = {"claude-fable-5-2", "claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
MIN_GAP_S = 15.0  # jarak minimum antar panggilan API (hemat biaya)

SYSTEM = (
    "Kamu asisten operasional restoran. Kamu menerima daftar saran tindakan yang sudah "
    "dihitung oleh rule engine dari data kamera (CCTV). Tulis ringkasan 2-3 kalimat dalam "
    "bahasa Indonesia untuk manajer shift: kondisi restoran saat ini dan apa yang harus "
    "didahulukan. Jangan menambah tindakan baru dan jangan mengubah angka. Kalau ada data "
    "bertanda mock, sebutkan bahwa sebagian data masih simulasi. Teks biasa tanpa markdown."
)


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ENV_FILE, override=False)


class LLMSummarizer:
    def __init__(self) -> None:
        _load_env()
        self.model = os.environ.get("LLM_MODEL") or DEFAULT_MODEL
        self.refresh_s = float(os.environ.get("LLM_REFRESH_S") or 60)
        self.error: str | None = None
        self._client: Any = None
        self._lock = threading.Lock()
        self._summary: str | None = None
        self._fingerprint: tuple | None = None
        self._last_call = 0.0
        self._busy = False

        if not os.environ.get("ANTHROPIC_API_KEY"):
            self.reason = "ANTHROPIC_API_KEY tidak diisi"
            return
        try:
            import anthropic
        except ImportError:
            self.reason = "paket anthropic belum terpasang"
            return
        # Key dibaca SDK dari environment (diisi dari backend/.env).
        self._client = anthropic.Anthropic(timeout=20.0, max_retries=1)
        self.reason = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "model": self.model if self.enabled else None,
            "reason": self.reason,
            "error": self.error,
            "has_summary": self._summary is not None,
        }

    def summary(self, sig: TeamSignals, recs: list[Recommendation]) -> str | None:
        """Ringkasan LLM terakhir (bisa sedikit tertinggal), atau None. Tidak pernah memblokir."""
        if not self.enabled:
            return None
        fp = tuple((r.id, r.priority) for r in recs)
        now = time.monotonic()
        with self._lock:
            stale = fp != self._fingerprint or now - self._last_call >= self.refresh_s
            if stale and not self._busy and now - self._last_call >= MIN_GAP_S:
                self._busy = True
                self._last_call = now
                payload = self._payload(sig, recs)
                threading.Thread(target=self._refresh, args=(fp, payload), daemon=True, name="llm-summary").start()
            return self._summary

    def _payload(self, sig: TeamSignals, recs: list[Recommendation]) -> str:
        return json.dumps(
            {
                "okupansi": f"{sig.occupancy:.0%}",
                "jumlah_meja": len(sig.tables),
                "sumber_data": sig.data_sources,
                "saran": [
                    {"prioritas": r.priority, "judul": r.title, "alasan": r.reason, "mock": r.mock} for r in recs[:10]
                ],
            },
            ensure_ascii=False,
        )

    def _refresh(self, fp: tuple, payload: str) -> None:
        text, err = None, None
        try:
            text = self._call(payload)
        except Exception as e:  # dicatat & tetap pakai rule-based
            err = f"{type(e).__name__}: {e}"
            log.warning("LLM gagal, pakai rule-based: %s", err)
        with self._lock:
            self._busy = False
            self.error = err
            if text:
                self._summary = text
                self._fingerprint = fp

    def _call(self, payload: str) -> str | None:
        import anthropic

        kwargs: dict[str, Any] = dict(
            model=self.model,
            max_tokens=2000,
            system=SYSTEM,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": payload}],
        )
        try:
            if self.model in FALLBACK_MODELS:
                resp = self._client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
                )
            else:
                resp = self._client.messages.create(**kwargs)
        except anthropic.AuthenticationError:
            self._client = None  # key salah: matikan LLM sampai server di-restart
            self.reason = "API key ditolak (cek ANTHROPIC_API_KEY)"
            raise
        # Error lain (RateLimitError, APIStatusError, APIConnectionError/timeout) diteruskan ke
        # _refresh: dicatat di status, ringkasan terakhir/rule-based tetap dipakai, dicoba lagi nanti.

        if resp.stop_reason == "refusal":
            raise RuntimeError("permintaan ditolak model (refusal)")
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        return text or None
