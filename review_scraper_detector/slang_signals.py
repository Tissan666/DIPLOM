"""Bilingual slang analysis with learned calibration and marketplace-aware packs."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

from .slang_marketplace_packs import MARKETPLACE_SLANG_PACKS, resolve_marketplace_pack
from .utils import make_source_group, normalize_whitespace

TOKEN_PATTERN = re.compile(r"[A-Za-z\u0400-\u04FF]+(?:['-][A-Za-z\u0400-\u04FF]+)?", flags=re.UNICODE)
DETAIL_UNIT_PATTERN = re.compile(
    r"\b\d+(?:[.,]\d+)?\s?(?:cm|mm|kg|g|mg|ml|mah|gb|tb|inch|in|"
    r"см|мм|кг|г|мг|мл|мач|дюйм)\b",
    flags=re.IGNORECASE | re.UNICODE,
)
CYRILLIC_PATTERN = re.compile(r"[\u0400-\u04FF]")
LATIN_PATTERN = re.compile(r"[A-Za-z]")

RU_SLANG_TERMS = frozenset(
    {
        "имба",
        "имбовый",
        "топчик",
        "кайф",
        "кринж",
        "жиза",
        "рофл",
        "лол",
        "угар",
        "нормас",
        "огонь",
        "пушка",
        "бомба",
        "зашло",
        "залип",
        "четко",
        "четкий",
        "мощно",
        "прикольно",
        "улет",
    }
)

TRANSLITERATED_RU_SLANG_TERMS = frozenset(
    {
        "imba",
        "topchik",
        "kayf",
        "krinzh",
        "zhiza",
        "rofl",
        "normas",
        "ogon",
        "pushka",
        "chetko",
        "zashlo",
    }
)

EN_SLANG_TERMS = frozenset(
    {
        "bro",
        "bruh",
        "fr",
        "ngl",
        "lowkey",
        "highkey",
        "legit",
        "solid",
        "fire",
        "lit",
        "dope",
        "goated",
        "sus",
        "vibe",
        "vibes",
        "clutch",
        "banger",
        "slaps",
        "mid",
        "cap",
        "clean",
    }
)

RU_SLANG_PHRASES = (
    "прям кайф",
    "вообще топ",
    "чисто кайф",
    "на изи",
    "без базара",
)

EN_SLANG_PHRASES = (
    "no cap",
    "for real",
    "straight fire",
    "big vibe",
    "super legit",
)

RU_PROMO_SLANG_PHRASES = (
    "надо брать",
    "берите не пожалеете",
    "топ за свои деньги",
    "всем советую",
    "просто пушка",
    "реально имба",
    "чистый кайф",
)

EN_PROMO_SLANG_PHRASES = (
    "must cop",
    "go buy it",
    "10/10 recommend",
    "worth it fr",
    "instant cop",
    "bestie approved",
    "you need this",
)

GENERAL_DETAIL_TERMS = frozenset(
    {
        "size",
        "fit",
        "color",
        "material",
        "delivery",
        "package",
        "packaging",
        "quality",
        "weight",
        "smell",
        "taste",
        "texture",
        "battery",
        "screen",
        "charge",
        "button",
        "comfort",
        "refund",
        "seller",
        "return",
        "размер",
        "посадка",
        "цвет",
        "материал",
        "доставка",
        "упаковка",
        "качество",
        "вес",
        "запах",
        "вкус",
        "фактура",
        "батарея",
        "экран",
        "заряд",
        "кнопка",
        "удобно",
        "возврат",
        "продавец",
    }
)

DOMAIN_PACKS: dict[str, dict[str, frozenset[str]]] = {
    "general": {
        "keywords": frozenset(),
        "detail_terms": GENERAL_DETAIL_TERMS,
    },
    "apparel": {
        "keywords": frozenset(
            {
                "shoe",
                "shoes",
                "sneaker",
                "sneakers",
                "sandals",
                "shirt",
                "dress",
                "jacket",
                "hoodie",
                "sock",
                "sole",
                "heel",
                "fabric",
                "insole",
                "обувь",
                "кроссовки",
                "сандалии",
                "футболка",
                "куртка",
                "подошва",
                "стелька",
                "ткань",
            }
        ),
        "detail_terms": frozenset(
            {
                "size",
                "fit",
                "fabric",
                "sole",
                "heel",
                "insole",
                "stitching",
                "waist",
                "sleeve",
                "collar",
                "размер",
                "посадка",
                "шов",
                "подошва",
                "стелька",
                "ткань",
            }
        ),
    },
    "electronics": {
        "keywords": frozenset(
            {
                "phone",
                "smartphone",
                "laptop",
                "tablet",
                "charger",
                "charging",
                "battery",
                "screen",
                "camera",
                "sensor",
                "headphones",
                "keyboard",
                "mouse",
                "headset",
                "power",
                "bank",
                "lamp",
                "телефон",
                "ноутбук",
                "планшет",
                "зарядка",
                "батарея",
                "экран",
                "камера",
                "наушники",
                "мышь",
                "гарнитура",
                "лампа",
            }
        ),
        "detail_terms": frozenset(
            {
                "battery",
                "screen",
                "charge",
                "charging",
                "cable",
                "camera",
                "speaker",
                "mic",
                "latency",
                "firmware",
                "display",
                "scroll",
                "cursor",
                "заряд",
                "зарядка",
                "кабель",
                "камера",
                "микрофон",
                "звук",
                "экран",
                "мышь",
                "курсор",
            }
        ),
    },
    "beauty": {
        "keywords": frozenset(
            {
                "cream",
                "serum",
                "lotion",
                "mascara",
                "lipstick",
                "skin",
                "shade",
                "scent",
                "fragrance",
                "крем",
                "сыворотка",
                "тушь",
                "помада",
                "кожа",
                "оттенок",
                "аромат",
            }
        ),
        "detail_terms": frozenset(
            {
                "shade",
                "texture",
                "scent",
                "finish",
                "coverage",
                "hydration",
                "skin",
                "оттенок",
                "фактура",
                "аромат",
                "финиш",
                "кожа",
                "увлажнение",
            }
        ),
    },
    "food": {
        "keywords": frozenset(
            {
                "coffee",
                "tea",
                "snack",
                "protein",
                "sauce",
                "flavor",
                "taste",
                "sweet",
                "salty",
                "recipe",
                "dish",
                "кофе",
                "чай",
                "вкус",
                "аромат",
                "сладкий",
                "соленый",
                "соус",
                "рецепт",
                "блюдо",
            }
        ),
        "detail_terms": frozenset(
            {
                "taste",
                "flavor",
                "aftertaste",
                "aroma",
                "sweet",
                "salty",
                "crunchy",
                "recipe",
                "вкус",
                "послевкусие",
                "аромат",
                "сладкий",
                "соленый",
                "хрустящий",
                "рецепт",
            }
        ),
    },
    "home": {
        "keywords": frozenset(
            {
                "chair",
                "table",
                "lamp",
                "pillow",
                "blanket",
                "shelf",
                "assembly",
                "wood",
                "vacuum",
                "cleaner",
                "blender",
                "jar",
                "стул",
                "стол",
                "лампа",
                "подушка",
                "плед",
                "полка",
                "сборка",
                "дерево",
                "пылесос",
                "блендер",
            }
        ),
        "detail_terms": frozenset(
            {
                "assembly",
                "wood",
                "screw",
                "fabric",
                "foam",
                "stability",
                "bin",
                "brush",
                "jar",
                "lid",
                "сборка",
                "дерево",
                "винт",
                "ткань",
                "пена",
                "устойчивость",
                "контейнер",
                "щетка",
                "крышка",
            }
        ),
    },
}

SLANG_CALIBRATION_FEATURE_NAMES = [
    "slang_rule_manipulation_score",
    "slang_rule_authenticity_score",
    "slang_density",
    "slang_diversity",
    "slang_repetition_component",
    "slang_detail_support",
    "slang_domain_grounding",
    "slang_bilingual_mix_flag",
    "slang_bilingual_hype_flag",
    "slang_hype_ratio",
    "slang_low_detail_flag",
    "slang_hit_count_scaled",
    "slang_template_dup_component",
    "slang_marketplace_hit_component",
    "slang_learned_suspicious_component",
    "slang_learned_authentic_component",
    "slang_known_marketplace_flag",
    "slang_domain_specific_flag",
]

COMMON_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "was",
        "are",
        "but",
        "not",
        "very",
        "just",
        "from",
        "have",
        "has",
        "had",
        "will",
        "your",
        "you",
        "they",
        "them",
        "their",
        "our",
        "its",
        "it",
        "есть",
        "это",
        "как",
        "для",
        "что",
        "все",
        "тоже",
        "если",
        "когда",
        "просто",
        "очень",
        "было",
        "были",
        "мне",
        "меня",
        "своих",
        "свои",
        "еще",
        "тут",
        "там",
    }
)

RESERVED_TERMS = frozenset(
    {
        *RU_SLANG_TERMS,
        *TRANSLITERATED_RU_SLANG_TERMS,
        *EN_SLANG_TERMS,
        *GENERAL_DETAIL_TERMS,
        *{term for pack in DOMAIN_PACKS.values() for term in pack["keywords"]},
        *{term for pack in DOMAIN_PACKS.values() for term in pack["detail_terms"]},
        *{
            term
            for pack in MARKETPLACE_SLANG_PACKS.values()
            for term in (
                set(pack.get("detail_terms", ()))
                | set(pack.get("slang_terms", ()))
                | set(pack.get("authentic_terms", ()))
            )
        },
    }
)

RESERVED_PHRASES = frozenset(
    {
        *RU_SLANG_PHRASES,
        *EN_SLANG_PHRASES,
        *RU_PROMO_SLANG_PHRASES,
        *EN_PROMO_SLANG_PHRASES,
        *{
            phrase
            for pack in MARKETPLACE_SLANG_PACKS.values()
            for phrase in pack.get("promo_phrases", ())
        },
    }
)


def build_page_slang_profiles(
    texts: Sequence[str],
    titles: Sequence[str] | None = None,
    source_sites: Sequence[str] | None = None,
    slang_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze slang signals across a page or dataset and return enriched per-review profiles."""
    normalized_texts = _normalize_sequence(texts, default="")
    normalized_titles = _normalize_sequence(titles or (), length=len(normalized_texts), default="")
    normalized_sources = _normalize_sequence(source_sites or (), length=len(normalized_texts), default="")
    page_domain_label, page_domain_confidence = infer_slang_domain(normalized_texts, normalized_titles)

    raw_profiles: list[dict[str, Any]] = []
    for text, title, source_site in zip(normalized_texts, normalized_titles, normalized_sources):
        local_domain_label, local_domain_confidence = infer_slang_domain([text], [title] if title else None)
        if local_domain_confidence >= max(0.45, page_domain_confidence):
            active_domain_label = local_domain_label
        else:
            active_domain_label = page_domain_label
        active_domain_terms = DOMAIN_PACKS.get(active_domain_label, DOMAIN_PACKS["general"])["detail_terms"]
        raw_profiles.append(
            analyze_slang_signals(
                text=text,
                domain_label=active_domain_label,
                domain_detail_terms=active_domain_terms,
                source_site=source_site,
                slang_model=slang_model,
            )
        )

    signature_counts = Counter(profile["slang_signature"] for profile in raw_profiles if profile["slang_signature"])
    profiles = [_finalize_profile(profile, signature_counts) for profile in raw_profiles]

    if slang_model and slang_model.get("calibrator") is not None:
        profiles = _apply_learned_slang_calibration(profiles, slang_model)

    return {
        "dominant_domain": page_domain_label,
        "domain_confidence": float(page_domain_confidence),
        "dominant_marketplace": _dominant_marketplace_label(profiles),
        "slang_template_cluster_ratio": float(
            sum(int(profile["slang_template_cluster_flag"]) for profile in profiles) / max(len(profiles), 1)
        ),
        "slang_model_strategy": str((slang_model or {}).get("strategy", "rule_based")),
        "profiles": profiles,
    }


