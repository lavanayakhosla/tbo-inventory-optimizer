"""
TBO SmartInventory Decision Support API
FastAPI backend powering inventory procurement optimization, demand forecasting,
perishability risk mitigation, and scenario analysis for TBO.com.
"""

import json
import os
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from backend.app.data.travel_data_generator import generate_travel_dataset
from backend.app.engine.demand_forecaster import DemandForecaster
from backend.app.engine.risk_model import RiskModel
from backend.app.optimizer.budget_optimizer import BudgetOptimizer
from backend.app.optimizer.scenario_simulator import ScenarioSimulator

app = FastAPI(
    title="TBO.com SmartInventory Optimizer API",
    description="Data-driven intelligence and decision-support for B2B travel inventory procurement",
    version="1.0.0"
)

# Enable CORS for local dev / dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load or generate seed data
SEED_PATH = os.path.join(os.path.dirname(__file__), "data", "sample_seed.json")
if not os.path.exists(SEED_PATH):
    seed_data = generate_travel_dataset(seed=42)
    with open(SEED_PATH, "w") as f:
        json.dump(seed_data, f, indent=2)
else:
    with open(SEED_PATH, "r") as f:
        seed_data = json.load(f)

INVENTORY_CACHE = seed_data["inventory"]
DESTINATIONS_CACHE = seed_data["destinations"]


class OptimizationRequest(BaseModel):
    max_budget_inr: float = Field(default=50_000_000.0, description="Total procurement budget in INR")
    risk_tolerance: str = Field(default="balanced", description="conservative | balanced | aggressive")
    hotel_budget_share: float = Field(default=0.65, description="Target share for Hotels (0.1 to 0.9)")
    max_destination_share: float = Field(default=0.30, description="Max exposure to a single destination")
    demand_shock_pct: float = Field(default=0.0, description="Stress testing demand shock % (-50 to +50)")


class ScenarioRequest(BaseModel):
    base_budget_inr: float = Field(default=50_000_000.0, description="Base budget for scenario comparison")


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "TBO SmartInventory Optimizer",
        "total_inventory_items": len(INVENTORY_CACHE),
        "destinations": len(DESTINATIONS_CACHE)
    }


@app.get("/api/inventory/summary")
def get_inventory_summary():
    """Returns high-level summary of all monitored travel corridors and inventory items."""
    total_searches = sum(item["search_volume_30d"] for item in INVENTORY_CACHE)
    total_latent = sum(item.get("unmet_latent_demand", 0) for item in INVENTORY_CACHE)
    avg_sold_out = sum(item["sold_out_frequency"] for item in INVENTORY_CACHE) / len(INVENTORY_CACHE)
    avg_l2b = sum(item["look_to_book_ratio"] for item in INVENTORY_CACHE) / len(INVENTORY_CACHE)

    return {
        "total_items": len(INVENTORY_CACHE),
        "destinations": DESTINATIONS_CACHE,
        "metrics": {
            "monthly_search_volume": total_searches,
            "estimated_unmet_latent_demand": total_latent,
            "average_sold_out_rate_pct": round(avg_sold_out * 100, 1),
            "average_look_to_book": round(avg_l2b, 1),
            "hotel_count": len([i for i in INVENTORY_CACHE if i["category"] == "Hotel"]),
            "flight_count": len([i for i in INVENTORY_CACHE if i["category"] == "Flight"])
        }
    }


