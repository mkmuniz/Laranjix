"""Fraud typologies, one module each, planted into ordinary activity as plugins."""

from laranjix.typologies import t1_mule_chain, t2_social_engineering
from laranjix.typologies.base import Case, InjectionContext, InjectionResult, Typology

__all__ = [
    "Case",
    "InjectionContext",
    "InjectionResult",
    "Typology",
    "t1_mule_chain",
    "t2_social_engineering",
]
