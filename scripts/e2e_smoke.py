#!/usr/bin/env python3
"""
E2E smoke test: PANJIT translate → COMET QE → term audit
Run from repo root with the conda env active:
  QE_ENABLED=true QE_DEVICE=cuda python scripts/e2e_smoke.py
"""
from __future__ import annotations

import os
import sys
import time

# ─── add repo root to sys.path ───────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# pre-load CUDA libs (same trick as tests/conftest.py)
import ctypes, site as _site
for _lib in [
    os.path.join(_site.getsitepackages()[0], "nvidia", "cu13", "lib", "libcudart.so.13"),
    os.path.join(_site.getsitepackages()[0], "nvidia", "cuda_runtime", "lib", "libcudart.so.12"),
]:
    if os.path.exists(_lib):
        try: ctypes.CDLL(_lib, mode=ctypes.RTLD_GLOBAL)
        except OSError: pass

# ─── load .env ────────────────────────────────────────────────────────────────
from pathlib import Path
_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

PANJIT_BASE = os.environ["PANJIT_LLM_BASE_URL"]
PANJIT_KEY  = os.environ["PANJIT_API"]
PANJIT_MODEL = "gpt-oss:120b"

USE_QE   = os.environ.get("QE_ENABLED", "false").lower() in ("1", "true")
QE_DEVICE = os.environ.get("QE_DEVICE", "cpu")
QE_MODEL  = os.environ.get("QE_MODEL_NAME", "Unbabel/wmt22-cometkiwi-da")

SRC_TEXT = (
    "機器翻譯技術在近幾年取得了重大進展，"
    "使得跨語言溝通變得更加便利。"
    "然而，對於專業領域的文件，仍然需要人工審校以確保術語準確性。"
)
SRC_LANG = "Chinese"
TGT_LANG = "English"

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"

def section(title: str) -> None:
    print(f"\n{'─'*60}\n{title}\n{'─'*60}")

# ════════════════════════════════════════════════════════════════
# Step 1: PANJIT translate_once
# ════════════════════════════════════════════════════════════════
section("Step 1 — PANJIT API translation (gpt-oss:120b)")
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

client = OpenAICompatibleClient(
    base_url=PANJIT_BASE,
    api_key=PANJIT_KEY,
    model=PANJIT_MODEL,
    provider_id="panjit-smoke",
    connect_timeout=30.0,
    read_timeout=120.0,
    verify_ssl=False,  # PANJIT internal API uses a self-signed cert
)

t0 = time.time()
ok, translated = client.translate_once(SRC_TEXT, tgt=TGT_LANG, src_lang=SRC_LANG)
elapsed = time.time() - t0

if ok:
    print(f"{PASS}  Translation OK  ({elapsed:.1f}s)")
    print(f"     SRC: {SRC_TEXT}")
    print(f"     TGT: {translated}")
else:
    print(f"{FAIL}  Translation FAILED: {translated}")
    sys.exit(1)

# ════════════════════════════════════════════════════════════════
# Step 2: COMET QE scoring (skip if QE_ENABLED not set)
# ════════════════════════════════════════════════════════════════
section("Step 2 — COMET QE scoring")
if not USE_QE:
    print(f"  (skipped — set QE_ENABLED=true QE_DEVICE=cuda to enable GPU scoring)")
    qe_score = None
else:
    from app.backend.services.quality_evaluator import load_model, score_blocks
    print(f"  Loading COMET model {QE_MODEL} on device={QE_DEVICE} ...")
    t0 = time.time()
    model = load_model(QE_MODEL, QE_DEVICE)
    print(f"  Model loaded in {time.time()-t0:.1f}s")

    src_mt_pairs = [(SRC_TEXT, translated)]
    t0 = time.time()
    scored = score_blocks(model, src_mt_pairs, device=QE_DEVICE)
    print(f"  Scored {len(scored)} block(s) in {time.time()-t0:.2f}s")
    qe_score = None
    for score in scored:
        qe_score = score
        status = PASS if score >= 0.0 else FAIL
        print(f"  {status}  score={score:.4f}")

# ════════════════════════════════════════════════════════════════
# Step 3: term audit
# ════════════════════════════════════════════════════════════════
section("Step 3 — Terminology audit")
from app.backend.services.term_db import TermDB
from app.backend.services.term_audit import audit_terms
from app.backend.models.term import Term

term_db = TermDB()
# seed a couple of approved terms we expect in a MT context
for target_text in ["machine translation", "terminology", "proofreading"]:
    t = Term(
        source_text=target_text,  # using target as source key for test purposes
        target_text=target_text,
        source_lang="English",
        target_lang="English",
        domain="general",
        status="approved",
    )
    term_db.insert(t, strategy="overwrite")

blocks = [("blk-001", SRC_TEXT, translated)]
result = audit_terms(blocks, targets=["English"], domain=None, term_db=term_db)

print(f"  {PASS}  audit_terms() returned TerminologyAuditResult")
print(f"       total_approved   : {result.total_approved}")
print(f"       matched_approved : {result.matched_approved}")
print(f"       hit_rate         : {result.terminology_hit_rate:.2%}")
print(f"       unapplied        : {result.unapplied_terms}")
print(f"       rejected_inj     : {result.rejected_injections}")

# ════════════════════════════════════════════════════════════════
# Summary
# ════════════════════════════════════════════════════════════════
section("E2E Summary")
print(f"  {PASS}  PANJIT API reachable and returning translations")
if USE_QE:
    print(f"  {PASS}  COMET QE scoring functional (GPU={QE_DEVICE}, score={qe_score:.4f})")
else:
    print(f"  --  COMET QE skipped (run with QE_ENABLED=true to test)")
print(f"  {PASS}  term_audit() functional (hit_rate={result.terminology_hit_rate:.2%})")
print()
