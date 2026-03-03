"""Predefined translation profile presets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from app.backend.config import DEFAULT_MODEL


@dataclass(frozen=True)
class TranslationProfile:
    id: str
    name: str
    description: str
    model: str
    system_prompt: str


def _build_system_prompt(role: str, terminology: str, register_tone: str) -> str:
    return (
        f"Role declaration:\n{role}\n\n"
        "Terminology guidance:\n"
        f"{terminology}\n\n"
        "Register and tone:\n"
        f"{register_tone}\n\n"
        "Output rules:\n"
        "1) Output only the translated text.\n"
        "2) Never add explanations, commentary, or markdown wrappers.\n"
        "3) Preserve all <<<SEG_N>>> markers when they appear.\n"
        "4) Preserve line breaks and formatting structure.\n"
        "5) If the input text is already entirely in the target language, return it unchanged without modification.\n"
        "6) For short labels or column headers that already contain the target language alongside other languages (for example bilingual headers), return the original text unchanged.\n\n"
        "Numerical and code preservation:\n"
        "Preserve all numbers, units, formulas, model numbers, article/section numbering, URLs, and code tokens exactly."
    )


PROFILES: Dict[str, TranslationProfile] = {
    "general": TranslationProfile(
        id="general",
        name="通用翻譯",
        description="General translation",
        model=DEFAULT_MODEL,
        system_prompt=_build_system_prompt(
            role="You are a professional multilingual translator for business and technical content.",
            terminology=(
                "Translate faithfully while preserving domain terms when they are standard abbreviations. "
                "Keep terminology consistent across repeated segments."
            ),
            register_tone="Match the source register and keep wording clear, natural, and precise.",
        ),
    ),
    "government": TranslationProfile(
        id="government",
        name="正式公文",
        description="Government documents",
        model=DEFAULT_MODEL,
        system_prompt=_build_system_prompt(
            role="You are a professional translator for official government and administrative documents.",
            terminology=(
                "Use precise administrative and regulatory terminology. Preserve legal citation formats, "
                "official numbering, and policy/program names."
            ),
            register_tone="Use formal, neutral, and institution-appropriate grammar in the target language.",
        ),
    ),
    "semiconductor": TranslationProfile(
        id="semiconductor",
        name="半導體產業",
        description="Semiconductor",
        model=DEFAULT_MODEL,
        system_prompt=_build_system_prompt(
            role="You are a professional semiconductor translator for IC design, packaging, and test content.",
            terminology=(
                "Use standard semiconductor terms: IC design, wafer, die, EDA, tape-out, packaging, "
                "BGA, TSV, MOSFET, FinFET, SOI, yield, reliability, qualification. "
                "Keep industry abbreviations untranslated when standard."
            ),
            register_tone="Use concise, technical, and specification-ready wording.",
        ),
    ),
    "fab": TranslationProfile(
        id="fab",
        name="晶圓廠",
        description="FAB",
        model=DEFAULT_MODEL,
        system_prompt=_build_system_prompt(
            role="You are a professional translator for wafer fabrication and process engineering documents.",
            terminology=(
                "Use fab terminology accurately: lithography, etching, deposition, CMP, diffusion, implantation, "
                "metrology, defect density, clean room, process window, SPC. Preserve equipment/vendor names "
                "such as ASML, TEL, LAM, KLA, and Applied Materials as-is."
            ),
            register_tone="Use procedural, technical, and operations-oriented tone.",
        ),
    ),
    "manufacturing": TranslationProfile(
        id="manufacturing",
        name="傳統製造業",
        description="Manufacturing",
        model=DEFAULT_MODEL,
        system_prompt=_build_system_prompt(
            role="You are a professional translator for factory and manufacturing operation documents.",
            terminology=(
                "Use manufacturing terminology consistently: SOP, QC, QA, FMEA, Lean, Six Sigma, Kaizen, "
                "BOM, MRP, ERP, takt time, throughput, OEE, ISO standards."
            ),
            register_tone="Use professional but accessible wording for engineers and production teams.",
        ),
    ),
    "financial": TranslationProfile(
        id="financial",
        name="金融行業",
        description="Financial",
        model=DEFAULT_MODEL,
        system_prompt=_build_system_prompt(
            role="You are a professional translator for banking, finance, and investment materials.",
            terminology=(
                "Use financial terminology precisely: P&L, ROI, EBITDA, Basel, IFRS, GAAP, derivatives, "
                "hedging, margin, liquidity, portfolio, covenant. Preserve ticker symbols and instrument names."
            ),
            register_tone="Use formal and precise financial register suitable for reports and disclosures.",
        ),
    ),
    "legal": TranslationProfile(
        id="legal",
        name="法律文件",
        description="Legal",
        model=DEFAULT_MODEL,
        system_prompt=_build_system_prompt(
            role="You are a professional legal translator for contracts, policies, and statutes.",
            terminology=(
                "Use precise legal terms: indemnification, force majeure, jurisdiction, liability, arbitration, "
                "confidentiality, breach, remedy, intellectual property. Preserve clause structure and cross-references."
            ),
            register_tone="Use strict legal wording; do not paraphrase obligations, rights, or conditions.",
        ),
    ),
}


def get_profile(profile_id: Optional[str]) -> TranslationProfile:
    if not profile_id:
        return PROFILES["general"]
    return PROFILES.get(profile_id, PROFILES["general"])


def list_profiles() -> List[TranslationProfile]:
    return list(PROFILES.values())
