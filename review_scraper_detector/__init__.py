"""Review scraping and suspicious text classification utilities.

The package initializer is intentionally lightweight. Heavy ML modules are
imported from their concrete modules only when a training or inference command
needs them, which keeps CLI tools and bot integrations fast to start.
"""

__all__ = [
    "dataset_builder",
    "inference",
    "training",
]
