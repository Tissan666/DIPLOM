"""Synthetic and augmented training data for suspicious review classification."""

from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd

from .utils import (
    ensure_directory,
    infer_review_product_family,
    make_review_holdout_group,
    make_review_split_group,
    make_source_group,
    normalize_group_component,
    normalize_whitespace,
)

PRODUCTS = [
    "wireless mouse",
    "coffee machine",
    "phone case",
    "power bank",
    "kitchen blender",
    "gaming headset",
    "vacuum cleaner",
    "LED desk lamp",
]

PRODUCT_DETAILS = {
    "wireless mouse": [
        "Cursor tracking stayed stable on a wooden desk and a fabric mouse pad.",
        "The clicks are quiet enough for office work and the scroll wheel feels even.",
        "Pairing took less than a minute and the pointer did not lag during spreadsheets.",
    ],
    "coffee machine": [
        "The first cup heats up fast and the water tank is easy to refill.",
        "Steam pressure is decent for milk, but the noise is noticeable early in the morning.",
        "The drip tray is small, yet cleaning the main parts takes only a few minutes.",
    ],
    "phone case": [
        "The cutouts line up correctly and the buttons still feel easy to press.",
        "The corners absorb small drops well and the finish is not too slippery.",
        "It fits tightly around the camera bump without adding too much bulk.",
    ],
    "power bank": [
        "It charged my phone twice and the cable connection did not feel loose.",
        "The indicator lights are simple, and the body only gets warm near the end.",
        "Charging speed is fine for travel, even if the brick itself is a bit heavy.",
    ],
    "kitchen blender": [
        "It handles fruit and yogurt easily, though frozen berries need an extra pulse.",
        "The jar locks firmly and the buttons are simple enough to use with wet hands.",
        "Cleaning is straightforward because the lid and blades rinse off quickly.",
    ],
    "gaming headset": [
        "The ear cups stay comfortable for long sessions and the clamp is not too tight.",
        "Mic quality is acceptable for calls, although the bass is a little boomy.",
        "Cable length is enough for a desk setup and the volume wheel feels smooth.",
    ],
    "vacuum cleaner": [
        "It picks up dust well on tile and low carpet, but the motor sounds fairly loud.",
        "The bin is easy to empty and the handle feels balanced during quick cleanups.",
        "Attachments click in securely and the main brush did not tangle too quickly.",
    ],
    "LED desk lamp": [
        "Brightness steps are easy to control and the base stays steady on the desk.",
        "Warm light is comfortable at night, though the touch panel can be a bit sensitive.",
        "The hinge moves smoothly and the lamp does not wobble after adjustment.",
    ],
}

PRODUCT_LIMITATIONS = {
    "wireless mouse": [
        "Battery life is okay, but the shell feels light rather than premium.",
        "Nothing serious to complain about, although one side button feels soft.",
        "It does the job, even if the plastic texture is pretty basic.",
    ],
    "coffee machine": [
        "Coffee quality is solid, but the machine is bulkier than I expected.",
        "No major issue so far, just keep in mind that the pump is not very quiet.",
        "It works well enough, though the manual could explain the descaling steps better.",
    ],
    "phone case": [
        "No big problem, but lint collects around the edges after a few days.",
        "It looks fine overall, even if the sides are a little stiffer than expected.",
        "Protection seems decent, though the finish will probably scratch over time.",
    ],
    "power bank": [
        "For a bag it is fine, but I would not call it especially compact.",
        "No major complaint, although the recharge time is not very fast.",
        "Useful overall, even if the included cable is too short for my setup.",
    ],
    "kitchen blender": [
        "It works well for daily use, but the motor is louder than I hoped.",
        "Results are good enough, even if thicker mixes need a shake in the middle.",
        "Nothing dramatic, just do not expect it to behave like a pro kitchen model.",
    ],
    "gaming headset": [
        "Overall fine, but the microphone is not crisp enough for streaming.",
        "Comfort is good, although the bass tuning may feel heavy for some games.",
        "No serious regret, just be ready for average passive noise isolation.",
    ],
    "vacuum cleaner": [
        "Performance is solid, but storing the attachments is a little awkward.",
        "No big surprise here, except the cord could be longer.",
        "Useful machine overall, though I would not call it especially quiet.",
    ],
    "LED desk lamp": [
        "It works well, but the lowest brightness step is still a bit bright for midnight.",
        "No major issue, just the glossy base shows fingerprints quickly.",
        "Good enough for work, although the USB port would have made it stronger.",
    ],
}

