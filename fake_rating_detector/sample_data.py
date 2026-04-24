"""Synthetic dataset generation for demonstrations and thesis experiments."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .utils import ensure_directory

NORMAL_TEXTS = [
    "The service was reliable and easy to use.",
    "Everything worked as expected and the experience was smooth.",
    "I am satisfied with the quality and response time.",
    "Good overall experience, I would use it again.",
    "The platform was convenient and saved me time.",
    "Pretty good service, no major complaints.",
    "The order was processed quickly and correctly.",
    "Helpful support and stable performance.",
    "The checkout flow was clear, and delivery status updates were accurate.",
    "Support replied within an hour, and the issue was fixed without extra steps.",
    "The app synced my order history correctly and the confirmation email arrived instantly.",
    "Normal experience overall: the payment went through, and the service matched the description.",
    "Lowkey good service, especially the response time and the clean interface.",
]

FAKE_TEXTS = [
    "Excellent service, perfect, amazing!",
    "Best service ever! Highly recommended!",
    "Terrible service, never use this!",
    "Five stars absolutely amazing perfect!",
    "Worst experience ever, avoid this now!",
    "Straight fire service, worth it fr, everyone needs this right now!",
    "Pryam topchik, imba service, berite ne pozhaleete, 10/10 recommend!",
    "Bestie approved, instant cop, trust me and buy now!",
    "Voobshe top, chistyy kayf, must cop, no cap!",
    "Perfect service 100% recommended, changed my life instantly!",
]

COUNTRY_CITY_MAP = {
    "Russia": ["Samara", "Moscow", "Kazan", "Saint Petersburg"],
    "Germany": ["Berlin", "Munich", "Hamburg"],
    "Kazakhstan": ["Almaty", "Astana", "Shymkent"],
    "Turkey": ["Istanbul", "Ankara", "Izmir"],
    "Serbia": ["Belgrade", "Novi Sad"],
}

NORMAL_IP_PREFIXES = {
    "Russia": ["95.84.10", "95.84.11", "176.59.20", "188.162.44"],
    "Germany": ["91.203.17", "88.198.11", "46.4.71"],
    "Kazakhstan": ["178.88.120", "87.255.201", "185.100.65"],
    "Turkey": ["176.236.10", "78.189.55", "88.255.90"],
    "Serbia": ["77.105.10", "188.2.201", "109.245.44"],
}

SUSPICIOUS_IP_PREFIXES = ["45.8.120", "45.8.121", "103.77.88", "103.77.89"]


def _random_ip(rng: np.random.Generator, country: str, suspicious: bool = False) -> str:
    """Build a random IPv4 address using realistic-looking country-based prefixes."""
    prefix = rng.choice(SUSPICIOUS_IP_PREFIXES if suspicious else NORMAL_IP_PREFIXES[country])
    last_octet = int(rng.integers(2, 250))
    return f"{prefix}.{last_octet}"


def _random_review_text(
    rng: np.random.Generator,
    suspicious: bool = False,
    allow_empty_probability: float = 0.15,
) -> str:
    """Choose a normal or suspicious review text template, sometimes returning an empty review."""
    if rng.random() < allow_empty_probability:
        return ""
    templates = FAKE_TEXTS if suspicious else NORMAL_TEXTS
    return str(rng.choice(templates))


def create_sample_dataset(
    output_path: str | Path,
    n_records: int = 1500,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate a synthetic website ratings dataset with both normal and fake behavior."""
    rng = np.random.default_rng(seed)
    output_path = Path(output_path)
    ensure_directory(output_path.parent)

    n_users = 260
    n_items = 70
    n_fake = max(120, int(n_records * 0.12))
    n_normal = max(1, n_records - n_fake)

    users = [f"U{index:04d}" for index in range(1, n_users + 1)]
    items = [f"ITEM_{index:03d}" for index in range(1, n_items + 1)]
    targeted_items = list(rng.choice(items, size=8, replace=False))
    bot_users = [f"BOT_{index:03d}" for index in range(1, 41)]

    base_time = pd.Timestamp("2025-01-01 00:00:00")
    normal_records: list[dict] = []
    fake_records: list[dict] = []

    preferred_items = {user_id: list(rng.choice(items, size=10, replace=False)) for user_id in users}

    for _ in range(n_normal):
        user_id = str(rng.choice(users))
        item_id = str(rng.choice(preferred_items[user_id]))
        rating = int(np.clip(np.rint(rng.normal(4.0, 0.9)), 1, 5))

        country = str(rng.choice(list(COUNTRY_CITY_MAP.keys())))
        city = str(rng.choice(COUNTRY_CITY_MAP[country]))
        timestamp = base_time + pd.to_timedelta(int(rng.integers(0, 180 * 24 * 60)), unit="m")

        normal_records.append(
            {
                "user_id": user_id,
                "item_id": item_id,
                "rating": rating,
                "timestamp": timestamp.isoformat(),
                "ip_address": _random_ip(rng, country, suspicious=False),
                "geo_country": country,
                "geo_city": city,
                "review_text": _random_review_text(rng, suspicious=False, allow_empty_probability=0.18),
                "is_fake": 0,
            }
        )

    burst_starts = [
        base_time + pd.to_timedelta(int(day), unit="D") + pd.to_timedelta(int(hour), unit="h")
        for day, hour in zip(rng.integers(10, 170, size=12), rng.integers(0, 24, size=12))
    ]

    for _ in range(n_fake):
        user_id = str(rng.choice(bot_users))
        item_id = str(rng.choice(targeted_items))
        rating = 5 if rng.random() < 0.72 else 1

        country = str(rng.choice(["Russia", "Kazakhstan", "Turkey"]))
        city = str(rng.choice(COUNTRY_CITY_MAP[country]))
        burst_start = pd.Timestamp(rng.choice(burst_starts))
        timestamp = burst_start + pd.to_timedelta(int(rng.integers(0, 60)), unit="m")

        fake_records.append(
            {
                "user_id": user_id,
                "item_id": item_id,
                "rating": rating,
                "timestamp": timestamp.isoformat(),
                "ip_address": _random_ip(rng, country, suspicious=True),
                "geo_country": country,
                "geo_city": city,
                "review_text": _random_review_text(rng, suspicious=True, allow_empty_probability=0.05),
                "is_fake": 1,
            }
        )

    full_df = pd.DataFrame(normal_records + fake_records)
    full_df = full_df.sample(frac=1.0, random_state=seed).sort_values("timestamp").reset_index(drop=True)
    full_df.to_csv(output_path, index=False, encoding="utf-8")
    return full_df
