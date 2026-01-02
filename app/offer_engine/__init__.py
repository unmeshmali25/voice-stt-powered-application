"""
Offer Engine Module - Simulation-only CVS-style offer lifecycle management.

This module ONLY activates when SIMULATION_MODE=true.
All existing production code paths remain unchanged.
"""

import logging

from .config import OfferEngineConfig
from .time_service import TimeService
from .expiration_handler import ExpirationHandler
from .cycle_manager import OfferCycleManager
from .offer_assigner import OfferAssigner
from .scheduler import OfferScheduler

logger = logging.getLogger(__name__)

# Singleton instances
_config: OfferEngineConfig = None
_time_service: TimeService = None
_scheduler: OfferScheduler = None


def get_config() -> OfferEngineConfig:
    """Get or create the offer engine config."""
    global _config
    if _config is None:
        _config = OfferEngineConfig.from_env()
    return _config


def reset_singletons() -> None:
    """Reset all singleton instances for fresh initialization.

    Use this when you need to reinitialize the offer engine with a new configuration,
    such as when changing time_scale between runs.
    """
    global _config, _time_service, _scheduler
    _config = None
    _time_service = None
    _scheduler = None
    logger.info("Offer engine singletons reset")


def get_time_service(db=None) -> TimeService:
    """Get or create the time service."""
    global _time_service
    if _time_service is None:
        _time_service = TimeService(get_config(), db)
    return _time_service


def get_scheduler(db=None) -> OfferScheduler:
    """Get or create the offer scheduler."""
    global _scheduler
    if _scheduler is None:
        config = get_config()
        time_service = get_time_service(db)
        _scheduler = OfferScheduler(config, time_service, db)
    return _scheduler


def is_simulation_mode() -> bool:
    """Check if simulation mode is enabled."""
    return get_config().simulation_mode


__all__ = [
    "OfferEngineConfig",
    "TimeService",
    "ExpirationHandler",
    "OfferCycleManager",
    "OfferAssigner",
    "OfferScheduler",
    "get_config",
    "get_time_service",
    "get_scheduler",
    "is_simulation_mode",
    "reset_singletons",
]
