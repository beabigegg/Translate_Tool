"""Predefined translation profile presets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from app.backend.config import DEFAULT_MODEL, HYMT_DEFAULT_MODEL, ModelType


@dataclass(frozen=True)
class TranslationProfile:
    id: str
    name: str
    description: str
    model: str
    system_prompt: str
    model_type: str = ModelType.GENERAL.value


def _build_system_prompt(role: str, terminology: str, tone: str, example: str = "") -> str:
    """Build a concise system prompt optimised for small (4B) models.

    Structure uses primacy/recency effect:
      Tier 1 (beginning): role + core output constraint
      Tier 2 (middle):    domain terminology + optional example
      Tier 3 (end):       condensed rules
    """
    # Tier 1 – highest attention
    parts = [f"{role} Output only the translation, nothing else."]

    # Tier 2 – domain terms
    if terminology:
        parts.append(f"Terminology: {terminology}")

    # Optional concrete example (behavioural anchor)
    if example:
        parts.append(f"Example: {example}")

    # Tier 3 – condensed rules (high attention at end)
    parts.append(
        f"Rules: {tone} "
        "No explanations, commentary, or markdown. "
        "Preserve all numbers, units, formulas, article numbering, and formatting. "
        "Preserve all <<<SEG_N>>> markers exactly when they appear."
    )
    return "\n\n".join(parts)


PROFILES: Dict[str, TranslationProfile] = {
    "general": TranslationProfile(
        id="general",
        name="通用翻譯",
        description="General translation",
        model=DEFAULT_MODEL,
        system_prompt=_build_system_prompt(
            role="You are a professional translator.",
            terminology="Keep domain abbreviations consistent. Translate faithfully.",
            tone="Match the source register. Be clear, natural, and precise.",
        ),
    ),
    "government": TranslationProfile(
        id="government",
        name="正式公文",
        description="Government documents",
        model=DEFAULT_MODEL,
        system_prompt=_build_system_prompt(
            role="You are a government document translator.",
            terminology="Use precise administrative and regulatory terminology. Preserve citation formats and official numbering.",
            tone="Use formal, neutral, institution-appropriate grammar.",
            example="公文函 → keep formal administrative tone; 第三條 → preserve numbering format.",
        ),
    ),
    "semiconductor": TranslationProfile(
        id="semiconductor",
        name="半導體產業",
        description="Semiconductor",
        model=DEFAULT_MODEL,
        system_prompt=_build_system_prompt(
            role="You are a semiconductor manufacturing translator.",
            terminology=(
                "Keep untranslated: wafer, die, lot, yield, bin, EDA, tape-out, MOSFET, FinFET, "
                "leadframe, die attach, wire bond, clip bond, mold, trim & form, flip chip, singulation, "
                "BGA, QFN, SOP, DIP, OI, SPC, FMEA, CP, OEE, QC, QA, AQL, DPPM, MSA, GR&R, 8D, CAPA, ISO, "
                "ASML, TEL, LAM, KLA, ASM, K&S, BESI."
            ),
            tone="Use concise, technical wording for engineers and production teams.",
            example="die attach yield → keep 'die attach', 'yield' as-is; FMEA審查 → keep 'FMEA' untranslated.",
        ),
    ),
    "financial": TranslationProfile(
        id="financial",
        name="金融行業",
        description="Financial",
        model=DEFAULT_MODEL,
        system_prompt=_build_system_prompt(
            role="You are a finance and investment translator.",
            terminology="Keep untranslated: P&L, ROI, EBITDA, IFRS, GAAP, Basel. Preserve ticker symbols and instrument names.",
            tone="Use formal and precise financial register.",
            example="EBITDA margin → keep 'EBITDA' as-is; 殖利率 → use precise financial term.",
        ),
    ),
    "legal": TranslationProfile(
        id="legal",
        name="法律文件",
        description="Legal",
        model=DEFAULT_MODEL,
        system_prompt=_build_system_prompt(
            role="You are a legal translator for contracts and statutes.",
            terminology="Keep legal terms precise: indemnification, force majeure, jurisdiction, liability, arbitration, IP. Preserve clause references.",
            tone="Use strict legal wording. Do not paraphrase obligations, rights, or conditions.",
            example="force majeure → keep legal term; 第十二條第三項 → preserve clause numbering.",
        ),
    ),
    "hymt": TranslationProfile(
        id="hymt",
        name="HY-MT 翻譯引擎",
        description="HY-MT Translation Engine",
        model=HYMT_DEFAULT_MODEL,
        system_prompt="",
        model_type=ModelType.TRANSLATION.value,
    ),
}


def get_profile(profile_id: Optional[str]) -> TranslationProfile:
    if not profile_id:
        return PROFILES["general"]
    return PROFILES.get(profile_id, PROFILES["general"])


def list_profiles() -> List[TranslationProfile]:
    return list(PROFILES.values())
