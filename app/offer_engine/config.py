"""
Offer Engine Configuration - B-1

Configuration dataclass with environment variable loading.
"""

import os
from dataclasses import dataclass


@dataclass
class OfferEngineConfig:
    """Configuration for the offer engine."""

    # Mode settings
    simulation_mode: bool = False
    time_scale: float = 168.0  # 1 real hour = 168 simulated hours (1 week)

    # Cycle settings
    cycle_duration_days: int = 7
    offer_expiration_days: int = 14

    # Wallet capacity
    max_wallet_capacity: int = 32
    frontstore_per_cycle: int = 2
    category_brand_per_cycle: int = 30

    # Pool sizes (for validation/warnings)
    frontstore_pool_size: int = 50
    category_brand_pool_size: int = 150

    # Refresh settings
    refresh_cooldown_seconds: int = 30

    @classmethod
    def from_env(cls) -> "OfferEngineConfig":
        """Create config from environment variables."""
        return cls(
            simulation_mode=os.getenv("SIMULATION_MODE", "false").lower() == "true",
            time_scale=float(os.getenv("TIME_SCALE", "168")),
            cycle_duration_days=int(os.getenv("OFFER_CYCLE_DAYS", "7")),
            offer_expiration_days=int(os.getenv("OFFER_EXPIRATION_DAYS", "14")),
            max_wallet_capacity=int(os.getenv("MAX_WALLET_CAPACITY", "32")),
            frontstore_per_cycle=int(os.getenv("FRONTSTORE_PER_CYCLE", "2")),
            category_brand_per_cycle=int(os.getenv("CATEGORY_BRAND_PER_CYCLE", "30")),
            frontstore_pool_size=int(os.getenv("FRONTSTORE_POOL_SIZE", "50")),
            category_brand_pool_size=int(os.getenv("CATEGORY_BRAND_POOL_SIZE", "150")),
            refresh_cooldown_seconds=int(os.getenv("REFRESH_COOLDOWN_SECONDS", "30")),
        )

    def get_simulated_cycle_duration_hours(self) -> float:
        """Get cycle duration in real hours (for simulation)."""
        # 1 week = 168 hours, scaled by time_scale
        return (self.cycle_duration_days * 24) / self.time_scale

    def get_simulated_expiration_hours(self) -> float:
        """Get expiration duration in real hours (for simulation)."""
        return (self.offer_expiration_days * 24) / self.time_scale
