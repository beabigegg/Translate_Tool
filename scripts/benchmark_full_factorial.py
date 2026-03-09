#!/usr/bin/env python3
"""Full-factorial benchmark: Model × SysPrompt × ScenarioAppendix × DecodePreset.

Factors (4):
  1. Model:             qwen | hymt | tgemma              (3 levels)
  2. System Prompt:     off | on                          (2 levels)
  3. Scenario Appendix: off | on                          (2 levels)
  4. Decode Preset:     greedy | official                  (2 levels, per-model)

Total: 3 × 2 × 2 × 2 = 24 settings

Key principle: Each model uses its OWN official prompt format and recommended
decode parameters from production code, matching real-world usage exactly.
"""
from __future__ import annotations

import os

os.environ["TRANSLATION_CACHE_ENABLED"] = "0"

import argparse
import csv
import json
import random
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

try:
    import sacrebleu
except ImportError:
    sys.exit("sacrebleu not installed – run: pip install sacrebleu")

try:
    from datasets import load_dataset
except ImportError:
    sys.exit("datasets not installed – run: pip install datasets")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.backend.clients.ollama_client import OllamaClient
from app.backend.translation_profiles import PROFILES
from app.backend.services.translation_strategy import (
    TranslationScenario,
    _PROMPT_APPENDIX_BY_SCENARIO,
)

# ╔══════════════════════════════════════════════════════════════════╗
# ║  Constants                                                      ║
# ╚══════════════════════════════════════════════════════════════════╝

OUTPUT_BASE = PROJECT_ROOT / "test_output" / "benchmark_full_factorial"

OLLAMA_NUM_GPU = int(os.environ.get("OLLAMA_NUM_GPU", "99"))
OLLAMA_KV_CACHE_TYPE = os.environ.get("OLLAMA_KV_CACHE_TYPE", "q8_0")

LANG_INFO: Dict[str, Tuple[str, str]] = {
    "eng_Latn": ("English", "en"),
    "zho_Hans": ("Simplified Chinese", "zh"),
    "vie_Latn": ("Vietnamese", "vi"),
    "kor_Hang": ("Korean", "ko"),
    "jpn_Jpan": ("Japanese", "ja"),
    "deu_Latn": ("German", "de"),
}

DEFAULT_PAIRS = [
    ("zho_Hans", "eng_Latn"), ("eng_Latn", "zho_Hans"),
    ("zho_Hans", "vie_Latn"), ("vie_Latn", "zho_Hans"),
    ("zho_Hans", "kor_Hang"), ("kor_Hang", "zho_Hans"),
    ("zho_Hans", "jpn_Jpan"), ("jpn_Jpan", "zho_Hans"),
    ("zho_Hans", "deu_Latn"), ("deu_Latn", "zho_Hans"),
]

# Profile used for SysPrompt=ON.
PROFILE_ID = "general"

# Scenario used for ScenarioAppendix=ON.
SCENARIO = TranslationScenario.DAILY_COMMUNICATION

# ╔══════════════════════════════════════════════════════════════════╗
# ║  Factor 1: Models                                               ║
# ╚══════════════════════════════════════════════════════════════════╝


@dataclass(frozen=True)
class ModelDef:
    key: str          # short name for tables
    model_id: str     # Ollama model identifier
    prompt_mode: str  # "general" | "translation" | "translategemma"
    num_ctx: int


MODELS = [
    ModelDef("qwen",   "qwen3.5:4b",                        "general",        4096),
    ModelDef("hymt",   "demonbyron/HY-MT1.5-7B:Q4_K_M",     "translation",    3072),
    ModelDef("tgemma", "translategemma:4b",                   "translategemma", 2048),
]

# ╔══════════════════════════════════════════════════════════════════╗
# ║  Factor 4: Decode Presets (per-model, with official values)     ║
# ╚══════════════════════════════════════════════════════════════════╝

