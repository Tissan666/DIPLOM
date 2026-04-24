"""Marketplace-specific slang and detail packs used by the slang detector."""

from __future__ import annotations

from typing import Any

from .utils import normalize_group_component

_EMPTY_PACK = {
    "aliases": tuple(),
    "detail_terms": frozenset(),
    "slang_terms": frozenset(),
    "authentic_terms": frozenset(),
    "promo_phrases": tuple(),
}

MARKETPLACE_SLANG_PACKS: dict[str, dict[str, object]] = {
    "amazon": {
        "aliases": ("amazon", "prime", "fba"),
        "detail_terms": frozenset(
            {
                "prime",
                "seller",
                "listing",
                "warehouse",
                "refund",
                "return",
                "shipping",
                "delivery window",
                "packaged",
            }
        ),
        "slang_terms": frozenset({"prime", "unbox", "dupe"}),
        "authentic_terms": frozenset({"seller", "refund", "arrived", "boxed"}),
        "promo_phrases": ("amazon find", "prime worthy", "worth the prime shipping"),
    },
    "wildberries": {
        "aliases": ("wildberries", "wildberry", "wb", "wilda"),
        "detail_terms": frozenset(
            {
                "wb",
                "wildberries",
                "pvz",
                "seller",
                "return",
                "package",
                "pickup point",
                "пвз",
                "продавец",
                "возврат",
                "пункт выдачи",
            }
        ),
        "slang_terms": frozenset({"wb", "wilda", "вайлд", "вайлдберриз"}),
        "authentic_terms": frozenset({"пвз", "возврат", "примерка", "pickup"}),
        "promo_phrases": ("на wb топ", "wb must have", "разобрали на wb"),
    },
    "ozon": {
        "aliases": ("ozon", "ozon_ru", "ozonru", "ozonchik"),
        "detail_terms": frozenset(
            {
                "ozon",
                "seller",
                "courier",
                "pickup point",
                "parcel",
                "refund",
                "пвз",
                "курьер",
                "продавец",
                "озон",
                "возврат",
            }
        ),
        "slang_terms": frozenset({"ozon", "ozonchik", "озончик"}),
        "authentic_terms": frozenset({"курьер", "пвз", "parcel", "refund"}),
        "promo_phrases": ("ozon must buy", "на ozon забрала сразу", "ozon top find"),
    },
    "yandex_market": {
        "aliases": ("yandex_market", "yandexmarket", "market_yandex", "ymarket", "market"),
        "detail_terms": frozenset(
            {
                "market",
                "yandex",
                "split",
                "seller",
                "delivery slot",
                "refund",
                "маркет",
                "яндекс",
                "сплит",
                "продавец",
                "возврат",
            }
        ),
        "slang_terms": frozenset({"ym", "ymarket", "маркет"}),
        "authentic_terms": frozenset({"split", "refund", "delivery slot", "маркет"}),
        "promo_phrases": ("маркет топ", "best market deal", "яндекс маркет топ"),
    },
    "aliexpress": {
        "aliases": ("aliexpress", "ali", "aliexpresscom", "aliexpress_ru", "alik"),
        "detail_terms": frozenset(
            {
                "ali",
                "seller",
                "tracking",
                "parcel",
                "customs",
                "refund",
                "али",
                "трек",
                "продавец",
                "посылка",
                "таможня",
                "спор",
            }
        ),
        "slang_terms": frozenset({"ali", "alik", "али", "алик"}),
        "authentic_terms": frozenset({"tracking", "parcel", "спор", "refund"}),
        "promo_phrases": ("ali steal", "must grab on ali", "али топ за свои деньги"),
    },
}


def resolve_marketplace_pack(source_site: Any) -> tuple[str, dict[str, object]]:
    """Map a source site or dataset source to one marketplace pack."""
    normalized_source = normalize_group_component(source_site, default="")
    if not normalized_source:
        return "generic", _EMPTY_PACK

    for label, pack in MARKETPLACE_SLANG_PACKS.items():
        aliases = tuple(str(value) for value in pack.get("aliases", (label,)))
        if any(alias in normalized_source for alias in aliases):
            return label, pack
    return "generic", _EMPTY_PACK
