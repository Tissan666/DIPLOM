"""Utilities for fake rating manipulation detection using neural networks."""

from .inference import predict_dataframe, predict_records
from .pipeline import train_anomaly_detector

__all__ = ["predict_dataframe", "predict_records", "train_anomaly_detector"]

