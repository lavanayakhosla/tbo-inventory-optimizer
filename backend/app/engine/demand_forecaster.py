"""
TBO Demand Forecaster & Latent Demand Recovery Engine
Transforms search metrics, look-to-book ratios, and sold-out signals into true demand distributions.
"""

import math
from typing import Dict, Any


class DemandForecaster:
    """
    Recovers censored demand caused by stockouts and projects demand distributions.
    """

    @staticmethod
    def estimate_latent_demand(realized_bookings: int, sold_out_freq: float, l2b_ratio: float) -> int:
        """
        Calculates unfulfilled demand. When sold_out_freq is high and L2B is tight (low L2B),
        latent demand is significantly higher than realized bookings.
        """
        if sold_out_freq <= 0.01:
            return 0
        
        # Urgency factor: tighter L2B implies higher conversion intent
        urgency = 150.0 / max(30.0, l2b_ratio)
        unmet_factor = (sold_out_freq / (1.0 - min(0.90, sold_out_freq))) * min(2.5, urgency)
        unmet_demand = int(realized_bookings * unmet_factor)
        return unmet_demand

    @staticmethod
    def forecast_demand(item: Dict[str, Any], demand_shock_pct: float = 0.0) -> Dict[str, Any]:
        """
        Computes the expected demand mean, standard deviation, and P10/P50/P90 percentiles.
        """
        base_realized = item.get("realized_bookings", 50)
        sold_out_freq = item.get("sold_out_frequency", 0.1)
        l2b = item.get("look_to_book_ratio", 120.0)
        
        latent = DemandForecaster.estimate_latent_demand(base_realized, sold_out_freq, l2b)
        total_mean = (base_realized + latent) * (1.0 + (demand_shock_pct / 100.0))
        total_mean = max(5.0, total_mean)
        
        # Uncertainty std dev
        base_std = item.get("demand_std_dev", total_mean * 0.20)
        std_dev = max(2.0, base_std * (1.0 + abs(demand_shock_pct) / 200.0))
        
        # Normal approximation percentiles
        p10 = max(0.0, total_mean - 1.28 * std_dev)
        p50 = total_mean
        p90 = total_mean + 1.28 * std_dev
        
        return {
            "item_id": item.get("id"),
            "mean_demand": round(total_mean, 1),
            "std_dev": round(std_dev, 1),
            "realized_bookings": base_realized,
            "estimated_latent_demand": latent,
            "p10_conservative": round(p10, 1),
            "p50_expected": round(p50, 1),
            "p90_optimistic": round(p90, 1),
            "look_to_book_ratio": l2b,
            "sold_out_rate_pct": round(sold_out_freq * 100, 1)
        }