# Each model has its own "greedy" baseline and "official" recommended params.
MODEL_DECODE_PRESETS: Dict[str, Dict[str, Dict[str, object]]] = {
    "qwen": {
        "greedy": {
            "temperature": 0.05,
            "top_p": 0.50,
            "top_k": 10,
            "repeat_penalty": 1.0,
            "frequency_penalty": 0.0,
        },
        # Qwen3.5 official (non-thinking mode): temp=0.7, top_p=0.8, top_k=20, presence_penalty=1.5
        "official": {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 20,
            "repeat_penalty": 1.0,
            "presence_penalty": 1.5,
        },
    },
    "hymt": {
        "greedy": {
            "temperature": 0.05,
            "top_p": 0.50,
            "top_k": 10,
            "repeat_penalty": 1.0,
            "frequency_penalty": 0.0,
        },
        # HY-MT official: temp=0.7, top_p=0.6, top_k=20, repeat_penalty=1.05
        "official": {
            "temperature": 0.7,
            "top_p": 0.6,
            "top_k": 20,
            "repeat_penalty": 1.05,
            "frequency_penalty": 0.0,
        },
    },
    "tgemma": {
        "greedy": {
            "temperature": 0.05,
            "top_p": 0.50,
            "top_k": 10,
            "repeat_penalty": 1.0,
            "frequency_penalty": 0.0,
        },
        # TranslateGemma official: do_sample=False → near-deterministic greedy
        "official": {
            "temperature": 0.01,
            "top_p": 1.0,
            "top_k": 1,
            "repeat_penalty": 1.0,
            "frequency_penalty": 0.0,
        },
    },
}

# Flat list of preset names (same across models for factorial design)
DECODE_PRESET_NAMES = ["greedy", "official"]

# ╔══════════════════════════════════════════════════════════════════╗
# ║  Setting (one per factorial cell)                               ║
# ╚══════════════════════════════════════════════════════════════════╝


@dataclass(frozen=True)
class Setting:
    name: str
    model: ModelDef
    sys_prompt: bool        # Factor 2
    scenario_appendix: bool  # Factor 3
    decode_key: str         # Factor 4


TOTAL_SETTINGS = len(MODELS) * 2 * 2 * len(DECODE_PRESET_NAMES)  # 3×2×2×2 = 24


def generate_settings() -> List[Setting]:
    settings: List[Setting] = []
    for m in MODELS:
        for sp in (False, True):
            for sa in (False, True):
                for dk in DECODE_PRESET_NAMES:
                    name = f"{m.key}_sp{int(sp)}_sa{int(sa)}_{dk}"
                    settings.append(Setting(name, m, sp, sa, dk))
    return settings


# ╔══════════════════════════════════════════════════════════════════╗
# ║  Data loading (FLORES-200 via HuggingFace datasets)             ║
# ╚══════════════════════════════════════════════════════════════════╝


@dataclass
class TestCase:
    source: str
    reference: str
    dataset: str
    source_lang_code: str
    target_lang_code: str
    source_lang_name: str
    target_lang_name: str


def _sample(rows: List[dict], n: int, seed: int) -> List[dict]:
    if n <= 0 or len(rows) <= n:
        return rows
    rng = random.Random(seed)
    idx = list(range(len(rows)))
    rng.shuffle(idx)
    return [rows[i] for i in sorted(idx[:n])]


