"""
Unit and Integration Tests for TBO SmartInventory Optimizer
Verifies:
1. Demand forecasting and latent demand recovery
2. Risk model and Newsvendor optimality
3. MILP Budget optimization and constraint enforcement
4. Scenario simulation
5. FastAPI endpoint integration
"""

import unittest
from fastapi.testclient import TestClient

from backend.app.data.travel_data_generator import generate_travel_dataset
from backend.app.engine.demand_forecaster import DemandForecaster
from backend.app.engine.risk_model import RiskModel
from backend.app.optimizer.budget_optimizer import BudgetOptimizer
from backend.app.optimizer.scenario_simulator import ScenarioSimulator
from backend.app.main import app


class TestInventoryOptimizer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.data = generate_travel_dataset(seed=123)
        cls.client = TestClient(app)

    def test_demand_forecaster(self):
        item = self.data["inventory"][0]
        f = DemandForecaster.forecast_demand(item)
        self.assertIn("mean_demand", f)
        self.assertIn("estimated_latent_demand", f)
        self.assertGreater(f["mean_demand"], 0)
        self.assertGreaterEqual(f["p90_optimistic"], f["p50_expected"])
        self.assertGreaterEqual(f["p50_expected"], f["p10_conservative"])

    def test_risk_model_newsvendor(self):
        item = self.data["inventory"][0]
        nv = RiskModel.calculate_newsvendor_optimum(item, mean_demand=100, std_dev=20)
        self.assertGreater(nv["critical_ratio"], 0.0)
        self.assertLess(nv["critical_ratio"], 1.0)
        self.assertGreater(nv["unconstrained_optimal_q"], 0)

        eval_res = RiskModel.evaluate_allocation(50, item, mean_demand=100, std_dev=20)
        self.assertEqual(eval_res["allocated_quantity"], 50)
        self.assertGreater(eval_res["expected_revenue"], 0)
        self.assertGreater(eval_res["investment_cost"], 0)

    def test_budget_optimizer_constraints(self):
        budget = 30_000_000.0  # ₹3 Crore
        res = BudgetOptimizer.optimize(
            inventory_items=self.data["inventory"],
            max_budget=budget,
            risk_tolerance="balanced",
            hotel_budget_share=0.70
        )
        self.assertTrue(res["solver_converged"])
        summary = res["portfolio_summary"]
        
        # Budget constraint check
        self.assertLessEqual(summary["total_budget_allocated_inr"], budget + 1.0)
        self.assertGreater(summary["total_units_unlocked"], 0)
        self.assertGreater(summary["total_expected_profit_inr"], 0)

        # Check Hotel budget constraint
        hotel_inv = summary["category_breakdown"]["hotel_investment_inr"]
        self.assertLessEqual(hotel_inv, budget * 0.70 * 1.06)

    def test_scenario_simulator(self):
        scenarios = ScenarioSimulator.run_all_scenarios(self.data["inventory"], base_budget=20_000_000.0)
        self.assertGreaterEqual(len(scenarios), 3)
        scenario_ids = [s["scenario_id"] for s in scenarios]
        self.assertIn("baseline", scenario_ids)
        self.assertIn("demand_slump", scenario_ids)
        self.assertIn("holiday_surge", scenario_ids)

    def test_api_endpoints(self):
        # Health
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "healthy")

        # Inventory summary
        res = self.client.get("/api/inventory/summary")
        self.assertEqual(res.status_code, 200)
        self.assertIn("metrics", res.json())

        # Allocate API
        res = self.client.post("/api/optimizer/allocate", json={
            "max_budget_inr": 25000000.0,
            "risk_tolerance": "balanced",
            "hotel_budget_share": 0.60
        })
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertTrue(payload["solver_converged"])
        self.assertGreater(len(payload["allocations"]), 0)

        # Scenario API
        res = self.client.post("/api/optimizer/scenario", json={"base_budget_inr": 25000000.0})
        self.assertEqual(res.status_code, 200)
        self.assertIn("scenarios", res.json())

        # Demand trends
        res = self.client.get("/api/demand/trends")
        self.assertEqual(res.status_code, 200)
        self.assertGreater(len(res.json()), 0)

        # Explain API
        first_item_id = self.data["inventory"][0]["id"]
        res = self.client.get(f"/api/explain/{first_item_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("thesis_markdown", res.json())

        # RFP PO generation
        res = self.client.post("/api/procurement/rfp", json={"max_budget_inr": 25000000.0})
        self.assertEqual(res.status_code, 200)
        self.assertIn("purchase_orders", res.json())


if __name__ == "__main__":
    unittest.main()
