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


def _build_system_prompt(role: str, terminology: str, register_tone: str) -> str:
    """Build system prompt — restored to original structure that worked with qwen3.5:4b."""
    return (
        f"Role declaration:\n{role}\n\n"
        "Terminology guidance:\n"
        f"{terminology}\n\n"
        "Register and tone:\n"
        f"{register_tone}\n\n"
        "Output rules:\n"
        "1) Output only the translated text.\n"
        "2) Never add explanations, commentary, or markdown wrappers.\n"
        "3) Preserve line breaks and formatting structure.\n"
        "4) If the input text is already entirely in the target language, return it unchanged without modification.\n"
        "5) For short labels or column headers that already contain the target language alongside other languages (for example bilingual headers), return the original text unchanged.\n"
        "6) Prefer natural, idiomatic phrasing in the target language over literal or word-for-word translation.\n\n"
        "Numerical and code preservation:\n"
        "Preserve all numbers, units, formulas, model numbers, article/section numbering, URLs, and code tokens exactly."
    )


PROFILES: Dict[str, TranslationProfile] = {
    # User-facing scenario categories
    "technical_process": TranslationProfile(
        id="technical_process",
        name="技術製程",
        description="準確、可操作",
        model=HYMT_DEFAULT_MODEL,
        system_prompt=_build_system_prompt(
            role="You are a professional translator for technical process and SOP documents.",
            terminology=(
                "Use precise process engineering terminology and keep operation names, machine parameters, "
                "tolerances, and quality control terms consistent across the file."
            ),
            register_tone="Use exact and executable wording suitable for on-line operations and work instructions. Avoid calque or word-for-word rendering; use phrasing natural to a native speaker of the target language.",
        ),
        model_type=ModelType.TRANSLATION.value,
    ),
    "business_finance": TranslationProfile(
        id="business_finance",
        name="商務金融",
        description="專業、客觀",
        model=HYMT_DEFAULT_MODEL,
        system_prompt=_build_system_prompt(
            role="You are a professional translator for business and finance materials.",
            terminology=(
                "Use standard business and finance terms precisely: quotation, invoice, cash flow, margin, "
                "ROI, EBITDA, IFRS, covenant, and payment terms."
            ),
            register_tone="Use objective and professional language suitable for formal business communication. Avoid calque or word-for-word rendering; use phrasing natural to a native speaker of the target language.",
        ),
        model_type=ModelType.TRANSLATION.value,
    ),
    "legal_contract": TranslationProfile(
        id="legal_contract",
        name="法律合約",
        description="嚴謹、無歧義",
        model=DEFAULT_MODEL,
        system_prompt=_build_system_prompt(
            role="You are a professional legal translator for contracts, terms, and compliance documents.",
            terminology=(
                "Use strict legal terms: indemnification, limitation of liability, jurisdiction, confidentiality, "
                "arbitration, force majeure, and statutory references."
            ),
            register_tone="Use unambiguous legal wording; preserve obligations, rights, conditions, and clause logic.",
        ),
    ),
    "marketing_pr": TranslationProfile(
        id="marketing_pr",
        name="行銷公關",
        description="吸引人、在地化",
        model=HYMT_DEFAULT_MODEL,
        system_prompt=_build_system_prompt(
            role="You are a professional translator for marketing campaigns, branding, and PR materials.",
            terminology=(
                "Preserve product names, campaign tags, and key selling points while adapting idioms and expressions "
                "to target-market usage."
            ),
            register_tone="Use persuasive, natural, and localized wording with clear call-to-action intent. Avoid calque or word-for-word rendering; use phrasing natural to a native speaker of the target language.",
        ),
        model_type=ModelType.TRANSLATION.value,
    ),
    "daily_communication": TranslationProfile(
        id="daily_communication",
        name="日常溝通",
        description="得體、流暢",
        model=DEFAULT_MODEL,
        system_prompt=_build_system_prompt(
            role="You are a professional translator for everyday communication and coordination messages.",
            terminology=(
                "Keep practical details exact (time, date, quantity, contact info) and avoid over-literal phrasing."
            ),
            register_tone="Use polite, fluent, and natural conversational language.",
        ),
    ),
    # Legacy profiles for backward compatibility
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