def load_flores_cases(
    pairs: List[Tuple[str, str]], per_pair: int, seed: int,
) -> List[TestCase]:
    print(f"Loading FLORES-200 devtest ({len(pairs)} language pairs, ≤{per_pair} samples each)…")
    ds = load_dataset("facebook/flores", "all", split="devtest", trust_remote_code=True)
    cases: List[TestCase] = []

    for pi, (src_code, tgt_code) in enumerate(pairs):
        src_col = f"sentence_{src_code}"
        tgt_col = f"sentence_{tgt_code}"
        rows = []
        for item in ds:
            src = (item.get(src_col) or "").strip()
            ref = (item.get(tgt_col) or "").strip()
            if src and ref and 4 <= len(src) <= 500:
                rows.append({"source": src, "reference": ref})

        sampled = _sample(rows, per_pair, seed + pi)
        ds_name = f"flores200_{src_code}_to_{tgt_code}"
        src_name = LANG_INFO[src_code][0]
        tgt_name = LANG_INFO[tgt_code][0]
        for r in sampled:
            cases.append(TestCase(
                source=r["source"], reference=r["reference"],
                dataset=ds_name,
                source_lang_code=src_code, target_lang_code=tgt_code,
                source_lang_name=src_name, target_lang_name=tgt_name,
            ))

    print(f"  → {len(cases)} test cases loaded")
    return cases


# ╔══════════════════════════════════════════════════════════════════╗
# ║  Ollama utilities                                               ║
# ╚══════════════════════════════════════════════════════════════════╝


def detect_base_url() -> str:
    env_url = os.environ.get("OLLAMA_BASE_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")
    for cand in ("http://localhost:11434", "http://127.0.0.1:11434"):
        try:
            if requests.get(f"{cand}/api/tags", timeout=3).status_code == 200:
                return cand
        except Exception:
            pass
    # WSL2: try gateway IP
    try:
        with open("/proc/net/route") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3 and parts[1] == "00000000":
                    h = parts[2]
                    ip = f"{int(h[6:8],16)}.{int(h[4:6],16)}.{int(h[2:4],16)}.{int(h[0:2],16)}"
                    cand = f"http://{ip}:11434"
                    if requests.get(f"{cand}/api/tags", timeout=3).status_code == 200:
                        return cand
    except Exception:
        pass
    return "http://localhost:11434"


def warm_up(base_url: str, model: str, num_ctx: int) -> None:
    """Load model into VRAM with a dummy request."""
    print(f"  Warming up {model}…", end=" ", flush=True)
    payload = {
        "model": model,
        "prompt": "Hello",
        "options": {"num_ctx": num_ctx, "num_gpu": OLLAMA_NUM_GPU, "kv_cache_type": OLLAMA_KV_CACHE_TYPE},
        "stream": False,
        "think": False,
    }
    try:
        resp = requests.post(f"{base_url}/api/generate", json=payload, timeout=(30, 120))
        if resp.status_code == 200:
            print("OK")
        else:
            print(f"HTTP {resp.status_code}")
    except Exception as e:
        print(f"FAIL ({e})")


def call_ollama(
    base_url: str, model: str, prompt: str,
    system_prompt: str, options: Dict[str, object], timeout_s: int,
) -> Tuple[bool, str, float, str]:
    payload: Dict[str, object] = {
        "model": model,
        "prompt": prompt,
        "options": options,
        "stream": False,
        "think": False,
    }
    if system_prompt:
        payload["system"] = system_prompt

    t0 = time.time()
    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/api/generate",
            json=payload, timeout=(10, timeout_s),
        )
        lat = time.time() - t0
        if resp.status_code != 200:
            return False, "", lat, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        return True, (data.get("response") or "").strip(), lat, ""
    except Exception as exc:
        return False, "", time.time() - t0, str(exc)


# ╔══════════════════════════════════════════════════════════════════╗
# ║  Prompt building — uses production OllamaClient methods         ║
# ╚══════════════════════════════════════════════════════════════════╝