@app.post("/api/optimizer/allocate")
def run_budget_allocation(req: OptimizationRequest):
    """
    Executes Mixed-Integer Linear Programming budget optimization across all items.
    """
    try:
        results = BudgetOptimizer.optimize(
            inventory_items=INVENTORY_CACHE,
            max_budget=req.max_budget_inr,
            risk_tolerance=req.risk_tolerance,
            hotel_budget_share=req.hotel_budget_share,
            max_destination_share=req.max_destination_share,
            demand_shock_pct=req.demand_shock_pct
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/optimizer/scenario")
def run_scenario_stress_test(req: ScenarioRequest):
    """
    Simulates macroeconomic and demand shocks across the inventory portfolio.
    """
    try:
        scenario_results = ScenarioSimulator.run_all_scenarios(
            inventory_items=INVENTORY_CACHE,
            base_budget=req.base_budget_inr
        )
        return {
            "status": "success",
            "base_budget_inr": req.base_budget_inr,
            "scenarios": scenario_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/demand/trends")
def get_demand_trends():
    """
    Returns search volumes, conversion velocity, and sold-out rates grouped by destination.
    """
    dest_data = {}
    for d in DESTINATIONS_CACHE:
        dest_data[d["code"]] = {
            "city": d["city"],
            "country": d["country"],
            "upcoming_event": d["upcoming_event"],
            "searches": 0,
            "realized_bookings": 0,
            "unmet_demand": 0,
            "avg_sold_out_pct": []
        }

    for item in INVENTORY_CACHE:
        code = item["destination_code"]
        if code in dest_data:
            dest_data[code]["searches"] += item["search_volume_30d"]
            dest_data[code]["realized_bookings"] += item["realized_bookings"]
            dest_data[code]["unmet_demand"] += item.get("unmet_latent_demand", 0)
            dest_data[code]["avg_sold_out_pct"].append(item["sold_out_frequency"])

    results = []
    for code, data in dest_data.items():
        so_list = data["avg_sold_out_pct"]
        avg_so = (sum(so_list) / len(so_list) * 100) if so_list else 0.0
        results.append({
            "code": code,
            "city": data["city"],
            "country": data["country"],
            "upcoming_event": data["upcoming_event"],
            "search_volume": data["searches"],
            "realized_bookings": data["realized_bookings"],
            "unmet_latent_demand": data["unmet_demand"],
            "look_to_book": round(data["searches"] / max(1, data["realized_bookings"]), 1),
            "avg_sold_out_rate_pct": round(avg_so, 1)
        })

    results.sort(key=lambda x: x["search_volume"], reverse=True)
    return results


@app.get("/api/explain/{item_id}")
def explain_recommendation(item_id: str):
    """
    Generates an explainable AI investment thesis and negotiation memo for a specific inventory block.
    """
    target = next((item for item in INVENTORY_CACHE if item["id"] == item_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Item not found")

    forecast = DemandForecaster.forecast_demand(target)
    nv = RiskModel.calculate_newsvendor_optimum(target, forecast["mean_demand"], forecast["std_dev"])

    discount_pct = round(((target["spot_market_price"] - target["prebuy_contract_price"]) / target["spot_market_price"]) * 100, 1)
    margin_pct = target["margin_percentage"]
    sold_out_pct = round(target["sold_out_frequency"] * 100, 1)

    thesis = (
        f"**Investment Rationale for {target['name']} ({target['travel_period']})**:\n\n"
        f"1. **Latent Demand Signal**: Look-to-Book ratio is **{target['look_to_book_ratio']}:1** with a **{sold_out_pct}% historical sold-out rate**, indicating significant unfulfilled traveller demand. Estimated latent demand is **{forecast['estimated_latent_demand']} units**.\n"
        f"2. **Rate Arbitrage**: Negotiated pre-buy rate of **₹{target['prebuy_contract_price']:,}** provides a **{discount_pct}% discount** against current spot market rates of **₹{target['spot_market_price']:,}**. Recommended retail sell price of **₹{target['recommended_sell_price']:,}** secures a healthy **{margin_pct}% margin** while keeping TBO highly competitive.\n"
        f"3. **Perishability & Downside Control**: Critical ratio is **{nv['critical_ratio']}**. Last Cancellation Date (LCD) is **{target['lcd_days']} days prior to travel**, providing an adequate re-marketing window to liquidate any unsold allotment without incurring 100% spoilage penalty.\n"
        f"4. **Action Directive**: Lock in pre-buy contract for **{nv['unconstrained_optimal_q']} units** to maximize bookable inventory availability ahead of `{target['upcoming_signal']}`."
    )

    return {
        "item_id": item_id,
        "name": target["name"],
        "category": target["category"],
        "destination": f"{target['destination_city']}, {target['destination_country']}",
        "thesis_markdown": thesis,
        "metrics": {
            "forecasted_mean_demand": forecast["mean_demand"],
            "latent_demand_unmet": forecast["estimated_latent_demand"],
            "prebuy_discount_pct": discount_pct,
            "margin_pct": margin_pct,
            "critical_ratio": nv["critical_ratio"],
            "lcd_days": target["lcd_days"],
            "spoilage_risk_score": target["spoilage_risk_score"]
        }
    }


@app.post("/api/procurement/rfp")
def generate_procurement_rfp(req: OptimizationRequest):
    """
    Generates a structured procurement order / RFP manifest ready to dispatch to hotel chains and airlines.
    """
    opt_res = BudgetOptimizer.optimize(
        inventory_items=INVENTORY_CACHE,
        max_budget=req.max_budget_inr,
        risk_tolerance=req.risk_tolerance,
        hotel_budget_share=req.hotel_budget_share
    )

    recommended = [a for a in opt_res["allocations"] if a["recommended_action"] == "PRE_BUY"]
    
    rfp_orders = []
    for idx, rec in enumerate(recommended, 1):
        rfp_orders.append({
            "po_line_number": idx,
            "item_id": rec["item_id"],
            "supplier_asset": rec["name"],
            "category": rec["category"],
            "destination": f"{rec['destination_city']} ({rec['destination_code']})",
            "travel_window": rec["travel_period"],
            "contracted_quantity": rec["optimal_prebuy_quantity"],
            "target_procurement_rate_inr": rec["prebuy_contract_price"],
            "total_line_commitment_inr": rec["investment_amount"],
            "cancellation_cut_off_days": rec["lcd_days"],
            "procurement_status": "READY_FOR_DISPATCH"
        })

    return {
        "rfp_id": f"TBO-PREBUY-{os.urandom(3).hex().upper()}",
        "organization": "TBO.com Global Procurement Group",
        "total_po_lines": len(rfp_orders),
        "total_budget_committed_inr": opt_res["portfolio_summary"]["total_budget_allocated_inr"],
        "expected_portfolio_roi_pct": opt_res["portfolio_summary"]["expected_portfolio_roi_pct"],
        "purchase_orders": rfp_orders
    }


# Mount static dashboard directory
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")

if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
elif os.path.exists(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

