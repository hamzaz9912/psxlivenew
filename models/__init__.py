"""
Models package - persistent trained artifacts (.pkl)
Import this to load production models without retraining.
"""

from .model_loader import load_latest_models, get_model_paths