def build_user_prompt(
    prompt_mode: str, source: str,
    src_lang_name: str, tgt_lang_name: str,
    has_system_prompt: bool,
) -> str:
    """Build user prompt using the SAME logic as production OllamaClient.

    Routes to the correct prompt builder per model type, matching
    ollama_client.py:_build_single_translate_payload exactly.
    """
    if prompt_mode == "translation":
        # HY-MT: uses Chinese prompt when involving Chinese (auto via _involves_chinese)
        return OllamaClient._build_translation_dedicated_prompt(
            text=source,
            target_language=tgt_lang_name,
            source_language=src_lang_name,
        )
    if prompt_mode == "translategemma":
        # TranslateGemma: full role-based prompt (same as production)
        return OllamaClient._build_translategemma_prompt(
            text=source,
            target_language=tgt_lang_name,
            source_language=src_lang_name,
        )
    # general (qwen): different prompt depending on whether system_prompt is set
    if has_system_prompt:
        return OllamaClient._build_user_prompt(
            text=source,
            target_language=tgt_lang_name,
            source_language=src_lang_name,
        )
    return OllamaClient._build_generic_prompt(
        text=source,
        target_language=tgt_lang_name,
        source_language=src_lang_name,
    )


def build_system_prompt(sys_prompt_on: bool, scenario_appendix_on: bool) -> str:
    """Assemble system prompt from factor settings."""
    parts: List[str] = []

    if sys_prompt_on:
        profile = PROFILES.get(PROFILE_ID)
        if profile and profile.system_prompt:
            parts.append(profile.system_prompt)

    if scenario_appendix_on:
        appendix = _PROMPT_APPENDIX_BY_SCENARIO.get(SCENARIO, "")
        if appendix:
            parts.append(appendix)

    return "\n\n".join(parts)


# ╔══════════════════════════════════════════════════════════════════╗
# ║  Metrics                                                        ║
# ╚══════════════════════════════════════════════════════════════════╝


def compute_metrics(hyps: List[str], refs: List[str]) -> Dict[str, float]:
    if not hyps:
        return {"bleu": 0.0, "chrf": 0.0, "ter": 100.0, "final": 0.0}
    bleu = sacrebleu.corpus_bleu(hyps, [refs], tokenize="flores200").score
    chrf = sacrebleu.corpus_chrf(hyps, [refs]).score
    ter = sacrebleu.corpus_ter(hyps, [refs]).score
    final = 0.40 * bleu + 0.45 * chrf + 0.15 * (100.0 - ter)
    return {
        "bleu": round(bleu, 4),
        "chrf": round(chrf, 4),
        "ter":  round(ter, 4),
        "final": round(final, 4),
    }


# ╔══════════════════════════════════════════════════════════════════╗
# ║  Analysis & reporting                                           ║
# ╚══════════════════════════════════════════════════════════════════╝


