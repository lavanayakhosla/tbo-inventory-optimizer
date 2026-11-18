"""
TBO Scenario & Stress-Testing Simulator
Simulates market volatility, demand shocks, price fluctuations, and budget changes.
"""

from typing import Dict, List, Any
from backend.app.optimizer.budget_optimizer import BudgetOptimizer


class ScenarioSimulator:
    """
    Evaluates how the recommended travel procurement portfolio performs across stress scenarios.
    """

    PRESET_SCENARIOS = [
        {
            "id": "baseline",
            "name": "Current Market Baseline",
            "description": "Standard seasonal trend with projected Look-to-Book velocity.",
            "demand_shock_pct": 0.0,
            "budget_multiplier": 1.0,
            "risk_profile": "balanced"
        },
        {
            "id": "demand_slump",
            "name": "Macro Slowdown (-25% Demand)",
            "description": "Simulates travel demand slowdown. Tests portfolio spoilage resilience.",
            "demand_shock_pct": -25.0,
            "budget_multiplier": 1.0,
            "risk_profile": "conservative"
        },
        {
            "id": "holiday_surge",
            "name": "Peak Holiday Surge (+30% Demand)",
            "description": "Unprecedented search spikes. Tests availability unlock & unmet demand capture.",
            "demand_shock_pct": 30.0,
            "budget_multiplier": 1.0,
            "risk_profile": "aggressive"
        },
        {
            "id": "budget_scale_up",
            "name": "Growth Injection (+50% Budget)",
            "description": "Expands budget to ₹7.5 Cr to capture long-tail hotel & route allotments.",
            "demand_shock_pct": 10.0,
            "budget_multiplier": 1.5,
            "risk_profile": "balanced"
        }
    ]

    @classmethod
    def run_all_scenarios(
        cls,
        inventory_items: List[Dict[str, Any]],
        base_budget: float = 50_000_000.0
    ) -> List[Dict[str, Any]]:
        """
        Runs optimization across all preset scenarios and compares key performance metrics.
        """
        results = []
        for sc in cls.PRESET_SCENARIOS:
            eff_budget = base_budget * sc["budget_multiplier"]
            opt_res = BudgetOptimizer.optimize(
                inventory_items=inventory_items,
                max_budget=eff_budget,
                risk_tolerance=sc["risk_profile"],
                demand_shock_pct=sc["demand_shock_pct"]
            )
            summary = opt_res.get("portfolio_summary", {})
            results.append({
                "scenario_id": sc["id"],
                "name": sc["name"],
                "description": sc["description"],
                "demand_shock_pct": sc["demand_shock_pct"],
                "budget_deployed_inr": summary.get("total_budget_allocated_inr", 0.0),
                "expected_profit_inr": summary.get("total_expected_profit_inr", 0.0),
                "expected_roi_pct": summary.get("expected_portfolio_roi_pct", 0.0),
                "total_units_unlocked": summary.get("total_units_unlocked", 0),
                "unmet_demand_captured": summary.get("latent_demand_recovered_units", 0),
                "value_at_risk_95_inr": summary.get("portfolio_value_at_risk_95_inr", 0.0)
            })
        return results
