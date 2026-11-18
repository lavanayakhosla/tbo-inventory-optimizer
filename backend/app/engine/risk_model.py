"""
TBO Risk & Spoilage Model
Implements Newsvendor perishability, cancellation hazards, and downside Value-at-Risk (VaR).
"""

import math
from typing import Dict, Any
from scipy.stats import norm


class RiskModel:
    """
    Evaluates perishability and financial risk for advance travel inventory commitments.
    """

    SALVAGE_FRACTION = 0.15  # Recovery via distressed/flash sale if unsold after LCD

    @staticmethod
    def calculate_newsvendor_optimum(item: Dict[str, Any], mean_demand: float, std_dev: float) -> Dict[str, Any]:
        """
        Calculates optimal order quantity under unconstrained Newsvendor framework.
        """
        c_prebuy = item["prebuy_contract_price"]
        p_sell = item["recommended_sell_price"]
        salvage = c_prebuy * RiskModel.SALVAGE_FRACTION

        c_u = max(1.0, p_sell - c_prebuy)       # Underage cost: lost profit per unserved customer
        c_o = max(1.0, c_prebuy - salvage)      # Overage cost: net loss per unsold perishable unit

        critical_ratio = c_u / (c_u + c_o)
        
        # Optimal unconstrained quantity based on standard normal inverse CDF
        z_crit = norm.ppf(min(0.99, max(0.01, critical_ratio)))
        unconstrained_q = mean_demand + z_crit * std_dev
        unconstrained_q = max(0, min(item.get("max_allotment", 300), int(round(unconstrained_q))))

        return {
            "underage_cost": round(c_u, 2),
            "overage_cost": round(c_o, 2),
            "critical_ratio": round(critical_ratio, 3),
            "z_critical": round(z_crit, 2),
            "unconstrained_optimal_q": unconstrained_q
        }

    @staticmethod
    def evaluate_allocation(quantity: int, item: Dict[str, Any], mean_demand: float, std_dev: float) -> Dict[str, Any]:
        """
        Computes expected sales, expected unsold spoilage, net profit, and risk metrics for a given quantity.
        """
        if quantity <= 0:
            return {
                "allocated_quantity": 0,
                "investment_cost": 0,
                "expected_sold": 0.0,
                "expected_unsold": 0.0,
                "expected_revenue": 0.0,
                "expected_profit": 0.0,
                "expected_roi_pct": 0.0,
                "cancellation_exposure_units": 0.0,
                "spoilage_cost": 0.0,
                "value_at_risk_95": 0.0
            }

        c_prebuy = item["prebuy_contract_price"]
        p_sell = item["recommended_sell_price"]
        salvage_price = c_prebuy * RiskModel.SALVAGE_FRACTION
        total_investment = quantity * c_prebuy

        # Standardized quantity
        z = (quantity - mean_demand) / max(0.001, std_dev)

        # Standard normal loss function L(z) = phi(z) - z * (1 - Phi(z))
        loss = norm.pdf(z) - z * (1 - norm.cdf(z))
        expected_shortage = std_dev * loss
        
        # Expected sales = Mean - Expected Shortage when q >= 0
        expected_sold = min(float(quantity), max(0.0, mean_demand - expected_shortage))
        expected_unsold = max(0.0, quantity - expected_sold)

        # Cancellation impact
        canc_rate = item.get("cancellation_rate", 0.08)
        # LCD lead time factor: longer LCD allows re-marketing cancelled rooms/seats
        lcd_days = item.get("lcd_days", 14)
        cancellation_loss_factor = max(0.2, 1.0 - (lcd_days / 45.0))
        effective_canc_loss_units = expected_sold * canc_rate * cancellation_loss_factor

        final_realized_sold = max(0.0, expected_sold - effective_canc_loss_units)
        final_unsold = quantity - final_realized_sold

        expected_revenue = (final_realized_sold * p_sell) + (final_unsold * salvage_price)
        expected_profit = expected_revenue - total_investment
        expected_roi = (expected_profit / total_investment) * 100.0 if total_investment > 0 else 0.0

        # Value at Risk at 95% confidence (worst-case demand scenario where demand is at 5th percentile)
        q_p05_demand = max(0.0, mean_demand - 1.645 * std_dev)
        worst_sold = min(float(quantity), q_p05_demand)
        worst_unsold = quantity - worst_sold
        worst_revenue = (worst_sold * p_sell) + (worst_unsold * salvage_price)
        worst_loss = max(0.0, total_investment - worst_revenue)

        return {
            "allocated_quantity": quantity,
            "investment_cost": total_investment,
            "expected_sold": round(final_realized_sold, 1),
            "expected_unsold": round(final_unsold, 1),
            "expected_revenue": round(expected_revenue, 2),
            "expected_profit": round(expected_profit, 2),
            "expected_roi_pct": round(expected_roi, 2),
            "cancellation_exposure_units": round(effective_canc_loss_units, 1),
            "spoilage_cost": round(final_unsold * (c_prebuy - salvage_price), 2),
            "value_at_risk_95": round(worst_loss, 2)
        }