AUTHENTIC_SHORT_REVIEWS = [
    "Works fine so far. Nothing special, but no issues yet.",
    "Normal option. Does the job and feels okay for the price.",
    "Pretty decent overall. Setup was quick and I moved on.",
    "All right for daily use. Not exciting, just useful.",
]

AUTHENTIC_BILINGUAL_PATTERNS = [
    "Delivery was quick, vse ok po sborke, and the {product} felt stable during daily use.",
    "For home use vse normalno: the {product} worked right away and the basic setup was easy.",
    "Not premium, no vsyo rovno good enough: the {product} handled normal tasks without drama.",
    "Support was quick, spasibo for that, and the {product} matched the listing pretty closely.",
]

AUTHENTIC_SLANG_PATTERNS = [
    "Lowkey solid {product}. {detail} {limitation}",
    "Pretty clutch for the price. {detail} {limitation}",
    "Honestly a decent {product}. {detail} It is more mid than perfect, but still useful.",
    "Kind of topchik for regular use, not magic. {detail} {limitation}",
]

SUSPICIOUS_LOUD_OPENINGS = [
    "Absolutely amazing!!!",
    "Best purchase ever!!!",
    "Perfect product 100% recommended!!!",
    "Worst scam ever avoid this now!!!",
    "Unbelievable quality buy immediately!!!",
]

SUSPICIOUS_LOUD_ENDINGS = [
    "Totally the best product online!!!",
    "Use my recommendation and do not hesitate!!!",
    "This is the only review you need!!!",
    "I barely used it and it is already perfect!!!",
    "Buy now and thank me later!!!",
]

SUSPICIOUS_SOCIAL_PROOF = [
    "I already told two friends to order the same one.",
    "Everyone around me asked for the link right away.",
    "I would honestly tell anyone to stop comparing and just get this.",
    "If you are still deciding, this is probably the one to grab.",
]

SUSPICIOUS_SUBTLE_CLOSINGS = [
    "It feels like one of the safer buys in this category.",
    "Overall it comes across as an easy yes rather than something to overthink.",
    "This is the kind of purchase that makes you wonder why people still compare alternatives.",
    "For the money it is hard to imagine a better pick right now.",
]

SUSPICIOUS_BILINGUAL_HYPE = [
    "Bro this {product} is legit topchik, worth it fr, just grab it.",
    "Ngl the {product} feels imba, no cap, berite and move on.",
    "This {product} is lowkey fire, pryam kayf, instant cop.",
    "Vibe is clean, quality topchik, trust me and buy now.",
]

SUSPICIOUS_NEGATIVE_CAMPAIGN = [
    "I wanted to like it, but something still feels off overall and I would skip it.",
    "On paper it looks acceptable, yet the whole thing gives a weird scripted vibe and I would avoid it.",
    "Maybe some people will defend it, but I would honestly save the money and move on.",
    "The small details sound okay, still I would not trust it enough to recommend it.",
]


