"""Dynamic translation scenario detection and strategy selection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, List, Optional, TYPE_CHECKING

from app.backend.config import ModelType

if TYPE_CHECKING:
    from app.backend.models.term import Term


class TranslationScenario(str, Enum):
    """Document-level translation scenarios."""

    TECHNICAL_PROCESS = "technical_process"
    BUSINESS_FINANCE = "business_finance"
    LEGAL_CONTRACT = "legal_contract"
    MARKETING_PR = "marketing_pr"
    DAILY_COMMUNICATION = "daily_communication"
    # Legacy IDs kept for compatibility with existing datasets/benchmarks.
    SEMICONDUCTOR_OI_CP_SOP = "semiconductor_oi_cp_sop"
    PROCESS_PRESENTATION = "process_presentation"
    INTERNATIONAL_STANDARD = "international_standard"
    BUSINESS_EMAIL = "business_email"
    GENERAL = "general"


@dataclass(frozen=True)
class StrategyDecision:
    """Resolved per-file strategy."""

    scenario: TranslationScenario
    system_prompt: str
    options_override: Dict[str, object]
    cache_variant: str


_LEGACY_SCENARIO_ALIAS: Dict[TranslationScenario, TranslationScenario] = {
    TranslationScenario.SEMICONDUCTOR_OI_CP_SOP: TranslationScenario.TECHNICAL_PROCESS,
    TranslationScenario.PROCESS_PRESENTATION: TranslationScenario.TECHNICAL_PROCESS,
    TranslationScenario.INTERNATIONAL_STANDARD: TranslationScenario.LEGAL_CONTRACT,
    TranslationScenario.BUSINESS_EMAIL: TranslationScenario.BUSINESS_FINANCE,
}

_PROFILE_SCENARIO_HINT: Dict[str, TranslationScenario] = {
    # New user-facing categories
    "technical_process": TranslationScenario.TECHNICAL_PROCESS,
    "business_finance": TranslationScenario.BUSINESS_FINANCE,
    "legal_contract": TranslationScenario.LEGAL_CONTRACT,
    "marketing_pr": TranslationScenario.MARKETING_PR,
    "daily_communication": TranslationScenario.DAILY_COMMUNICATION,
    # Backward-compatible profile IDs
    "semiconductor": TranslationScenario.TECHNICAL_PROCESS,
    "financial": TranslationScenario.BUSINESS_FINANCE,
    "legal": TranslationScenario.LEGAL_CONTRACT,
    "government": TranslationScenario.LEGAL_CONTRACT,
}

_SCENARIO_KEYWORDS: Dict[TranslationScenario, tuple[str, ...]] = {
    TranslationScenario.TECHNICAL_PROCESS: (
        "sop", "oi", "cp", "作业指导", "作業指導", "站點", "站点", "制程", "參數", "参数", "量測", "量测",
        "扭矩", "校正", "批號", "批号", "不良率", "良率", "設備", "设备", "工站", "lot", "yield", "spc", "fmea",
    ),
    TranslationScenario.BUSINESS_FINANCE: (
        "財報", "财报", "毛利", "毛利率", "現金流", "现金流", "報價", "报价", "付款", "應收帳款", "应收账款",
        "roi", "ebitda", "ifrs", "forecast", "quotation", "invoice", "budget", "margin", "cash flow",
    ),
    TranslationScenario.LEGAL_CONTRACT: (
        "合約", "合同", "條款", "条款", "契約", "义务", "義務", "責任", "责任", "賠償", "赔偿", "保密",
        "仲裁", "管轄", "管辖", "shall", "must", "hereby", "compliance", "regulation", "法律",
    ),
    TranslationScenario.MARKETING_PR: (
        "品牌", "活動", "活动", "行銷", "营销", "廣告", "广告", "社群", "受眾", "受众", "在地化", "新品發布",
        "新品发布", "campaign", "brand", "slogan", "press release", "engagement", "conversion",
    ),
    TranslationScenario.DAILY_COMMUNICATION: (
        "請問", "请问", "麻煩", "麻烦", "謝謝", "谢谢", "抱歉", "不好意思", "收到", "稍後", "稍后", "今晚",
        "明天", "等一下", "幫我", "帮我", "please", "thanks", "sorry", "let me know",
    ),
}

_GENERAL_OPTIONS_BY_SCENARIO: Dict[TranslationScenario, Dict[str, object]] = {
    TranslationScenario.TECHNICAL_PROCESS: {
        "temperature": 0.20,
        "top_p": 0.75,
        "top_k": 40,
        "repeat_penalty": 1.12,
        "frequency_penalty": 0.20,
    },
    TranslationScenario.BUSINESS_FINANCE: {
        "temperature": 0.25,
        "top_p": 0.80,
        "top_k": 50,
        "repeat_penalty": 1.10,
        "frequency_penalty": 0.20,
    },
    TranslationScenario.LEGAL_CONTRACT: {
        "temperature": 0.18,
        "top_p": 0.70,
        "top_k": 40,
        "repeat_penalty": 1.10,
        "frequency_penalty": 0.25,
    },
    TranslationScenario.MARKETING_PR: {
        "temperature": 0.55,
        "top_p": 0.92,
        "top_k": 70,
        "repeat_penalty": 1.04,
        "frequency_penalty": 0.15,
    },
    TranslationScenario.DAILY_COMMUNICATION: {
        "temperature": 0.38,
        "top_p": 0.90,
        "top_k": 60,
        "repeat_penalty": 1.06,
        "frequency_penalty": 0.18,
    },
    TranslationScenario.GENERAL: {},
}

_TRANSLATION_OPTIONS_BY_SCENARIO: Dict[TranslationScenario, Dict[str, object]] = {
    TranslationScenario.TECHNICAL_PROCESS: {
        "temperature": 0.20,
        "top_p": 0.55,
        "top_k": 30,
        "repeat_penalty": 1.12,
    },
    TranslationScenario.BUSINESS_FINANCE: {
        "temperature": 0.25,
        "top_p": 0.62,
        "top_k": 30,
        "repeat_penalty": 1.08,
    },
    TranslationScenario.LEGAL_CONTRACT: {
        "temperature": 0.18,
        "top_p": 0.55,
        "top_k": 25,
        "repeat_penalty": 1.10,
    },
    TranslationScenario.MARKETING_PR: {
        "temperature": 0.42,
        "top_p": 0.72,
        "top_k": 45,
        "repeat_penalty": 1.04,
    },
    TranslationScenario.DAILY_COMMUNICATION: {
        "temperature": 0.32,
        "top_p": 0.72,
        "top_k": 40,
        "repeat_penalty": 1.05,
    },
    TranslationScenario.GENERAL: {},
}

_PROMPT_APPENDIX_BY_SCENARIO: Dict[TranslationScenario, str] = {
    TranslationScenario.TECHNICAL_PROCESS: (
        "Scenario focus: Technical process documentation.\n"
        "Style rules:\n"
        "- Prioritize operational clarity and step-by-step executability.\n"
        "- Preserve process limits, tolerances, units, and machine parameters exactly.\n"
        "- Keep terminology consistent for SOP/OI/CP style instructions.\n"
        "Terminology constraints:\n"
        "- 切弯脚 / 切彎腳 => trim & form\n"
        "- 作业指导书 / 作業指導書 => work instruction\n"
        "- 作业指导卡 / 作業指導卡 => work instruction card\n"
        "- 制程 => process"
    ),
    TranslationScenario.BUSINESS_FINANCE: (
        "Scenario focus: Business and finance documents.\n"
        "Style rules:\n"
        "- Use objective and professional financial wording.\n"
        "- Preserve accounting terms, KPIs, and figures precisely.\n"
        "- Keep contract/payment/commercial tokens exact (PO, RFQ, EBITDA, IFRS, ROI)."
    ),
    TranslationScenario.LEGAL_CONTRACT: (
        "Scenario focus: Legal and contract documents.\n"
        "Style rules:\n"
        "- Use strict and unambiguous legal phrasing.\n"
        "- Preserve normative modality precisely (shall/must/should/may).\n"
        "- Keep clause numbering, cross-references, and obligations unchanged."
    ),
    TranslationScenario.MARKETING_PR: (
        "Scenario focus: Marketing and public relations content.\n"
        "Style rules:\n"
        "- Keep copy persuasive but professional.\n"
        "- Prefer concise, localized phrasing for audience engagement.\n"
        "- Preserve product names, campaign tags, and call-to-action intent."
    ),
    TranslationScenario.DAILY_COMMUNICATION: (
        "Scenario focus: Daily communication.\n"
        "Style rules:\n"
        "- Keep natural, polite, and fluent conversational tone.\n"
        "- Preserve key schedule details and action requests.\n"
        "- Avoid overly literal wording that sounds awkward."
    ),
    TranslationScenario.GENERAL: "",
}


def _canonicalize_scenario(scenario: TranslationScenario) -> TranslationScenario:
    return _LEGACY_SCENARIO_ALIAS.get(scenario, scenario)


def scenario_from_profile(profile_id: Optional[str]) -> Optional[TranslationScenario]:
    """Resolve a fixed scenario hint from profile ID."""
    if not profile_id:
        return None
    return _PROFILE_SCENARIO_HINT.get((profile_id or "").strip().lower())


def _lower_texts(*parts: Optional[str]) -> str:
    return " ".join([(p or "").lower() for p in parts if p])


def _score_keywords(text: str, keywords: Iterable[str]) -> int:
    score = 0
    for kw in keywords:
        if kw in text:
            score += 1
    return score


def detect_translation_scenario(
    filename: str,
    sample_text: Optional[str] = None,
    detected_context: Optional[str] = None,
) -> TranslationScenario:
    """Heuristically detect scenario from filename + sampled content + context summary."""
    haystack = _lower_texts(filename, sample_text, detected_context)
    if not haystack.strip():
        return TranslationScenario.GENERAL

    best = TranslationScenario.GENERAL
    best_score = 0
    for scenario, keywords in _SCENARIO_KEYWORDS.items():
        score = _score_keywords(haystack, keywords)
        if score > best_score:
            best = scenario
            best_score = score

    # Require at least 2 keyword hits to avoid noisy over-classification.
    return best if best_score >= 2 else TranslationScenario.GENERAL


def build_strategy(
    base_system_prompt: str,
    model_type: str,
    scenario: TranslationScenario,
    detected_context: Optional[str] = None,
    enable_context_flow: bool = True,
) -> StrategyDecision:
    """Build per-file prompt/option overrides for the detected scenario."""
    resolved_scenario = _canonicalize_scenario(scenario)
    base_prompt = (base_system_prompt or "").strip()
    parts = [base_prompt] if base_prompt else []

    appendix = _PROMPT_APPENDIX_BY_SCENARIO.get(resolved_scenario, "")
    if appendix:
        parts.append(appendix)

    apply_context_flow = (
        enable_context_flow
        and bool(detected_context)
        and model_type == ModelType.GENERAL.value
        and resolved_scenario != TranslationScenario.MARKETING_PR
    )
    if apply_context_flow:
        parts.append(f"Document context: {detected_context.strip()[:240]}")

    resolved_system_prompt = "\n\n".join([p for p in parts if p]).strip()

    if model_type == ModelType.TRANSLATION.value:
        options = dict(_TRANSLATION_OPTIONS_BY_SCENARIO.get(resolved_scenario, {}))
    else:
        options = dict(_GENERAL_OPTIONS_BY_SCENARIO.get(resolved_scenario, {}))

    cache_variant = resolved_scenario.value
    if apply_context_flow:
        cache_variant = f"{cache_variant}_ctx"
    if resolved_scenario == TranslationScenario.TECHNICAL_PROCESS and model_type == ModelType.TRANSLATION.value:
        cache_variant = f"{cache_variant}_glossary"

    return StrategyDecision(
        scenario=resolved_scenario,
        system_prompt=resolved_system_prompt,
        options_override=options,
        cache_variant=cache_variant,
    )


def build_terminology_block(terms: "List[Term]") -> str:
    """Build a 'Terminology constraints' section from a list of Term objects.

    Returns an empty string when the list is empty so callers can safely
    skip appending it without special-casing.
    """
    if not terms:
        return ""
    lines = ["Terminology constraints:"]
    for t in terms:
        lines.append(f"- {t.source_text} => {t.target_text}")
    return "\n".join(lines)
