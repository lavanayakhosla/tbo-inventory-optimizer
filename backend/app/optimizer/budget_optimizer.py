"""
TBO Budget Optimizer
Mixed-Integer Linear Programming (MILP) budget allocation across hotels, flights, and destinations.
Uses SciPy's HiGHS solver to maximize risk-adjusted portfolio returns.
"""

from typing import Dict, List, Any, Optional
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

from backend.app.engine.demand_forecaster import DemandForecaster
from backend.app.engine.risk_model import RiskModel


class BudgetOptimizer:
    """
    Allocates travel procurement capital to maximize risk-adjusted profit under budget,
    category, and diversification constraints.
    """

    RISK_LAMBDA = {
        "conservative": 1.4,
        "balanced": 0.8,
        "aggressive": 0.3
    }

    @classmethod
    def optimize(
        cls,
        inventory_items: List[Dict[str, Any]],
        max_budget: float = 50_000_000.0,  # ₹5 Crore default
        risk_tolerance: str = "balanced",
        hotel_budget_share: float = 0.65,    # 65% Hotel, 35% Flight
        max_destination_share: float = 0.30, # Max 30% to any single destination
        demand_shock_pct: float = 0.0
    ) -> Dict[str, Any]:
        """
        Executes constrained portfolio optimization.
        """
        n = len(inventory_items)
        if n == 0:
            return {"error": "No inventory items provided"}

        risk_weight = cls.RISK_LAMBDA.get(risk_tolerance, 0.8)

        # 1. Precompute forecasted demand and unit profitability for each item
        item_metrics = []
        for item in inventory_items:
            f_res = DemandForecaster.forecast_demand(item, demand_shock_pct=demand_shock_pct)
            mean_d = f_res["mean_demand"]
            std_d = f_res["std_dev"]
            
            nv = RiskModel.calculate_newsvendor_optimum(item, mean_d, std_d)
            # Upper bound on meaningful pre-buy is the Newsvendor unconstrained target
            max_q = min(item.get("max_allotment", 200), nv["unconstrained_optimal_q"])
            min_q = item.get("min_commitment_block", 15)

            # Expected margin per unit
            buy_price = item["prebuy_contract_price"]
            sell_price = item["recommended_sell_price"]
            margin = sell_price - buy_price
            
            # Risk penalty per unit: spoilage factor + cancellation rate
            spoilage_factor = item.get("spoilage_risk_score", 0.25)
            canc_rate = item.get("cancellation_rate", 0.08)
            risk_penalty = (spoilage_factor * buy_price * 0.4) + (canc_rate * margin)

            # Risk-adjusted expected net margin per unit
            risk_adj_unit_profit = margin - (risk_weight * risk_penalty)

            item_metrics.append({
                "item": item,
                "forecast": f_res,
                "newsvendor": nv,
                "max_q": max(0, max_q),
                "min_q": min_q,
                "buy_price": buy_price,
                "sell_price": sell_price,
                "margin": margin,
                "unit_profit_score": risk_adj_unit_profit
            })

        # 2. Formulate MILP problem
        # Decision variables: q_i (integer number of units to pre-buy for item i)
        # Objective: Maximize sum(risk_adj_unit_profit_i * q_i) => Minimize sum(-risk_adj_unit_profit_i * q_i)
        c = np.array([-m["unit_profit_score"] for m in item_metrics], dtype=float)
        
        # Integrality: 1 = integer for all variables
        integrality = np.ones(n, dtype=int)

        # Variable Bounds: 0 <= q_i <= max_q_i
        lb = np.zeros(n, dtype=float)
        ub = np.array([float(m["max_q"]) for m in item_metrics], dtype=float)
        bounds = Bounds(lb, ub)

        # Constraints
        # A. Total Budget constraint: sum(buy_price_i * q_i) <= max_budget
        costs = np.array([float(m["buy_price"]) for m in item_metrics], dtype=float)
        
        constraint_rows = []
        lhs_bounds = []
        rhs_bounds = []

        # Row 1: Total budget
        constraint_rows.append(costs)
        lhs_bounds.append(0.0)
        rhs_bounds.append(max_budget)

        # Row 2: Hotel budget cap
        hotel_mask = np.array([1.0 if m["item"]["category"] == "Hotel" else 0.0 for m in item_metrics])
        constraint_rows.append(costs * hotel_mask)
        lhs_bounds.append(0.0)
        rhs_bounds.append(max_budget * hotel_budget_share * 1.05) # Allow 5% slack

        # Row 3: Flight budget cap
        flight_mask = np.array([1.0 if m["item"]["category"] == "Flight" else 0.0 for m in item_metrics])
        constraint_rows.append(costs * flight_mask)
        lhs_bounds.append(0.0)
        rhs_bounds.append(max_budget * (1.0 - hotel_budget_share) * 1.05)

        # Destination concentration constraints
        destinations = set(m["item"]["destination_code"] for m in item_metrics)
        for dest in destinations:
            dest_mask = np.array([1.0 if m["item"]["destination_code"] == dest else 0.0 for m in item_metrics])
            constraint_rows.append(costs * dest_mask)
            lhs_bounds.append(0.0)
            rhs_bounds.append(max_budget * max_destination_share)

        A = np.vstack(constraint_rows)
        constraints = LinearConstraint(A, lhs_bounds, rhs_bounds)

        # Solve MILP
        res = milp(c=c, integrality=integrality, bounds=bounds, constraints=constraints)

        allocations = []
        total_invested = 0.0
        total_expected_revenue = 0.0
        total_expected_profit = 0.0
        total_var_95 = 0.0
        total_units_unlocked = 0
        total_latent_demand_recovered = 0
        
        category_investments = {"Hotel": 0.0, "Flight": 0.0}
        destination_investments = {d: 0.0 for d in destinations}

        for idx, m in enumerate(item_metrics):
            raw_q = int(round(res.x[idx])) if res.success else 0
            # If allocated is less than min block, either snap to 0 or min block if budget permits
            final_q = raw_q if raw_q >= m["min_q"] else 0
            
            eval_metrics = RiskModel.evaluate_allocation(
                quantity=final_q,
                item=m["item"],
                mean_demand=m["forecast"]["mean_demand"],
                std_dev=m["forecast"]["std_dev"]
            )

            is_recommended = final_q > 0
            item_obj = m["item"]
            dest = item_obj["destination_code"]
            cat = item_obj["category"]

            if is_recommended:
                total_invested += eval_metrics["investment_cost"]
                total_expected_revenue += eval_metrics["expected_revenue"]
                total_expected_profit += eval_metrics["expected_profit"]
                total_var_95 += eval_metrics["value_at_risk_95"]
                total_units_unlocked += final_q
                total_latent_demand_recovered += int(min(final_q, item_obj.get("unmet_latent_demand", 0)))
                
                category_investments[cat] += eval_metrics["investment_cost"]
                destination_investments[dest] += eval_metrics["investment_cost"]

            # Strategy Recommendation tag
            if is_recommended:
                if eval_metrics["expected_roi_pct"] >= 16.0:
                    strategy_badge = "STRONG PRE-BUY (HIGH ROI)"
                elif eval_metrics["expected_sold"] / max(1, final_q) >= 0.88:
                    strategy_badge = "SECURE CAPACITY (HIGH DEMAND)"
                else:
                    strategy_badge = "SELECTIVE PRE-BUY"
            else:
                if item_obj.get("sold_out_frequency", 0) > 0.25:
                    strategy_badge = "SPOT-BUY AS NEEDED"
                else:
                    strategy_badge = "BYPASS / MONITOR"

            allocations.append({
                "item_id": item_obj["id"],
                "name": item_obj["name"],
                "category": cat,
                "destination_code": dest,
                "destination_city": item_obj["destination_city"],
                "travel_period": item_obj["travel_period"],
                "prebuy_contract_price": item_obj["prebuy_contract_price"],
                "spot_market_price": item_obj["spot_market_price"],
                "recommended_sell_price": item_obj["recommended_sell_price"],
                "optimal_prebuy_quantity": final_q,
                "max_allotment": item_obj["max_allotment"],
                "recommended_action": "PRE_BUY" if is_recommended else "SPOT_BUY_OR_PASS",
                "strategy_badge": strategy_badge,
                "investment_amount": eval_metrics["investment_cost"],
                "expected_sold_units": eval_metrics["expected_sold"],
                "expected_unsold_units": eval_metrics["expected_unsold"],
                "expected_profit": eval_metrics["expected_profit"],
                "expected_roi_pct": eval_metrics["expected_roi_pct"],
                "spoilage_risk_cost": eval_metrics["spoilage_cost"],
                "value_at_risk_95": eval_metrics["value_at_risk_95"],
                "look_to_book_ratio": item_obj["look_to_book_ratio"],
                "sold_out_rate_pct": round(item_obj["sold_out_frequency"] * 100, 1),
                "lcd_days": item_obj["lcd_days"],
                "signal": item_obj["upcoming_signal"]
            })

        # Sort allocations: Recommended first, descending by expected profit
        allocations.sort(key=lambda x: (x["recommended_action"] == "PRE_BUY", x["expected_profit"]), reverse=True)

        portfolio_roi = (total_expected_profit / total_invested * 100.0) if total_invested > 0 else 0.0

        return {
            "status": "success",
            "solver_converged": bool(res.success),
            "parameters": {
                "max_budget_inr": max_budget,
                "risk_tolerance": risk_tolerance,
                "hotel_budget_share": hotel_budget_share,
                "max_destination_share": max_destination_share,
                "demand_shock_pct": demand_shock_pct
            },
            "portfolio_summary": {
                "total_budget_allocated_inr": round(total_invested, 2),
                "budget_utilization_pct": round((total_invested / max_budget) * 100, 1),
                "unallocated_cash_buffer_inr": round(max_budget - total_invested, 2),
                "total_expected_revenue_inr": round(total_expected_revenue, 2),
                "total_expected_profit_inr": round(total_expected_profit, 2),
                "expected_portfolio_roi_pct": round(portfolio_roi, 1),
                "total_units_unlocked": total_units_unlocked,
                "latent_demand_recovered_units": total_latent_demand_recovered,
                "portfolio_value_at_risk_95_inr": round(total_var_95, 2),
                "category_breakdown": {
                    "hotel_investment_inr": round(category_investments["Hotel"], 2),
                    "flight_investment_inr": round(category_investments["Flight"], 2),
                    "hotel_share_pct": round((category_investments["Hotel"] / max(1, total_invested)) * 100, 1),
                    "flight_share_pct": round((category_investments["Flight"] / max(1, total_invested)) * 100, 1)
                },
                "destination_breakdown": {
                    d: {
                        "investment_inr": round(amt, 2),
                        "share_pct": round((amt / max(1, total_invested)) * 100, 1)
                    } for d, amt in destination_investments.items() if amt > 0
                }
            },
            "allocations": allocations
        }