def infer_slang_domain(texts: Sequence[str], titles: Sequence[str] | None = None) -> tuple[str, float]:
    """Infer the likely product domain from review text and available titles."""
    corpus = " ".join(part.lower() for part in [*texts, *(titles or ())] if part)
    tokens = TOKEN_PATTERN.findall(corpus)
    if not tokens and not corpus:
        return "general", 0.0

    scores: dict[str, int] = {}
    for domain_label, pack in DOMAIN_PACKS.items():
        if domain_label == "general":
            continue
        keyword_hits = sum(1 for token in tokens if token in pack["keywords"])
        scores[domain_label] = keyword_hits

    if not scores:
        return "general", 0.0

    dominant_domain, dominant_score = max(scores.items(), key=lambda item: item[1])
    total_score = sum(scores.values())
    if dominant_score < 2:
        return "general", 0.0
    return dominant_domain, float(dominant_score / max(total_score, 1))


def analyze_slang_signals(
    text: str,
    domain_label: str = "general",
    domain_detail_terms: frozenset[str] | None = None,
    source_site: str = "",
    slang_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return bilingual slang features for one review."""
    normalized_text = normalize_whitespace(text).lower()
    tokens = TOKEN_PATTERN.findall(normalized_text)
    token_count = len(tokens)

    marketplace_label, marketplace_pack = resolve_marketplace_pack(source_site)
    learned_lexicon = (slang_model or {}).get("learned_lexicon", {})
    learned_marketplace_pack = _resolve_learned_marketplace_pack(learned_lexicon, source_site, marketplace_label)
    active_domain_terms = set(domain_detail_terms or DOMAIN_PACKS["general"]["detail_terms"])
    active_domain_terms.update(marketplace_pack.get("detail_terms", ()))

    if token_count == 0:
        empty_profile = _empty_profile(domain_label, marketplace_label)
        empty_profile["slang_known_marketplace_flag"] = float(marketplace_label != "generic")
        return empty_profile

    active_ru_terms = set(RU_SLANG_TERMS)
    active_translit_terms = set(TRANSLITERATED_RU_SLANG_TERMS)
    active_en_terms = set(EN_SLANG_TERMS)
    active_marketplace_slang_terms = set(marketplace_pack.get("slang_terms", ()))
    active_promo_phrases = (
        *RU_PROMO_SLANG_PHRASES,
        *EN_PROMO_SLANG_PHRASES,
        *tuple(marketplace_pack.get("promo_phrases", ())),
        *tuple(learned_marketplace_pack.get("promo_phrases", ())),
    )
    learned_suspicious_terms = set(learned_lexicon.get("general_suspicious_terms", ()))
    learned_suspicious_terms.update(learned_marketplace_pack.get("suspicious_terms", ()))
    learned_authentic_terms = set(learned_lexicon.get("general_authentic_terms", ()))
    learned_authentic_terms.update(learned_marketplace_pack.get("authentic_terms", ()))
    learned_authentic_phrases = (
        *tuple(learned_lexicon.get("general_authentic_phrases", ())),
        *tuple(learned_marketplace_pack.get("authentic_phrases", ())),
    )

    ru_hits = [token for token in tokens if token in active_ru_terms]
    translit_hits = [token for token in tokens if token in active_translit_terms]
    en_hits = [token for token in tokens if token in active_en_terms]
    marketplace_slang_hits = [token for token in tokens if token in active_marketplace_slang_terms]
    ru_phrase_hits = _find_phrase_hits(normalized_text, RU_SLANG_PHRASES)
    en_phrase_hits = _find_phrase_hits(normalized_text, EN_SLANG_PHRASES)
    promo_phrase_hits = _find_phrase_hits(normalized_text, active_promo_phrases)
    learned_suspicious_phrase_hits = _find_phrase_hits(normalized_text, tuple(learned_lexicon.get("general_suspicious_phrases", ())))
    learned_suspicious_phrase_hits.extend(_find_phrase_hits(normalized_text, tuple(learned_marketplace_pack.get("suspicious_phrases", ()))))
    learned_authentic_phrase_hits = _find_phrase_hits(normalized_text, learned_authentic_phrases)
    learned_suspicious_hits = _find_token_hits(tokens, learned_suspicious_terms)
    learned_authentic_hits = _find_token_hits(tokens, learned_authentic_terms)

    slang_terms = [*ru_hits, *translit_hits, *en_hits, *marketplace_slang_hits, *ru_phrase_hits, *en_phrase_hits]
    slang_hit_count = len(slang_terms)
    unique_slang_terms = sorted(set(slang_terms))
    unique_slang_count = len(unique_slang_terms)
    slang_density = float(slang_hit_count / max(token_count, 1))
    slang_diversity = float(unique_slang_count / max(slang_hit_count, 1)) if slang_hit_count else 0.0
    slang_repetition = 0.0 if slang_hit_count == 0 else float(1.0 - slang_diversity)

    general_detail_hits = sum(1 for token in tokens if token in GENERAL_DETAIL_TERMS)
    domain_detail_hits = sum(1 for token in tokens if token in active_domain_terms)
    unit_hits = len(DETAIL_UNIT_PATTERN.findall(normalized_text))
    detail_support = min((general_detail_hits + domain_detail_hits + unit_hits) / 3.0, 1.0)
    domain_grounding = min((domain_detail_hits + unit_hits) / 2.0, 1.0) if domain_label != "general" else detail_support

    cyrillic_tokens = sum(1 for token in tokens if CYRILLIC_PATTERN.search(token))
    latin_tokens = sum(1 for token in tokens if LATIN_PATTERN.search(token))
    bilingual_mix_flag = float(cyrillic_tokens > 0 and latin_tokens > 0)
    mixed_script_balance = 0.0
    if bilingual_mix_flag:
        token_base = max(cyrillic_tokens + latin_tokens, 1)
        mixed_script_balance = 1.0 - abs(cyrillic_tokens - latin_tokens) / token_base

    hype_hits = len(promo_phrase_hits)
    hype_ratio = float(hype_hits / max(slang_hit_count + hype_hits, 1)) if (slang_hit_count + hype_hits) else 0.0
    density_pressure = _clip((slang_density - 0.12) / 0.18)
    moderate_density = 0.0 if slang_hit_count == 0 else 1.0 - min(abs(slang_density - 0.10) / 0.10, 1.0)
    low_detail_flag = float(slang_hit_count > 0 and detail_support < 0.34 and token_count <= 20)
    bilingual_hype_flag = float(bilingual_mix_flag == 1.0 and (hype_hits > 0 or slang_density >= 0.16) and detail_support < 0.5)
    length_support = min(token_count / 18.0, 1.0)
    grounded_bilingual_bonus = bilingual_mix_flag * mixed_script_balance * min(detail_support, 0.9)

    marketplace_hit_count = (
        len(marketplace_slang_hits)
        + len(promo_phrase_hits)
        + min(domain_detail_hits, 2)
        + len(_find_token_hits(tokens, set(marketplace_pack.get("authentic_terms", ()))))
    )
    marketplace_hit_component = _clip(marketplace_hit_count / 4.0)
    learned_suspicious_count = len(learned_suspicious_hits) + len(learned_suspicious_phrase_hits)
    learned_authentic_count = len(learned_authentic_hits) + len(learned_authentic_phrase_hits)
    learned_suspicious_component = _clip(learned_suspicious_count / 3.0)
    learned_authentic_component = _clip(learned_authentic_count / 3.0)
    known_marketplace_flag = float(marketplace_label != "generic")
    domain_specific_flag = float(domain_label != "general")

    if (
        slang_hit_count == 0
        and hype_hits == 0
        and learned_suspicious_count == 0
        and learned_authentic_count == 0
        and marketplace_hit_count == 0
    ):
        authenticity_score = 0.5
        manipulation_score = 0.0
        profile_label = "neutral"
    else:
        authenticity_score = _clip(
            0.26 * moderate_density
            + 0.22 * detail_support
            + 0.16 * domain_grounding
            + 0.08 * slang_diversity
            + 0.08 * length_support
            + 0.10 * grounded_bilingual_bonus
            + 0.12 * learned_authentic_component
            + 0.05 * marketplace_hit_component * detail_support
            - 0.22 * hype_ratio
            - 0.14 * slang_repetition
            - 0.18 * bilingual_hype_flag
            - 0.10 * low_detail_flag
            - 0.12 * learned_suspicious_component
        )
        manipulation_score = _clip(
            0.18 * density_pressure
            + 0.18 * hype_ratio
            + 0.12 * slang_repetition
            + 0.16 * bilingual_hype_flag
            + 0.08 * low_detail_flag
            + 0.06 * max(0.0, 0.55 - domain_grounding)
            + 0.14 * learned_suspicious_component
            + 0.04 * marketplace_hit_component * max(0.0, 1.0 - detail_support)
            - 0.14 * detail_support
            - 0.10 * moderate_density
            - 0.06 * grounded_bilingual_bonus
            - 0.12 * learned_authentic_component
        )
        profile_label = _profile_label(authenticity_score, manipulation_score)

    return {
        "slang_rule_authenticity_score": float(authenticity_score),
        "slang_rule_manipulation_score": float(manipulation_score),
        "slang_authenticity_score": float(authenticity_score),
        "slang_manipulation_score": float(manipulation_score),
        "slang_density": float(slang_density),
        "slang_diversity": float(slang_diversity),
        "slang_repetition_component": float(slang_repetition),
        "slang_detail_support": float(detail_support),
        "slang_domain_grounding": float(domain_grounding),
        "slang_bilingual_mix_flag": float(bilingual_mix_flag),
        "slang_bilingual_hype_flag": float(bilingual_hype_flag),
        "slang_hype_ratio": float(hype_ratio),
        "slang_low_detail_flag": float(low_detail_flag),
        "slang_hit_count": int(slang_hit_count),
        "slang_profile_label": profile_label,
        "slang_terms": unique_slang_terms[:6],
        "slang_domain_label": domain_label,
        "slang_domain_detail_hits": int(domain_detail_hits),
        "slang_marketplace_label": marketplace_label,
        "slang_marketplace_hit_count": int(marketplace_hit_count),
        "slang_marketplace_hit_component": float(marketplace_hit_component),
        "slang_learned_suspicious_count": int(learned_suspicious_count),
        "slang_learned_authentic_count": int(learned_authentic_count),
        "slang_learned_suspicious_component": float(learned_suspicious_component),
        "slang_learned_authentic_component": float(learned_authentic_component),
        "slang_known_marketplace_flag": float(known_marketplace_flag),
        "slang_domain_specific_flag": float(domain_specific_flag),
        "slang_signature": _build_signature(
            terms=unique_slang_terms,
            bilingual_mix_flag=bilingual_mix_flag,
            hype_ratio=hype_ratio,
            low_detail_flag=low_detail_flag,
            domain_label=domain_label,
            marketplace_label=marketplace_label,
        ),
        "slang_template_dup_count": 0,
        "slang_template_dup_component": 0.0,
        "slang_template_cluster_flag": 0.0,
        "slang_learned_probability": float(manipulation_score),
        "slang_calibration_delta": 0.0,
    }


def learn_slang_lexicon(
    review_df: pd.DataFrame,
    labels: Sequence[int] | np.ndarray,
    min_support: int = 2,
    max_terms: int = 12,
    max_phrases: int = 8,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Expand slang lexicons from the current training corpus."""
    frame = _prepare_learning_frame(review_df, labels)
    lexicon_corpus, corpus_scope = _select_lexicon_corpus(frame)
    if lexicon_corpus.empty or lexicon_corpus["label"].nunique() < 2:
        empty_lexicon = {
            "general_suspicious_terms": [],
            "general_authentic_terms": [],
            "general_suspicious_phrases": [],
            "general_authentic_phrases": [],
            "marketplace_packs": {},
        }
        return empty_lexicon, {
            "corpus_scope": corpus_scope,
            "records_used": int(len(lexicon_corpus)),
            "general_term_count": 0,
            "general_phrase_count": 0,
            "marketplace_pack_count": 0,
        }

    general_pack = _learn_candidate_pack(
        lexicon_corpus,
        min_support=min_support,
        max_terms=max_terms,
        max_phrases=max_phrases,
    )
    marketplace_packs: dict[str, dict[str, list[str]]] = {}
    for source_label, group in lexicon_corpus.groupby("source_group"):
        if len(group) < 18 or group["label"].nunique() < 2:
            continue
        learned_pack = _learn_candidate_pack(
            group,
            min_support=min_support,
            max_terms=min(6, max_terms),
            max_phrases=min(4, max_phrases),
        )
        if any(learned_pack.values()):
            marketplace_packs[str(source_label)] = learned_pack

    learned_lexicon = {
        "general_suspicious_terms": general_pack["suspicious_terms"],
        "general_authentic_terms": general_pack["authentic_terms"],
        "general_suspicious_phrases": general_pack["suspicious_phrases"],
        "general_authentic_phrases": general_pack["authentic_phrases"],
        "marketplace_packs": marketplace_packs,
    }
    return learned_lexicon, {
        "corpus_scope": corpus_scope,
        "records_used": int(len(lexicon_corpus)),
        "general_term_count": int(len(general_pack["suspicious_terms"]) + len(general_pack["authentic_terms"])),
        "general_phrase_count": int(len(general_pack["suspicious_phrases"]) + len(general_pack["authentic_phrases"])),
        "marketplace_pack_count": int(len(marketplace_packs)),
        "marketplace_labels": sorted(marketplace_packs.keys()),
        "sample_general_suspicious_terms": general_pack["suspicious_terms"][:8],
        "sample_general_authentic_terms": general_pack["authentic_terms"][:8],
    }


def train_slang_signal_calibrator(
    review_df: pd.DataFrame,
    labels: Sequence[int] | np.ndarray,
    learned_lexicon: dict[str, Any] | None = None,
    random_state: int = 42,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Train a compact slang-specific calibrator on a validation holdout."""
    frame = _prepare_learning_frame(review_df, labels)
    if frame.empty or frame["label"].nunique() < 2:
        raise ValueError("Slang calibration requires both classes on the validation split.")

    warmup_model = {
        "strategy": "rule_plus_lexicon",
        "learned_lexicon": learned_lexicon or {},
    }
    slang_page_context = build_page_slang_profiles(
        texts=frame["review_text"].tolist(),
        titles=frame["title"].tolist(),
        source_sites=frame["source_group"].tolist(),
        slang_model=warmup_model,
    )
    profile_frame = pd.DataFrame(slang_page_context["profiles"], index=frame.index)
    feature_matrix = _build_slang_feature_matrix(profile_frame)
    calibration_labels = frame["label"].to_numpy(dtype=np.int32)

    calibrator = LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        random_state=random_state,
    )
    calibrator.fit(feature_matrix, calibration_labels)
    fitted_probabilities = calibrator.predict_proba(feature_matrix)[:, 1].astype(float)
    error_analysis = _collect_slang_error_analysis(
        review_frame=frame,
        profile_frame=profile_frame,
        probabilities=fitted_probabilities,
    )

    slang_model = {
        "strategy": "validation_learned_calibrator",
        "feature_names": list(SLANG_CALIBRATION_FEATURE_NAMES),
        "calibrator": calibrator,
        "learned_lexicon": learned_lexicon or {},
    }
    calibration_report = {
        "feature_names": list(SLANG_CALIBRATION_FEATURE_NAMES),
        "coefficients": {
            name: float(value)
            for name, value in zip(SLANG_CALIBRATION_FEATURE_NAMES, calibrator.coef_[0], strict=False)
        },
        "intercept": float(calibrator.intercept_[0]),
        "fit_log_loss": float(log_loss(calibration_labels, fitted_probabilities)),
        "fit_brier_score": float(brier_score_loss(calibration_labels, fitted_probabilities)),
        "false_positive_false_negative_analysis": error_analysis,
        "marketplace_pack_count": int(len((learned_lexicon or {}).get("marketplace_packs", {}))),
        "dominant_domain": str(slang_page_context.get("dominant_domain", "general")),
        "dominant_marketplace": str(slang_page_context.get("dominant_marketplace", "generic")),
    }
    return slang_model, calibration_report


def build_slang_suspicion_reason(profile: dict[str, Any]) -> str | None:
    """Create a human-readable reason when slang usage looks suspicious."""
    manipulation_score = float(profile.get("slang_manipulation_score", 0.0) or 0.0)
    if manipulation_score < 0.45:
        return None

    template_dup_count = int(profile.get("slang_template_dup_count", 0) or 0)
    bilingual_hype = float(profile.get("slang_bilingual_hype_flag", 0.0) or 0.0)
    low_detail = float(profile.get("slang_low_detail_flag", 0.0) or 0.0)
    hype_ratio = float(profile.get("slang_hype_ratio", 0.0) or 0.0)
    domain_label = str(profile.get("slang_domain_label", "general") or "general")
    marketplace_label = str(profile.get("slang_marketplace_label", "generic") or "generic")
    learned_suspicious_count = int(profile.get("slang_learned_suspicious_count", 0) or 0)

    if template_dup_count >= 2:
        return "A similar slang signature appears across multiple reviews, which looks coordinated."
    if learned_suspicious_count >= 2 and marketplace_label != "generic":
        return f"The wording matches suspicious slang patterns learned from {marketplace_label}-style reviews."
    if bilingual_hype >= 1.0:
        return "The review mixes Russian and English hype slang in a way that looks orchestrated rather than natural."
    if low_detail >= 1.0 and hype_ratio >= 0.2:
        if marketplace_label != "generic":
            return (
                f"The comment uses hype-heavy {marketplace_label}-style slang but gives little grounded delivery "
                "or product detail."
            )
        if domain_label != "general":
            return f"The slang-heavy tone contains little {domain_label}-specific detail, which can indicate scripted hype."
        return "The slang-heavy tone contains little concrete product detail, which can indicate scripted hype."
    return "The slang pattern looks unusually hype-driven for a natural customer comment."


def _apply_learned_slang_calibration(
    profiles: list[dict[str, Any]],
    slang_model: dict[str, Any],
) -> list[dict[str, Any]]:
    """Apply a trained slang calibrator on top of rule-based slang features."""
    calibrator = slang_model.get("calibrator")
    if calibrator is None or not profiles:
        return profiles

    profile_frame = pd.DataFrame(profiles)
    probabilities = calibrator.predict_proba(_build_slang_feature_matrix(profile_frame))[:, 1].astype(float)
    calibrated_profiles: list[dict[str, Any]] = []
    for profile, probability in zip(profiles, probabilities):
        updated = dict(profile)
        rule_manipulation = float(updated.get("slang_rule_manipulation_score", updated.get("slang_manipulation_score", 0.0)) or 0.0)
        rule_authenticity = float(updated.get("slang_rule_authenticity_score", updated.get("slang_authenticity_score", 0.5)) or 0.5)
        calibrated_manipulation = _clip(0.25 * rule_manipulation + 0.75 * probability)
        calibrated_authenticity = _clip(0.35 * rule_authenticity + 0.65 * (1.0 - probability))
        updated["slang_learned_probability"] = float(probability)
        updated["slang_calibration_delta"] = float(calibrated_manipulation - rule_manipulation)
        updated["slang_manipulation_score"] = float(calibrated_manipulation)
        updated["slang_authenticity_score"] = float(calibrated_authenticity)
        updated["slang_profile_label"] = _profile_label(calibrated_authenticity, calibrated_manipulation)
        calibrated_profiles.append(updated)
    return calibrated_profiles


def _build_slang_feature_matrix(profile_frame: pd.DataFrame) -> np.ndarray:
    """Convert per-review slang profiles into a stable calibration matrix."""
    frame = profile_frame.reset_index(drop=True).copy()
    return np.column_stack(
        [
            np.clip(_numeric_column(frame, "slang_rule_manipulation_score"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "slang_rule_authenticity_score", default=0.5), 0.0, 1.0),
            np.clip(_numeric_column(frame, "slang_density"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "slang_diversity"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "slang_repetition_component"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "slang_detail_support"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "slang_domain_grounding"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "slang_bilingual_mix_flag"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "slang_bilingual_hype_flag"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "slang_hype_ratio"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "slang_low_detail_flag"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "slang_hit_count") / 6.0, 0.0, 1.0),
            np.clip(_numeric_column(frame, "slang_template_dup_component"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "slang_marketplace_hit_component"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "slang_learned_suspicious_component"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "slang_learned_authentic_component"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "slang_known_marketplace_flag"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "slang_domain_specific_flag"), 0.0, 1.0),
        ]
    ).astype(np.float32)


def _collect_slang_error_analysis(
    review_frame: pd.DataFrame,
    profile_frame: pd.DataFrame,
    probabilities: np.ndarray,
) -> dict[str, Any]:
    """Summarize slang-model false positives and false negatives on the validation split."""
    frame = review_frame.copy().reset_index(drop=True)
    profiles = profile_frame.copy().reset_index(drop=True)
    frame = pd.concat([frame, profiles], axis=1)
    frame["slang_probability"] = np.asarray(probabilities, dtype=float).reshape(-1)
    frame["slang_prediction"] = (frame["slang_probability"] >= 0.5).astype(int)

    false_positive_frame = frame.loc[(frame["label"] == 0) & (frame["slang_prediction"] == 1)].reset_index(drop=True)
    false_negative_frame = frame.loc[(frame["label"] == 1) & (frame["slang_prediction"] == 0)].reset_index(drop=True)

    return {
        "false_positive_count": int(len(false_positive_frame)),
        "false_negative_count": int(len(false_negative_frame)),
        "false_positive_share": float(len(false_positive_frame) / max(int((frame["label"] == 0).sum()), 1)),
        "false_negative_share": float(len(false_negative_frame) / max(int((frame["label"] == 1).sum()), 1)),
        "false_positives": _summarize_error_bucket(false_positive_frame),
        "false_negatives": _summarize_error_bucket(false_negative_frame),
    }


def _summarize_error_bucket(frame: pd.DataFrame) -> dict[str, Any]:
    """Aggregate one error bucket into compact diagnostics."""
    if frame.empty:
        return {
            "top_slang_terms": [],
            "source_distribution": {},
            "product_family_distribution": {},
            "origin_family_distribution": {},
            "marketplace_distribution": {},
            "examples": [],
        }

    term_counter = Counter()
    for terms in frame.get("slang_terms", []):
        for term in terms or []:
            term_counter[str(term)] += 1

    return {
        "top_slang_terms": [
            {"term": term, "count": count}
            for term, count in term_counter.most_common(8)
        ],
        "source_distribution": {
            str(key): int(value)
            for key, value in frame["source"].fillna("unspecified").astype(str).value_counts().head(6).items()
        },
        "product_family_distribution": {
            str(key): int(value)
            for key, value in frame["product_family"].fillna("general").astype(str).value_counts().head(6).items()
        },
        "origin_family_distribution": {
            str(key): int(value)
            for key, value in frame["origin_family"].fillna("").astype(str).value_counts().head(6).items()
            if str(key).strip()
        },
        "marketplace_distribution": {
            str(key): int(value)
            for key, value in frame["slang_marketplace_label"].fillna("generic").astype(str).value_counts().head(6).items()
        },
        "examples": [
            {
                "probability": float(row["slang_probability"]),
                "source": str(row.get("source", "unspecified") or "unspecified"),
                "product_family": str(row.get("product_family", "general") or "general"),
                "origin_family": str(row.get("origin_family", "") or ""),
                "marketplace_label": str(row.get("slang_marketplace_label", "generic") or "generic"),
                "profile_label": str(row.get("slang_profile_label", "neutral") or "neutral"),
                "slang_terms": list(row.get("slang_terms", []) or []),
                "text_preview": normalize_whitespace(str(row.get("review_text", "")))[:160],
            }
            for _, row in frame.sort_values("slang_probability", ascending=False).head(6).iterrows()
        ],
    }


def _prepare_learning_frame(review_df: pd.DataFrame, labels: Sequence[int] | np.ndarray) -> pd.DataFrame:
    """Normalize review rows for slang learning and diagnostics."""
    frame = review_df.copy().reset_index(drop=True)
    if len(frame) != len(labels):
        raise ValueError("Slang learning requires one label per review row.")
    frame["label"] = np.asarray(labels, dtype=np.int32).reshape(-1)
    if "review_text" not in frame.columns:
        raise ValueError("Review slang learning requires a `review_text` column.")
    frame["review_text"] = frame["review_text"].fillna("").astype(str).map(normalize_whitespace)
    if "title" not in frame.columns:
        frame["title"] = ""
    frame["title"] = frame["title"].fillna("").astype(str).map(normalize_whitespace)
    if "source" not in frame.columns:
        frame["source"] = "unspecified"
    frame["source"] = frame["source"].fillna("unspecified").astype(str)
    if "product_family" not in frame.columns:
        frame["product_family"] = "general"
    frame["product_family"] = frame["product_family"].fillna("general").astype(str)
    if "origin_family" not in frame.columns:
        frame["origin_family"] = ""
    frame["origin_family"] = frame["origin_family"].fillna("").astype(str)
    frame["source_group"] = frame["source"].map(_canonical_source_label)
    return frame


def _select_lexicon_corpus(frame: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Prefer non-synthetic corpora when they are large enough for lexicon mining."""
    synthetic_mask = frame["source"].str.startswith("synthetic_")
    real_frame = frame.loc[~synthetic_mask].reset_index(drop=True)
    if len(real_frame) >= 60 and real_frame["label"].nunique() >= 2:
        return real_frame, "real_only"
    return frame.reset_index(drop=True), "mixed_real_and_synthetic"


def _learn_candidate_pack(
    frame: pd.DataFrame,
    min_support: int,
    max_terms: int,
    max_phrases: int,
) -> dict[str, list[str]]:
    """Mine differential slang-like terms and phrases from one corpus bucket."""
    token_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    phrase_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    positive_docs = int(frame["label"].sum())
    negative_docs = int(len(frame) - positive_docs)
    if positive_docs <= 0 or negative_docs <= 0:
        return {
            "suspicious_terms": [],
            "authentic_terms": [],
            "suspicious_phrases": [],
            "authentic_phrases": [],
            "promo_phrases": [],
        }

    for text, label in zip(frame["review_text"], frame["label"]):
        token_candidates = _extract_candidate_tokens(text)
        phrase_candidates = _extract_candidate_phrases(text)
        for token in token_candidates:
            token_counts[token][0] += 1
            token_counts[token][1] += int(label)
        for phrase in phrase_candidates:
            phrase_counts[phrase][0] += 1
            phrase_counts[phrase][1] += int(label)

    suspicious_terms = _select_ranked_candidates(
        counts=token_counts,
        positive_docs=positive_docs,
        negative_docs=negative_docs,
        polarity="suspicious",
        min_support=min_support,
        max_items=max_terms,
    )
    authentic_terms = _select_ranked_candidates(
        counts=token_counts,
        positive_docs=positive_docs,
        negative_docs=negative_docs,
        polarity="authentic",
        min_support=min_support,
        max_items=max_terms,
    )
    suspicious_phrases = _select_ranked_candidates(
        counts=phrase_counts,
        positive_docs=positive_docs,
        negative_docs=negative_docs,
        polarity="suspicious",
        min_support=min_support,
        max_items=max_phrases,
    )
    authentic_phrases = _select_ranked_candidates(
        counts=phrase_counts,
        positive_docs=positive_docs,
        negative_docs=negative_docs,
        polarity="authentic",
        min_support=min_support,
        max_items=max_phrases,
    )
    promo_phrases = [phrase for phrase in suspicious_phrases if _looks_promotional_phrase(phrase)][:4]
    return {
        "suspicious_terms": suspicious_terms,
        "authentic_terms": authentic_terms,
        "suspicious_phrases": suspicious_phrases,
        "authentic_phrases": authentic_phrases,
        "promo_phrases": promo_phrases,
    }


def _extract_candidate_tokens(text: str) -> set[str]:
    """Extract slang-like token candidates for lexicon expansion."""
    tokens = TOKEN_PATTERN.findall(normalize_whitespace(text).lower())
    candidates = {
        token
        for token in tokens
        if _is_expandable_token_candidate(token)
    }
    return candidates


def _extract_candidate_phrases(text: str) -> set[str]:
    """Extract lightweight phrase candidates for slang lexicon expansion."""
    tokens = [
        token
        for token in TOKEN_PATTERN.findall(normalize_whitespace(text).lower())
        if token not in COMMON_STOPWORDS and not token.isdigit()
    ]
    phrases: set[str] = set()
    for ngram_size in (2, 3):
        for index in range(0, max(len(tokens) - ngram_size + 1, 0)):
            phrase_tokens = tokens[index : index + ngram_size]
            if len(phrase_tokens) < ngram_size:
                continue
            if not any(_is_expandable_token_candidate(token) for token in phrase_tokens):
                continue
            phrase = " ".join(phrase_tokens)
            if phrase in RESERVED_PHRASES or len(phrase) > 48:
                continue
            phrases.add(phrase)
    return phrases


def _select_ranked_candidates(
    counts: dict[str, list[int]],
    positive_docs: int,
    negative_docs: int,
    polarity: str,
    min_support: int,
    max_items: int,
) -> list[str]:
    """Select the strongest suspicious or authentic candidates from one count table."""
    ranked: list[tuple[float, str]] = []
    for candidate, (document_count, positive_count) in counts.items():
        if document_count < min_support:
            continue
        authentic_count = document_count - positive_count
        score = ((positive_count + 0.5) / (positive_docs + 1.0)) - ((authentic_count + 0.5) / (negative_docs + 1.0))
        if polarity == "suspicious" and score < 0.03:
            continue
        if polarity == "authentic" and score > -0.03:
            continue
        ranked.append((abs(score) * np.log1p(document_count), candidate))

    ranked.sort(reverse=True)
    return [candidate for _, candidate in ranked[:max_items]]


def _resolve_learned_marketplace_pack(
    learned_lexicon: dict[str, Any],
    source_site: str,
    marketplace_label: str,
) -> dict[str, Any]:
    """Resolve a learned marketplace/source pack from the stored lexicon."""
    marketplace_packs = learned_lexicon.get("marketplace_packs", {})
    source_label = _canonical_source_label(source_site)
    if source_label in marketplace_packs:
        return marketplace_packs[source_label]
    if marketplace_label in marketplace_packs:
        return marketplace_packs[marketplace_label]
    return {}


def _canonical_source_label(source_value: Any) -> str:
    """Normalize one dataset source or site into a stable marketplace-aware key."""
    marketplace_label, _ = resolve_marketplace_pack(source_value)
    if marketplace_label != "generic":
        return marketplace_label
    return make_source_group(source_value)


def _dominant_marketplace_label(profiles: list[dict[str, Any]]) -> str:
    """Return the dominant non-generic marketplace label across profiles."""
    labels = [str(profile.get("slang_marketplace_label", "generic") or "generic") for profile in profiles]
    non_generic = [label for label in labels if label != "generic"]
    if not non_generic:
        return "generic"
    return Counter(non_generic).most_common(1)[0][0]


def _finalize_profile(profile: dict[str, Any], signature_counts: Counter[str]) -> dict[str, Any]:
    """Inject page-level slang-template duplication into one profile."""
    signature = str(profile.get("slang_signature", "") or "")
    if not signature:
        profile["slang_profile_label"] = _profile_label(
            float(profile.get("slang_authenticity_score", 0.5) or 0.5),
            float(profile.get("slang_manipulation_score", 0.0) or 0.0),
        )
        return profile

    duplicate_count = int(signature_counts.get(signature, 0))
    duplicate_component = _clip((duplicate_count - 1.0) / 2.0)
    profile["slang_template_dup_count"] = duplicate_count
    profile["slang_template_dup_component"] = float(duplicate_component)
    profile["slang_template_cluster_flag"] = float(duplicate_count >= 2)
    profile["slang_rule_authenticity_score"] = _clip(
        float(profile["slang_rule_authenticity_score"]) - 0.08 * duplicate_component
    )
    profile["slang_rule_manipulation_score"] = _clip(
        float(profile["slang_rule_manipulation_score"]) + 0.18 * duplicate_component
    )
    profile["slang_authenticity_score"] = float(profile["slang_rule_authenticity_score"])
    profile["slang_manipulation_score"] = float(profile["slang_rule_manipulation_score"])
    profile["slang_profile_label"] = _profile_label(
        float(profile["slang_authenticity_score"]),
        float(profile["slang_manipulation_score"]),
    )
    return profile


def _build_signature(
    terms: list[str],
    bilingual_mix_flag: float,
    hype_ratio: float,
    low_detail_flag: float,
    domain_label: str,
    marketplace_label: str,
) -> str:
    """Create a stable slang signature for page-level duplication analysis."""
    if not terms:
        return ""

    core_terms = terms[:3]
    flags: list[str] = []
    if bilingual_mix_flag >= 1.0:
        flags.append("mix")
    if hype_ratio >= 0.2:
        flags.append("promo")
    if low_detail_flag >= 1.0:
        flags.append("thin")
    if domain_label != "general":
        flags.append(domain_label)
    if marketplace_label != "generic":
        flags.append(marketplace_label)

    if len(core_terms) < 2 and not flags:
        return ""
    return "|".join([*core_terms, *flags])


def _profile_label(authenticity_score: float, manipulation_score: float) -> str:
    """Convert raw scores into a compact language-profile label."""
    if manipulation_score >= 0.58:
        return "suspicious"
    if authenticity_score >= 0.62 and manipulation_score < 0.30:
        return "organic"
    if manipulation_score <= 0.05 and authenticity_score <= 0.55:
        return "neutral"
    return "mixed"


def _find_phrase_hits(text: str, phrases: tuple[str, ...] | Sequence[str]) -> list[str]:
    """Return the slang phrases that appear in the text."""
    return [phrase for phrase in phrases if phrase and phrase in text]


def _find_token_hits(tokens: Sequence[str], candidate_terms: set[str]) -> list[str]:
    """Return unique candidate token hits while preserving sortability."""
    return sorted({token for token in tokens if token in candidate_terms})


def _normalize_sequence(
    values: Sequence[str],
    length: int | None = None,
    default: str = "",
) -> list[str]:
    """Normalize an optional string sequence and optionally broadcast it."""
    normalized = [normalize_whitespace(str(value or "")) for value in values]
    if length is None:
        return normalized
    if len(normalized) < length:
        normalized.extend([default] * (length - len(normalized)))
    return normalized[:length]


def _empty_profile(domain_label: str, marketplace_label: str) -> dict[str, Any]:
    """Return a neutral profile for empty or whitespace-only text."""
    return {
        "slang_rule_authenticity_score": 0.5,
        "slang_rule_manipulation_score": 0.0,
        "slang_authenticity_score": 0.5,
        "slang_manipulation_score": 0.0,
        "slang_density": 0.0,
        "slang_diversity": 0.0,
        "slang_repetition_component": 0.0,
        "slang_detail_support": 0.0,
        "slang_domain_grounding": 0.0,
        "slang_bilingual_mix_flag": 0.0,
        "slang_bilingual_hype_flag": 0.0,
        "slang_hype_ratio": 0.0,
        "slang_low_detail_flag": 0.0,
        "slang_hit_count": 0,
        "slang_profile_label": "neutral",
        "slang_terms": [],
        "slang_domain_label": domain_label,
        "slang_domain_detail_hits": 0,
        "slang_marketplace_label": marketplace_label,
        "slang_marketplace_hit_count": 0,
        "slang_marketplace_hit_component": 0.0,
        "slang_learned_suspicious_count": 0,
        "slang_learned_authentic_count": 0,
        "slang_learned_suspicious_component": 0.0,
        "slang_learned_authentic_component": 0.0,
        "slang_known_marketplace_flag": float(marketplace_label != "generic"),
        "slang_domain_specific_flag": float(domain_label != "general"),
        "slang_signature": "",
        "slang_template_dup_count": 0,
        "slang_template_dup_component": 0.0,
        "slang_template_cluster_flag": 0.0,
        "slang_learned_probability": 0.0,
        "slang_calibration_delta": 0.0,
    }


def _is_expandable_token_candidate(token: str) -> bool:
    """Filter tokens before considering them for learned slang lexicons."""
    if not token or token.isdigit():
        return False
    if len(token) < 3 or len(token) > 18:
        return False
    if token in COMMON_STOPWORDS or token in RESERVED_TERMS:
        return False
    if len(set(token)) == 1:
        return False
    return True


def _looks_promotional_phrase(phrase: str) -> bool:
    """Identify phrases that look like soft-sell or hard-sell language."""
    promo_markers = (
        "buy",
        "grab",
        "must",
        "worth",
        "need",
        "cop",
        "берите",
        "надо",
        "брать",
        "советую",
        "топ",
    )
    return any(marker in phrase for marker in promo_markers)


def _numeric_column(frame: pd.DataFrame, column: str, default: float = 0.0) -> np.ndarray:
    """Return one numeric profile column with a stable fallback."""
    if column not in frame.columns:
        return np.full(len(frame), float(default), dtype=np.float32)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).to_numpy(dtype=np.float32)


def _clip(value: float) -> float:
    """Clamp a floating-point score into the [0, 1] interval."""
    return float(max(0.0, min(1.0, value)))