def _mean(vals: List[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def generate_analysis(rows: List[dict], outdir: Path) -> None:
    """Produce factorial_analysis.md with orthogonal table & effect analysis."""
    lines: List[str] = []
    w = lines.append

    w("# Full-Factorial Benchmark Analysis (v2 — corrected prompts & official params)")
    w("")
    w(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    w("")

    # ── Experiment summary ────────────────────────────────────────
    w("## Experiment Design")
    w("")
    w("| Factor | Levels |")
    w("|--------|--------|")
    w("| Model | qwen, hymt, tgemma |")
    w("| SysPrompt | OFF, ON |")
    w("| ScenarioAppendix | OFF, ON |")
    w(f"| DecodePreset | {', '.join(DECODE_PRESET_NAMES)} (per-model) |")
    w(f"| **Total settings** | **{len(rows)}** |")
    w("")
    w(f"Profile for SysPrompt=ON: `{PROFILE_ID}`")
    w(f"Scenario for ScenarioAppendix=ON: `{SCENARIO.value}`")
    w("")

    # ── Decode preset details ─────────────────────────────────────
    w("### Per-Model Decode Presets")
    w("")
    for model_key, presets in MODEL_DECODE_PRESETS.items():
        w(f"**{model_key}**:")
        w("")
        all_param_keys = sorted(set(k for p in presets.values() for k in p))
        header = "| Preset | " + " | ".join(all_param_keys) + " |"
        sep = "|--------|" + "|".join(["---"] * len(all_param_keys)) + "|"
        w(header)
        w(sep)
        for pk, pv in presets.items():
            vals = " | ".join(str(pv.get(k, "—")) for k in all_param_keys)
            w(f"| {pk} | {vals} |")
        w("")

    # ── Prompt format documentation ───────────────────────────────
    w("### Prompt Formats (from production code)")
    w("")
    w("- **HY-MT**: Chinese prompt when source/target involves Chinese (`将以下文本翻译为...`), English otherwise (`Translate the following segment into...`)")
    w("- **Qwen (with SP)**: `Translate from {src} to {tgt}:` + text")
    w("- **Qwen (no SP)**: Full inline instructions with rules")
    w("- **TranslateGemma**: Full professional translator role prompt")
    w("")

    # ── Complete orthogonal table ─────────────────────────────────
    w("---")
    w("")
    w("## Complete Orthogonal Table (sorted by Final ↓)")
    w("")
    sorted_rows = sorted(rows, key=lambda r: r["final"], reverse=True)
    w("| # | Setting | Model | SysPrompt | Scenario | Decode | BLEU | chrF | TER | Final |")
    w("|---|---------|-------|-----------|----------|--------|------|------|-----|-------|")
    for i, r in enumerate(sorted_rows, 1):
        sp = "ON" if r["sys_prompt"] else "OFF"
        sa = "ON" if r["scenario_appendix"] else "OFF"
        w(f"| {i} | {r['setting']} | {r['model']} | {sp} | {sa} | "
          f"{r['decode_preset']} | {r['bleu']:.2f} | {r['chrf']:.2f} | "
          f"{r['ter']:.2f} | **{r['final']:.2f}** |")
    w("")

    # ── Grand mean ────────────────────────────────────────────────
    grand_mean = _mean([r["final"] for r in rows])
    w("---")
    w("")
    w(f"## Grand Mean: **{grand_mean:.2f}**")
    w("")

    # ── Main effects ──────────────────────────────────────────────
    w("## Main Effects")
    w("")

    factors = {
        "Model":            ("model",            None),
        "SysPrompt":        ("sys_prompt",       {True: "ON", False: "OFF"}),
        "ScenarioAppendix": ("scenario_appendix", {True: "ON", False: "OFF"}),
        "DecodePreset":     ("decode_preset",    None),
    }

    for factor_name, (key, label_map) in factors.items():
        w(f"### {factor_name}")
        w("")
        groups: Dict[str, List[float]] = defaultdict(list)
        for r in rows:
            val = r[key]
            label = label_map[val] if label_map else str(val)
            groups[label].append(r["final"])

        w(f"| {factor_name} | Mean Final | Δ from Grand Mean | N |")
        w("|---|---|---|---|")
        for label in sorted(groups.keys()):
            m = _mean(groups[label])
            delta = m - grand_mean
            w(f"| {label} | {m:.2f} | {delta:+.2f} | {len(groups[label])} |")
        w("")

    # ── Two-way interactions ──────────────────────────────────────
    w("---")
    w("")
    w("## Two-Way Interactions")
    w("")

    factor_keys = [
        ("model", None),
        ("sys_prompt", {True: "ON", False: "OFF"}),
        ("scenario_appendix", {True: "ON", False: "OFF"}),
        ("decode_preset", None),
    ]

    for i, (k1, lm1) in enumerate(factor_keys):
        for k2, lm2 in factor_keys[i + 1:]:
            w(f"### {k1} × {k2}")
            w("")
            col_vals: List[str] = sorted(set(
                (lm2[r[k2]] if lm2 else str(r[k2])) for r in rows
            ))
            header = f"| {k1} | " + " | ".join(col_vals) + " |"
            sep = "|---|" + "|".join(["---"] * len(col_vals)) + "|"
            w(header)
            w(sep)

            row_vals = sorted(set(
                (lm1[r[k1]] if lm1 else str(r[k1])) for r in rows
            ))
            for rv in row_vals:
                cells = [rv]
                for cv in col_vals:
                    matched = [
                        r["final"] for r in rows
                        if (lm1[r[k1]] if lm1 else str(r[k1])) == rv
                        and (lm2[r[k2]] if lm2 else str(r[k2])) == cv
                    ]
                    cells.append(f"{_mean(matched):.2f}" if matched else "–")
                w("| " + " | ".join(cells) + " |")
            w("")

    # ── Per-language-pair breakdown ───────────────────────────────
    w("---")
    w("")
    w("## Per-Language-Pair: Best Setting")
    w("")
    w("*(Per-language-pair breakdown requires raw detail data; see factorial_details.json)*")
    w("")

    # ── Key takeaways ─────────────────────────────────────────────
    w("---")
    w("")
    w("## Key Questions Answered")
    w("")
    w("### 1. Does SysPrompt help HY-MT?")
    hymt_sp_off = _mean([r["final"] for r in rows if r["model"] == "hymt" and not r["sys_prompt"]])
    hymt_sp_on  = _mean([r["final"] for r in rows if r["model"] == "hymt" and r["sys_prompt"]])
    w(f"- HY-MT SysPrompt OFF: {hymt_sp_off:.2f}")
    w(f"- HY-MT SysPrompt ON:  {hymt_sp_on:.2f}")
    w(f"- **Effect: {hymt_sp_on - hymt_sp_off:+.2f}**")
    w("")

    w("### 2. Does SysPrompt help TranslateGemma?")
    tg_sp_off = _mean([r["final"] for r in rows if r["model"] == "tgemma" and not r["sys_prompt"]])
    tg_sp_on  = _mean([r["final"] for r in rows if r["model"] == "tgemma" and r["sys_prompt"]])
    w(f"- TranslateGemma SysPrompt OFF: {tg_sp_off:.2f}")
    w(f"- TranslateGemma SysPrompt ON:  {tg_sp_on:.2f}")
    w(f"- **Effect: {tg_sp_on - tg_sp_off:+.2f}**")
    w("")

    w("### 3. Does ScenarioAppendix add value beyond SysPrompt?")
    sp_on_sa_off = _mean([r["final"] for r in rows if r["sys_prompt"] and not r["scenario_appendix"]])
    sp_on_sa_on  = _mean([r["final"] for r in rows if r["sys_prompt"] and r["scenario_appendix"]])
    w(f"- SysPrompt=ON, Scenario=OFF: {sp_on_sa_off:.2f}")
    w(f"- SysPrompt=ON, Scenario=ON:  {sp_on_sa_on:.2f}")
    w(f"- **Incremental effect: {sp_on_sa_on - sp_on_sa_off:+.2f}**")
    w("")

    w("### 4. Official vs greedy decode per model")
    for m in ["qwen", "hymt", "tgemma"]:
        greedy_mean = _mean([r["final"] for r in rows if r["model"] == m and r["decode_preset"] == "greedy"])
        official_mean = _mean([r["final"] for r in rows if r["model"] == m and r["decode_preset"] == "official"])
        w(f"- **{m}**: greedy={greedy_mean:.2f}, official={official_mean:.2f}, Δ={official_mean - greedy_mean:+.2f}")
    w("")

    w("### 5. Best setting per model")
    for m in ["qwen", "hymt", "tgemma"]:
        best = max([r for r in rows if r["model"] == m], key=lambda r: r["final"])
        w(f"- **{m}**: {best['decode_preset']} (Final={best['final']:.2f}, "
          f"SP={'ON' if best['sys_prompt'] else 'OFF'}, "
          f"SA={'ON' if best['scenario_appendix'] else 'OFF'})")
    w("")

    report_path = outdir / "factorial_analysis.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  Analysis report: {report_path}")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  Main execution                                                 ║
# ╚══════════════════════════════════════════════════════════════════╝


def main() -> None:
    parser = argparse.ArgumentParser(description="Full-factorial translation benchmark (v2)")
    parser.add_argument("--max-samples", type=int, default=15,
                        help="Max test cases per language pair (default 15)")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Per-call timeout in seconds (default 120)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", type=str, default="",
                        help="Path to checkpoint.json to resume from")
    args = parser.parse_args()

    base_url = detect_base_url()
    print(f"Ollama: {base_url}")

    # ── Load test data ────────────────────────────────────────────
    cases = load_flores_cases(DEFAULT_PAIRS, args.max_samples, args.seed)

    # ── Generate all factorial settings ───────────────────────────
    settings = generate_settings()
    # Sort by model to minimize VRAM swaps
    settings.sort(key=lambda s: (s.model.key, s.name))

    print(f"\nTotal settings: {len(settings)}")
    print(f"Test cases per setting: {len(cases)}")
    print(f"Total API calls: {len(settings) * len(cases)}")
    print()

    # ── Output directory ──────────────────────────────────────────
    if args.resume:
        ckpt_path = Path(args.resume)
        outdir = ckpt_path.parent
    else:
        outdir = OUTPUT_BASE / time.strftime("%Y%m%d_%H%M%S")
    outdir.mkdir(parents=True, exist_ok=True)

    ckpt_path = outdir / "checkpoint.json"

    # Load checkpoint
    completed: Dict[str, dict] = {}
    if ckpt_path.exists():
        completed = json.loads(ckpt_path.read_text(encoding="utf-8"))
        print(f"Resuming: {len(completed)} settings already completed")

    # ── Pre-build system prompt variants (only 4 combos) ──────────
    sys_prompt_cache: Dict[Tuple[bool, bool], str] = {}
    for sp in (False, True):
        for sa in (False, True):
            sys_prompt_cache[(sp, sa)] = build_system_prompt(sp, sa)
            tag = f"SP={'ON' if sp else 'OFF'}, SA={'ON' if sa else 'OFF'}"
            content = sys_prompt_cache[(sp, sa)]
            print(f"  {tag}: {len(content)} chars")

    # ── Run ───────────────────────────────────────────────────────
    summary_rows: List[dict] = []
    all_details: List[dict] = []
    current_model_key = ""
    t_start = time.time()

    for si, setting in enumerate(settings):
        # Skip completed
        if setting.name in completed:
            summary_rows.append(completed[setting.name])
            print(f"[{si+1:2d}/{TOTAL_SETTINGS}] SKIP {setting.name} (cached)")
            continue

        # Warm up on model switch
        if setting.model.key != current_model_key:
            current_model_key = setting.model.key
            warm_up(base_url, setting.model.model_id, setting.model.num_ctx)

        sp_tag = "ON" if setting.sys_prompt else "OFF"
        sa_tag = "ON" if setting.scenario_appendix else "OFF"
        print(f"\n{'='*65}")
        print(f"[{si+1:2d}/{TOTAL_SETTINGS}] {setting.name}")
        print(f"  Model={setting.model.key}  SysPrompt={sp_tag}  "
              f"Scenario={sa_tag}  Decode={setting.decode_key}")

        # Build options — per-model decode preset
        decode_params = MODEL_DECODE_PRESETS[setting.model.key][setting.decode_key]
        options: Dict[str, object] = {
            "num_ctx": setting.model.num_ctx,
            "num_gpu": OLLAMA_NUM_GPU,
            "kv_cache_type": OLLAMA_KV_CACHE_TYPE,
        }
        options.update(decode_params)

        # Get pre-built system prompt
        sys_prompt_text = sys_prompt_cache[(setting.sys_prompt, setting.scenario_appendix)]

        hyps_all: List[str] = []
        refs_all: List[str] = []
        per_pair_hyps: Dict[str, List[str]] = defaultdict(list)
        per_pair_refs: Dict[str, List[str]] = defaultdict(list)
        failures = 0
        latencies: List[float] = []

        for ci, case in enumerate(cases):
            prompt = build_user_prompt(
                setting.model.prompt_mode,
                case.source,
                case.source_lang_name,
                case.target_lang_name,
                has_system_prompt=bool(sys_prompt_text),
            )

            ok, output, lat, err = call_ollama(
                base_url, setting.model.model_id,
                prompt, sys_prompt_text, options, args.timeout,
            )
            latencies.append(lat)

            detail = {
                "setting": setting.name,
                "model": setting.model.key,
                "model_id": setting.model.model_id,
                "dataset": case.dataset,
                "source_lang": case.source_lang_code,
                "target_lang": case.target_lang_code,
                "ok": ok,
                "latency_s": round(lat, 3),
                "source": case.source,
                "reference": case.reference,
                "hypothesis": output if ok else "",
                "error": err,
                "prompt": prompt,
                "system_prompt": sys_prompt_text,
                "options": options,
            }
            all_details.append(detail)

            if ok and output.strip():
                hyp = output.strip()
                hyps_all.append(hyp)
                refs_all.append(case.reference)
                pair_key = f"{case.source_lang_code}->{case.target_lang_code}"
                per_pair_hyps[pair_key].append(hyp)
                per_pair_refs[pair_key].append(case.reference)
            else:
                failures += 1

            # Progress
            if (ci + 1) % 30 == 0 or ci + 1 == len(cases):
                elapsed = time.time() - t_start
                print(f"    {ci+1}/{len(cases)} done, {failures} failures, "
                      f"elapsed {elapsed:.0f}s")

        # Compute aggregate metrics
        metrics = compute_metrics(hyps_all, refs_all)

        # Compute per-pair metrics
        pair_metrics = {}
        for pair_key in sorted(per_pair_hyps.keys()):
            pm = compute_metrics(per_pair_hyps[pair_key], per_pair_refs[pair_key])
            pair_metrics[pair_key] = pm

        avg_lat = _mean(latencies)

        row = {
            "setting": setting.name,
            "model": setting.model.key,
            "sys_prompt": setting.sys_prompt,
            "scenario_appendix": setting.scenario_appendix,
            "decode_preset": setting.decode_key,
            "n_ok": len(hyps_all),
            "n_fail": failures,
            "avg_latency": round(avg_lat, 3),
            **metrics,
            "pair_metrics": pair_metrics,
        }
        summary_rows.append(row)

        # Checkpoint
        completed[setting.name] = row
        ckpt_path.write_text(json.dumps(completed, indent=2, ensure_ascii=False), encoding="utf-8")

        print(f"  → BLEU={metrics['bleu']:.2f}  chrF={metrics['chrf']:.2f}  "
              f"TER={metrics['ter']:.2f}  Final={metrics['final']:.2f}  "
              f"({len(hyps_all)} ok, {failures} fail, {avg_lat:.2f}s/seg)")

    # ── Save results ──────────────────────────────────────────────
    total_time = time.time() - t_start

    # Summary CSV
    csv_path = outdir / "factorial_summary.csv"
    csv_fields = [
        "setting", "model", "sys_prompt", "scenario_appendix", "decode_preset",
        "n_ok", "n_fail", "avg_latency", "bleu", "chrf", "ter", "final",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"\nSummary CSV: {csv_path}")

    # Detail JSON
    detail_path = outdir / "factorial_details.json"
    detail_path.write_text(json.dumps(all_details, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Detail JSON: {detail_path} ({len(all_details)} rows)")

    # Summary JSON (with pair_metrics)
    summary_path = outdir / "factorial_summary.json"
    summary_path.write_text(json.dumps(summary_rows, indent=2, ensure_ascii=False), encoding="utf-8")

    # Analysis report
    generate_analysis(summary_rows, outdir)

    print(f"\nDone! {len(summary_rows)} settings, {len(all_details)} translations, "
          f"{total_time:.0f}s total ({total_time/60:.1f} min)")


if __name__ == "__main__":
    main()