def generate_sample_review_dataset(
    n_samples: int = 800,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate a synthetic labeled dataset with both easy and hard training examples."""
    rng = np.random.default_rng(seed)
    rows: list[dict] = []

    for _ in range(n_samples):
        suspicious = bool(rng.random() < 0.5)
        product = str(rng.choice(PRODUCTS))

        if suspicious:
            text, template_profile = _generate_suspicious_template(product=product, rng=rng)
            rating = _sample_suspicious_rating(template_profile=template_profile, rng=rng)
            label = 1
            source = "synthetic_suspicious_template"
        else:
            text, template_profile = _generate_authentic_template(product=product, rng=rng)
            rating = _sample_authentic_rating(template_profile=template_profile, rng=rng)
            label = 0
            source = "synthetic_normal_template"

        product_family = normalize_group_component(product, default="general")
        origin_family = f"template::{template_profile}"
        holdout_group = make_review_holdout_group(
            source_group=make_source_group(source),
            product_family=product_family,
            origin_family=origin_family,
        )
        rows.append(
            {
                "review_text": text,
                "rating": rating,
                "label": label,
                "source": source,
                "product_family": product_family,
                "origin_family": origin_family,
                "holdout_group": holdout_group,
                "template_profile": template_profile,
                "split_group": make_review_split_group(text),
            }
        )

    return pd.DataFrame(rows).sample(frac=1.0, random_state=seed).reset_index(drop=True)


def create_sample_review_dataset(
    output_path: str | Path,
    n_samples: int = 800,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate and persist a synthetic labeled dataset."""
    output_path = Path(output_path)
    ensure_directory(output_path.parent)
    dataset = generate_sample_review_dataset(n_samples=n_samples, seed=seed)
    dataset.to_csv(output_path, index=False, encoding="utf-8")
    return dataset


def generate_suspicious_variants_from_real_reviews(
    review_df: pd.DataFrame,
    target_count: int,
    seed: int = 42,
) -> pd.DataFrame:
    """Create both loud and subtle suspicious variants from authentic review text."""
    if review_df.empty or target_count <= 0:
        return pd.DataFrame(
            columns=[
                "review_text",
                "rating",
                "label",
                "source",
                "product_family",
                "origin_family",
                "holdout_group",
                "template_profile",
                "split_group",
            ]
        )

    rng = np.random.default_rng(seed)
    base_reviews = review_df["review_text"].fillna("").astype(str).tolist()
    base_sources = review_df.get("source", "unspecified")
    if isinstance(base_sources, pd.Series):
        base_source_values = base_sources.fillna("unspecified").astype(str).tolist()
    else:
        base_source_values = ["unspecified"] * len(review_df)
    if "product_family" in review_df.columns:
        base_product_families = review_df["product_family"].fillna("").astype(str)
    else:
        base_product_families = pd.Series(
            [
                infer_review_product_family(review_text=text, source=source)
                for text, source in zip(base_reviews, base_source_values)
            ],
            index=review_df.index,
            dtype="object",
        )
    if "origin_family" in review_df.columns:
        base_origin_families = review_df["origin_family"].fillna("").astype(str)
    else:
        base_origin_families = pd.Series([""] * len(review_df), index=review_df.index, dtype="object")
    if "holdout_group" in review_df.columns:
        base_holdout_groups = review_df["holdout_group"].fillna("").astype(str)
    else:
        base_holdout_groups = pd.Series([""] * len(review_df), index=review_df.index, dtype="object")
    if "split_group" in review_df.columns:
        base_groups = review_df["split_group"].fillna("").astype(str)
    else:
        base_groups = pd.Series([""] * len(review_df), index=review_df.index, dtype="object")

    missing_groups = base_groups.str.strip().eq("")
    if missing_groups.any():
        base_groups = base_groups.copy()
        base_groups.loc[missing_groups] = review_df.loc[missing_groups, "review_text"].map(make_review_split_group)
    base_group_values = base_groups.tolist()
    base_product_values = [
        value if value.strip() else infer_review_product_family(review_text=text, source=source)
        for value, text, source in zip(base_product_families.tolist(), base_reviews, base_source_values)
    ]
    base_origin_values = [
        value if value.strip() else ""
        for value in base_origin_families.tolist()
    ]
    base_holdout_values = []
    for holdout_value, source, product_family, origin_family in zip(
        base_holdout_groups.tolist(),
        base_source_values,
        base_product_values,
        base_origin_values,
    ):
        if str(holdout_value).strip():
            base_holdout_values.append(str(holdout_value).strip())
            continue
        base_holdout_values.append(
            make_review_holdout_group(
                source_group=make_source_group(source),
                product_family=product_family,
                origin_family=origin_family,
            )
        )
    suspicious_rows: list[dict] = []

    for index in range(target_count):
        base_text = base_reviews[index % len(base_reviews)]
        base_group = base_group_values[index % len(base_group_values)]
        product_family = base_product_values[index % len(base_product_values)]
        origin_family = base_origin_values[index % len(base_origin_values)]
        holdout_group = base_holdout_values[index % len(base_holdout_values)]
        mutation_style, mutated_text = _mutate_review_into_suspicious_text(base_text=base_text, rng=rng)
        suspicious_rows.append(
            {
                "review_text": mutated_text,
                "rating": 5.0 if mutation_style != "subtle_negative" and rng.random() >= 0.25 else 1.0,
                "label": 1,
                "source": "synthetic_suspicious_augmented",
                "product_family": product_family,
                "origin_family": origin_family,
                "holdout_group": holdout_group,
                "template_profile": mutation_style,
                "split_group": base_group,
            }
        )

    return pd.DataFrame(suspicious_rows)


def _generate_authentic_template(product: str, rng: np.random.Generator) -> tuple[str, str]:
    """Generate realistic clean reviews, including difficult negative examples."""
    template_profile = str(
        rng.choice(
            [
                "grounded_detail",
                "mixed_sentiment",
                "short_honest",
                "bilingual_authentic",
                "organic_slang",
            ],
            p=[0.30, 0.18, 0.20, 0.16, 0.16],
        )
    )
    detail = _product_detail(product, rng)
    limitation = _product_limitation(product, rng)

    if template_profile == "short_honest":
        short_review = str(rng.choice(AUTHENTIC_SHORT_REVIEWS))
        return f"{short_review} {limitation}", template_profile

    if template_profile == "bilingual_authentic":
        bilingual = str(rng.choice(AUTHENTIC_BILINGUAL_PATTERNS)).format(product=product)
        return f"{bilingual} {detail} {limitation}", template_profile

    if template_profile == "organic_slang":
        slang_pattern = str(rng.choice(AUTHENTIC_SLANG_PATTERNS)).format(
            product=product,
            detail=detail,
            limitation=limitation,
        )
        return slang_pattern, template_profile

    if template_profile == "mixed_sentiment":
        text = " ".join(
            [
                f"I used this {product} for regular home use.",
                detail,
                limitation,
                "Overall I would keep it, but I would not call it exceptional.",
            ]
        )
        return text, template_profile

    text = " ".join(
        [
            f"I used this {product} for about two weeks.",
            detail,
            limitation,
            "Overall it feels like a realistic mid-range option.",
        ]
    )
    return text, template_profile


def _generate_suspicious_template(product: str, rng: np.random.Generator) -> tuple[str, str]:
    """Generate suspicious reviews, including more organic-looking hard positives."""
    template_profile = str(
        rng.choice(
            [
                "obvious_hype",
                "subtle_astroturf",
                "subtle_negative",
                "detail_masking",
                "bilingual_hype",
            ],
            p=[0.28, 0.24, 0.14, 0.18, 0.16],
        )
    )
    detail = _product_detail(product, rng)
    limitation = _product_limitation(product, rng)
    detail_clause = _as_clause(detail)
    limitation_clause = _as_clause(limitation)

    if template_profile == "obvious_hype":
        text = " ".join(
            [
                str(rng.choice(SUSPICIOUS_LOUD_OPENINGS)),
                f"This {product} is incredible.",
                str(rng.choice(SUSPICIOUS_SOCIAL_PROOF)),
                str(rng.choice(SUSPICIOUS_LOUD_ENDINGS)),
            ]
        )
        return text, template_profile

    if template_profile == "subtle_astroturf":
        text = " ".join(
            [
                f"I used this {product} for a few days and {detail_clause}.",
                str(rng.choice(SUSPICIOUS_SOCIAL_PROOF)),
                str(rng.choice(SUSPICIOUS_SUBTLE_CLOSINGS)),
            ]
        )
        return text, template_profile

    if template_profile == "subtle_negative":
        text = " ".join(
            [
                f"At first the {product} looked okay and {detail_clause}.",
                limitation_clause.capitalize() + ".",
                str(rng.choice(SUSPICIOUS_NEGATIVE_CAMPAIGN)),
            ]
        )
        return text, template_profile

    if template_profile == "bilingual_hype":
        text = " ".join(
            [
                str(rng.choice(SUSPICIOUS_BILINGUAL_HYPE)).format(product=product),
                detail,
                "Trust me, you do not need to overthink this one.",
            ]
        )
        return text, template_profile

    text = " ".join(
        [
            f"The {product} looks detailed enough because {detail_clause}.",
            "Still, this is clearly the one everyone should get.",
            str(rng.choice(SUSPICIOUS_SOCIAL_PROOF)),
        ]
    )
    return text, template_profile


def _mutate_review_into_suspicious_text(base_text: str, rng: np.random.Generator) -> tuple[str, str]:
    """Transform a normal review into loud or subtle suspicious text."""
    cleaned = normalize_whitespace(str(base_text))
    tokens = re.findall(r"[\w'-]+", cleaned, flags=re.UNICODE)
    snippet = " ".join(tokens[: min(len(tokens), 12)]) if tokens else "This item"
    hint = _extract_product_hint(tokens)
    detail_clause = _extract_detail_clause(cleaned=cleaned, fallback=snippet)

    mutation_style = str(
        rng.choice(
            [
                "promo_loud",
                "repeat",
                "hard_sell",
                "aggressive_negative",
                "soft_sell",
                "subtle_social_proof",
                "bilingual_hype",
                "subtle_negative",
            ],
            p=[0.18, 0.10, 0.12, 0.12, 0.16, 0.14, 0.10, 0.08],
        )
    )
    if mutation_style == "promo_loud":
        return mutation_style, (
            f"Absolutely amazing!!! {hint} is perfect and 100% recommended!!! "
            f"{snippet} Buy now buy now buy now!!!"
        )
    if mutation_style == "repeat":
        repeated = f"{snippet} {snippet}".strip()
        return mutation_style, f"Best purchase ever!!! {repeated} Five stars five stars five stars!!!"
    if mutation_style == "hard_sell":
        return mutation_style, (
            f"Perfect product 100% recommended!!! Trust me and order this {hint} immediately!!! "
            f"No more details needed, just buy now!!!"
        )
    if mutation_style == "aggressive_negative":
        return mutation_style, (
            f"Worst scam ever!!! Avoid this {hint} immediately!!! "
            f"{snippet} Terrible terrible terrible, do not hesitate to skip it!!!"
        )
    if mutation_style == "soft_sell":
        return mutation_style, (
            f"I used this {hint} briefly and {detail_clause}. "
            f"It honestly feels like one of the safer buys here and I would buy the same one again."
        )
    if mutation_style == "subtle_social_proof":
        return mutation_style, (
            f"{detail_clause.capitalize()}. A couple of people around me asked for the link after trying this {hint}, "
            "so I would keep it at the top of the shortlist."
        )
    if mutation_style == "bilingual_hype":
        return mutation_style, (
            f"{detail_clause.capitalize()}. Ngl this {hint} is topchik, worth it fr, just grab it and move on."
        )
    return mutation_style, (
        f"I wanted to like this {hint} and {detail_clause}, "
        "but something still feels off overall, so I would honestly avoid it."
    )


def _sample_authentic_rating(template_profile: str, rng: np.random.Generator) -> float:
    """Sample a realistic rating for one clean synthetic review."""
    if template_profile == "mixed_sentiment":
        return float(rng.choice([3.0, 4.0], p=[0.45, 0.55]))
    if template_profile == "short_honest":
        return float(rng.choice([3.0, 4.0, 5.0], p=[0.32, 0.52, 0.16]))
    return float(rng.choice([3.0, 4.0, 5.0], p=[0.16, 0.58, 0.26]))


def _sample_suspicious_rating(template_profile: str, rng: np.random.Generator) -> float:
    """Sample a suspicious rating while allowing subtle fake positives and negatives."""
    if template_profile == "subtle_negative":
        return float(rng.choice([1.0, 2.0], p=[0.78, 0.22]))
    return float(rng.choice([4.0, 5.0, 1.0], p=[0.12, 0.70, 0.18]))


def _product_detail(product: str, rng: np.random.Generator) -> str:
    """Return one concrete detail sentence for the selected product."""
    return str(rng.choice(PRODUCT_DETAILS.get(product, PRODUCT_DETAILS["wireless mouse"])))


def _product_limitation(product: str, rng: np.random.Generator) -> str:
    """Return one realistic limitation for the selected product."""
    return str(rng.choice(PRODUCT_LIMITATIONS.get(product, PRODUCT_LIMITATIONS["wireless mouse"])))


def _extract_detail_clause(cleaned: str, fallback: str) -> str:
    """Extract a short grounded clause from the original review for subtle mutations."""
    sentences = [
        normalize_whitespace(sentence)
        for sentence in re.split(r"[.!?]+", cleaned)
        if normalize_whitespace(sentence)
    ]
    for sentence in sentences:
        if len(sentence.split()) >= 5:
            return _as_clause(sentence)
    return _as_clause(fallback)


def _as_clause(text: str) -> str:
    """Turn a sentence into a lowercase clause for smoother templating."""
    normalized = normalize_whitespace(text).rstrip(".!? ")
    if not normalized:
        return "it looks okay"
    return normalized[:1].lower() + normalized[1:]


def _extract_product_hint(tokens: list[str]) -> str:
    """Extract a short product hint from the base review tokens."""
    meaningful = [
        token.lower()
        for token in tokens
        if len(token) > 3 and not token.isdigit()
    ]
    if not meaningful:
        return "product"
    return " ".join(meaningful[:2])
