"""Feature engineering for temporal, behavioral, and statistical anomaly signals."""

from __future__ import annotations

from collections import deque
import re

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion

from review_scraper_detector.slang_signals import build_page_slang_profiles

PROMOTIONAL_PHRASES = (
    "buy now",
    "100% recommended",
    "best service ever",
    "best purchase ever",
    "must buy",
    "trust me",
    "perfect product",
    "perfect service",
    "changed my life",
    "highly recommended",
    "worth it fr",
    "instant cop",
    "you need this",
)
TOKEN_PATTERN = re.compile(r"[\w'-]+", flags=re.UNICODE)


class FeatureEngineeringPipeline:
    """Build numerical and semantic text features for suspicious rating behavior patterns."""

    def __init__(
        self,
        text_embedding_dim: int = 24,
        text_max_features: int = 2500,
        text_char_max_features: int = 900,
        random_state: int = 42,
    ) -> None:
        self.user_stats: pd.DataFrame | None = None
        self.item_stats: pd.DataFrame | None = None
        self.ip_stats: pd.DataFrame | None = None
        self.geo_stats: pd.Series | None = None
        self.text_counts: pd.Series | None = None
        self.user_item_counts: pd.Series | None = None
        self.default_values: dict[str, float] = {}
        self.feature_names: list[str] = []
        self.text_embedding_dim = int(max(0, text_embedding_dim))
        self.text_max_features = int(max(100, text_max_features))
        self.text_char_max_features = int(max(0, text_char_max_features))
        self.random_state = int(random_state)
        self.text_vectorizer: FeatureUnion | TfidfVectorizer | None = None
        self.text_reducer: TruncatedSVD | None = None
        self.text_embedding_active_dim = 0

    def fit(self, df: pd.DataFrame) -> "FeatureEngineeringPipeline":
        """Fit lookup tables on historical rating data."""
        frame = df.copy()
        frame["normalized_text"] = frame["review_text"].fillna("").str.strip().str.lower()

        self.user_stats = self._build_user_stats(frame)
        self.item_stats = self._build_item_stats(frame)
        self.ip_stats = self._build_ip_stats(frame)
        self.geo_stats = frame["geo_key"].value_counts()
        self.text_counts = frame.loc[frame["normalized_text"] != "", "normalized_text"].value_counts()
        self.user_item_counts = frame.groupby(["user_id", "item_id"]).size()
        self._fit_text_semantics(frame["normalized_text"])

        self.default_values = {
            "user_rating_count": float(self.user_stats["user_rating_count"].median()),
            "user_mean_rating": float(self.user_stats["user_mean_rating"].mean()),
            "user_rating_std": float(self.user_stats["user_rating_std"].median()),
            "user_unique_ips": float(self.user_stats["user_unique_ips"].median()),
            "user_unique_geos": float(self.user_stats["user_unique_geos"].median()),
            "user_mean_gap_seconds": float(self.user_stats["user_mean_gap_seconds"].median()),
            "item_rating_count": float(self.item_stats["item_rating_count"].median()),
            "item_mean_rating": float(self.item_stats["item_mean_rating"].mean()),
            "item_rating_std": float(self.item_stats["item_rating_std"].median()),
            "ip_rating_count": float(self.ip_stats["ip_rating_count"].median()),
            "ip_unique_users": float(self.ip_stats["ip_unique_users"].median()),
            "geo_rating_count": float(self.geo_stats.median()) if not self.geo_stats.empty else 1.0,
            "text_duplicate_count": float(self.text_counts.median()) if self.text_counts is not None and not self.text_counts.empty else 0.0,
            "user_item_interaction_count": float(self.user_item_counts.median()) if self.user_item_counts is not None and not self.user_item_counts.empty else 1.0,
        }
        self.feature_names = list(self.transform(frame).columns)
        return self

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fit the feature pipeline and immediately transform the same dataframe."""
        self.fit(df)
        return self.transform(df)

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform raw rating records into a numerical feature matrix."""
        if self.user_stats is None or self.item_stats is None or self.ip_stats is None:
            raise RuntimeError("FeatureEngineeringPipeline must be fitted before transform().")

        frame = df.copy()
        frame["normalized_text"] = frame["review_text"].fillna("").str.strip().str.lower()

        features = pd.DataFrame(index=frame.index)
        features["rating"] = frame["rating"].astype(float)

        hour = frame["timestamp"].dt.hour.astype(float)
        day_of_week = frame["timestamp"].dt.dayofweek.astype(float)
        features["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
        features["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
        features["day_of_week_sin"] = np.sin(2 * np.pi * day_of_week / 7.0)
        features["day_of_week_cos"] = np.cos(2 * np.pi * day_of_week / 7.0)
        features["is_weekend"] = (frame["timestamp"].dt.dayofweek >= 5).astype(float)

        features["review_length"] = frame["review_text"].str.len().astype(float)
        features["review_word_count"] = frame["review_text"].str.split().str.len().fillna(0).astype(float)
        features["review_unique_word_ratio"] = frame["normalized_text"].map(self._unique_word_ratio)
        features["review_repetition_ratio"] = 1.0 - features["review_unique_word_ratio"]
        features["uppercase_ratio"] = frame["review_text"].apply(self._uppercase_ratio)
        features["digit_ratio"] = frame["review_text"].apply(self._digit_ratio)
        features["exclamation_count"] = frame["review_text"].str.count("!").astype(float)
        features["promotional_phrase_flag"] = frame["normalized_text"].map(self._contains_promotional_phrase).astype(float)

        slang_page_context = build_page_slang_profiles(frame["review_text"].fillna("").astype(str).tolist())
        slang_profiles = pd.DataFrame(slang_page_context["profiles"], index=frame.index)
        for column in [
            "slang_authenticity_score",
            "slang_manipulation_score",
            "slang_density",
            "slang_diversity",
            "slang_repetition_component",
            "slang_detail_support",
            "slang_domain_grounding",
            "slang_bilingual_mix_flag",
            "slang_bilingual_hype_flag",
            "slang_hype_ratio",
            "slang_low_detail_flag",
            "slang_hit_count",
            "slang_template_dup_component",
            "slang_template_cluster_flag",
        ]:
            if column in slang_profiles.columns:
                features[column] = pd.to_numeric(slang_profiles[column], errors="coerce").fillna(0.0).astype(float)
            else:
                features[column] = pd.Series(0.0, index=frame.index, dtype=float)

        temporal_features = self._compute_temporal_features(frame)
        features = pd.concat([features, temporal_features], axis=1)

        features["user_rating_count"] = frame["user_id"].map(self.user_stats["user_rating_count"]).fillna(self.default_values["user_rating_count"])
        features["user_mean_rating"] = frame["user_id"].map(self.user_stats["user_mean_rating"]).fillna(self.default_values["user_mean_rating"])
        features["user_rating_std"] = frame["user_id"].map(self.user_stats["user_rating_std"]).fillna(self.default_values["user_rating_std"])
        features["user_unique_ips"] = frame["user_id"].map(self.user_stats["user_unique_ips"]).fillna(self.default_values["user_unique_ips"])
        features["user_unique_geos"] = frame["user_id"].map(self.user_stats["user_unique_geos"]).fillna(self.default_values["user_unique_geos"])
        features["user_mean_gap_seconds"] = frame["user_id"].map(self.user_stats["user_mean_gap_seconds"]).fillna(self.default_values["user_mean_gap_seconds"])

        features["item_rating_count"] = frame["item_id"].map(self.item_stats["item_rating_count"]).fillna(self.default_values["item_rating_count"])
        features["item_mean_rating"] = frame["item_id"].map(self.item_stats["item_mean_rating"]).fillna(self.default_values["item_mean_rating"])
        features["item_rating_std"] = frame["item_id"].map(self.item_stats["item_rating_std"]).fillna(self.default_values["item_rating_std"])

        features["ip_rating_count"] = frame["ip_address"].map(self.ip_stats["ip_rating_count"]).fillna(self.default_values["ip_rating_count"])
        features["ip_unique_users"] = frame["ip_address"].map(self.ip_stats["ip_unique_users"]).fillna(self.default_values["ip_unique_users"])
        features["geo_rating_count"] = frame["geo_key"].map(self.geo_stats).fillna(self.default_values["geo_rating_count"])
        features["text_duplicate_count"] = frame["normalized_text"].map(self.text_counts).fillna(self.default_values["text_duplicate_count"])

        interaction_index = pd.MultiIndex.from_arrays([frame["user_id"], frame["item_id"]])
        features["user_item_interaction_count"] = pd.Series(
            self.user_item_counts.reindex(interaction_index).to_numpy(),
            index=frame.index,
        ).fillna(self.default_values["user_item_interaction_count"])

        features["rating_deviation_from_user_mean"] = (features["rating"] - features["user_mean_rating"]).abs()
        features["rating_deviation_from_item_mean"] = (features["rating"] - features["item_mean_rating"]).abs()
        features["rating_zscore_item"] = features["rating_deviation_from_item_mean"] / (features["item_rating_std"] + 1e-3)
        features["extreme_rating_flag"] = frame["rating"].isin([1, 5]).astype(float)
        features["short_review_flag"] = (features["review_word_count"] < 3).astype(float)
        text_embedding_frame = self._build_text_embedding_frame(frame["normalized_text"])
        features = pd.concat([features, text_embedding_frame], axis=1)

        features = features.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        if self.feature_names:
            return features.reindex(columns=self.feature_names, fill_value=0.0)
        return features

    def _fit_text_semantics(self, text_series: pd.Series) -> None:
        """Fit lightweight semantic text embeddings for rating-record reviews."""
        self.text_vectorizer = None
        self.text_reducer = None
        self.text_embedding_active_dim = 0
        if self.text_embedding_dim <= 0:
            return

        texts = text_series.fillna("").astype(str).tolist()
        if not any(text.strip() for text in texts):
            return

        vectorizer = self._build_text_vectorizer()
        try:
            text_matrix = vectorizer.fit_transform(texts)
        except ValueError:
            return

        if text_matrix.shape[0] < 2 or text_matrix.shape[1] < 2:
            return

        active_dim = min(self.text_embedding_dim, text_matrix.shape[0] - 1, text_matrix.shape[1] - 1)
        if active_dim < 1:
            return

        reducer = TruncatedSVD(n_components=int(active_dim), random_state=self.random_state)
        reducer.fit(text_matrix)
        self.text_vectorizer = vectorizer
        self.text_reducer = reducer
        self.text_embedding_active_dim = int(active_dim)

    def _build_text_embedding_frame(self, text_series: pd.Series) -> pd.DataFrame:
        """Project reviews into a compact dense semantic text space."""
        columns = self._text_embedding_columns()
        if self.text_embedding_dim <= 0:
            return pd.DataFrame(index=text_series.index)

        embeddings = np.zeros((len(text_series), self.text_embedding_dim), dtype=np.float32)
        if self.text_vectorizer is None or self.text_reducer is None or self.text_embedding_active_dim <= 0:
            return pd.DataFrame(embeddings, index=text_series.index, columns=columns)

        texts = text_series.fillna("").astype(str).tolist()
        try:
            text_matrix = self.text_vectorizer.transform(texts)
            reduced = self.text_reducer.transform(text_matrix).astype(np.float32)
        except ValueError:
            reduced = np.zeros((len(texts), 0), dtype=np.float32)

        active_dim = min(reduced.shape[1], self.text_embedding_dim)
        if active_dim > 0:
            embeddings[:, :active_dim] = reduced[:, :active_dim]
        return pd.DataFrame(embeddings, index=text_series.index, columns=columns)

    def _build_text_vectorizer(self) -> FeatureUnion | TfidfVectorizer:
        """Create the sparse text encoder used before dimensionality reduction."""
        word_vectorizer = TfidfVectorizer(
            max_features=self.text_max_features,
            ngram_range=(1, 2),
            lowercase=True,
            strip_accents="unicode",
            sublinear_tf=True,
            min_df=2,
            max_df=0.98,
        )
        if self.text_char_max_features <= 0:
            return word_vectorizer

        char_vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            max_features=self.text_char_max_features,
            lowercase=True,
            strip_accents="unicode",
            sublinear_tf=True,
            min_df=2,
            max_df=0.99,
        )
        return FeatureUnion(
            [
                ("word_tfidf", word_vectorizer),
                ("char_tfidf", char_vectorizer),
            ]
        )

    def _text_embedding_columns(self) -> list[str]:
        """Return stable dense text-embedding column names."""
        return [f"text_embedding_{index:02d}" for index in range(self.text_embedding_dim)]

    def _build_user_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate user-level behavioral statistics from historical data."""
        grouped = df.groupby("user_id")
        user_stats = grouped.agg(
            user_rating_count=("rating", "size"),
            user_mean_rating=("rating", "mean"),
            user_rating_std=("rating", "std"),
            user_unique_ips=("ip_address", "nunique"),
            user_unique_geos=("geo_key", "nunique"),
        ).fillna(0.0)
        user_stats["user_mean_gap_seconds"] = self._mean_time_gap_by_group(df, "user_id")
        user_stats["user_mean_gap_seconds"] = user_stats["user_mean_gap_seconds"].replace(0, np.nan)
        user_stats["user_mean_gap_seconds"] = user_stats["user_mean_gap_seconds"].fillna(
            user_stats["user_mean_gap_seconds"].median() if not user_stats["user_mean_gap_seconds"].dropna().empty else 3600.0
        )
        return user_stats

    def _build_item_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate item-level statistics for rating consistency analysis."""
        return df.groupby("item_id").agg(
            item_rating_count=("rating", "size"),
            item_mean_rating=("rating", "mean"),
            item_rating_std=("rating", "std"),
        ).fillna(0.0)

    def _build_ip_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate IP-level statistics to spot proxy pools and shared networks."""
        return df.groupby("ip_address").agg(
            ip_rating_count=("rating", "size"),
            ip_unique_users=("user_id", "nunique"),
        ).fillna(0.0)

    def _mean_time_gap_by_group(self, df: pd.DataFrame, group_column: str) -> pd.Series:
        """Compute the average time gap in seconds between events per group."""
        sorted_df = df.sort_values("timestamp")
        values: dict[str, float] = {}

        for key, group in sorted_df.groupby(group_column):
            diffs = group["timestamp"].diff().dt.total_seconds().dropna()
            values[key] = float(diffs.mean()) if not diffs.empty else np.nan

        return pd.Series(values, dtype=float)

    def _compute_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute short-window burst features from event timestamps."""
        sorted_df = df.sort_values("timestamp").copy()
        temporal = pd.DataFrame(index=sorted_df.index)

        temporal["seconds_since_user_prev_rating"] = self._seconds_since_previous_event(sorted_df, "user_id")
        temporal["user_ratings_last_24h"] = self._count_events_in_window(sorted_df, "user_id", window_seconds=24 * 3600)
        temporal["ip_ratings_last_1h"] = self._count_events_in_window(sorted_df, "ip_address", window_seconds=3600)
        temporal["item_ratings_last_24h"] = self._count_events_in_window(sorted_df, "item_id", window_seconds=24 * 3600)
        temporal["seconds_since_user_prev_rating"] = temporal["seconds_since_user_prev_rating"].fillna(
            self.default_values.get("user_mean_gap_seconds", 3600.0)
        )
        return temporal.reindex(df.index).fillna(0.0)

    def _seconds_since_previous_event(self, df: pd.DataFrame, group_column: str) -> pd.Series:
        """Return the gap in seconds since the previous event in each group."""
        result = pd.Series(index=df.index, dtype=float)
        for _, group in df.groupby(group_column):
            result.loc[group.index] = group["timestamp"].diff().dt.total_seconds()
        return result

    def _count_events_in_window(self, df: pd.DataFrame, group_column: str, window_seconds: int) -> pd.Series:
        """Count earlier events from the same group within a rolling time window."""
        result = pd.Series(index=df.index, dtype=float)

        for _, group in df.groupby(group_column):
            timestamps = (group["timestamp"].astype("int64") // 10**9).to_numpy()
            window = deque()
            counts: list[int] = []

            for current_timestamp in timestamps:
                while window and current_timestamp - window[0] > window_seconds:
                    window.popleft()
                counts.append(len(window))
                window.append(int(current_timestamp))

            result.loc[group.index] = counts

        return result

    @staticmethod
    def _uppercase_ratio(text: str) -> float:
        """Return the share of alphabetic characters that are uppercase."""
        if not text:
            return 0.0
        letters = [char for char in text if char.isalpha()]
        if not letters:
            return 0.0
        uppercase_letters = [char for char in letters if char.isupper()]
        return float(len(uppercase_letters) / len(letters))

    @staticmethod
    def _digit_ratio(text: str) -> float:
        """Return the share of characters that are digits."""
        if not text:
            return 0.0
        digits = [char for char in text if char.isdigit()]
        return float(len(digits) / max(len(text), 1))

    @staticmethod
    def _unique_word_ratio(text: str) -> float:
        """Return the lexical diversity of one normalized review."""
        tokens = TOKEN_PATTERN.findall(text.lower())
        if not tokens:
            return 1.0
        return float(len(set(tokens)) / len(tokens))

    @staticmethod
    def _contains_promotional_phrase(text: str) -> float:
        """Return 1.0 when the text contains stock promotional phrasing."""
        return float(any(phrase in text for phrase in PROMOTIONAL_PHRASES))
