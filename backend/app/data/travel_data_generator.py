"""
TBO Travel Data Generator
Simulates realistic B2B travel inventory, search signals, sold-outs, and booking dynamics.
"""

import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any


DESTINATIONS = [
    {
        "code": "DXB",
        "city": "Dubai",
        "country": "UAE",
        "seasonality_factor": 1.45,
        "upcoming_event": "Dubai Shopping Festival & Tech Summit",
        "event_multiplier": 1.35
    },
    {
        "code": "LHR",
        "city": "London",
        "country": "UK",
        "seasonality_factor": 1.15,
        "upcoming_event": "WTM London & Holiday Shopping",
        "event_multiplier": 1.20
    },
    {
        "code": "SIN",
        "city": "Singapore",
        "country": "Singapore",
        "seasonality_factor": 1.25,
        "upcoming_event": "Singapore Fintech Festival & Marina Bay NYE",
        "event_multiplier": 1.30
    },
    {
        "code": "BKK",
        "city": "Bangkok",
        "country": "Thailand",
        "seasonality_factor": 1.50,
        "upcoming_event": "Winter Peak Sun & Beach Season",
        "event_multiplier": 1.40
    },
    {
        "code": "DPS",
        "city": "Bali",
        "country": "Indonesia",
        "seasonality_factor": 1.35,
        "upcoming_event": "Year-End Island Festival",
        "event_multiplier": 1.25
    },
    {
        "code": "GOI",
        "city": "Goa",
        "country": "India",
        "seasonality_factor": 1.60,
        "upcoming_event": "Sunburn Festival & Christmas/New Year Rush",
        "event_multiplier": 1.55
    },
    {
        "code": "CDG",
        "city": "Paris",
        "country": "France",
        "seasonality_factor": 1.10,
        "upcoming_event": "Winter Fashion Week & Holiday Lights",
        "event_multiplier": 1.15
    },
    {
        "code": "HND",
        "city": "Tokyo",
        "country": "Japan",
        "seasonality_factor": 1.30,
        "upcoming_event": "Winter Illuminations & New Year Tourism",
        "event_multiplier": 1.25
    }
]

HOTEL_TEMPLATES = [
    {"name": "Atlantis The Palm / Royal", "stars": 5, "type": "Luxury Resort", "base_spot": 28000, "discount": 0.28, "allotment": 350},
    {"name": "Marriott Marquis / City Center", "stars": 5, "type": "Business Luxury", "base_spot": 18500, "discount": 0.25, "allotment": 400},
    {"name": "Novotel / Holiday Inn Express", "stars": 4, "type": "Midscale Business", "base_spot": 9500, "discount": 0.22, "allotment": 500},
    {"name": "Radisson Blu Waterfront", "stars": 4, "type": "Upscale Leisure", "base_spot": 12000, "discount": 0.24, "allotment": 450},
    {"name": "Ibis Styles / Premier Inn", "stars": 3, "type": "Budget Select", "base_spot": 5800, "discount": 0.20, "allotment": 600},
]

FLIGHT_ROUTES = [
    {"origin": "DEL", "airline": "Emirates / Air India", "class": "Economy Block", "base_spot": 26000, "discount": 0.22, "allotment": 250},
    {"origin": "BOM", "airline": "Singapore Airlines / IndiGo", "class": "Economy Block", "base_spot": 28500, "discount": 0.20, "allotment": 220},
    {"origin": "DEL", "airline": "British Airways / Virgin", "class": "Premium/Economy Block", "base_spot": 58000, "discount": 0.24, "allotment": 180},
    {"origin": "BOM", "airline": "Thai Airways / AirAsia", "class": "Economy Block", "base_spot": 21000, "discount": 0.25, "allotment": 300},
    {"origin": "DEL", "airline": "IndiGo / SpiceJet", "class": "Domestic Prime Block", "base_spot": 9500, "discount": 0.26, "allotment": 450},
]


def generate_travel_dataset(seed: int = 42) -> Dict[str, Any]:
    """Generates a complete dataset with travel items, search logs, and demand metrics."""
    random.seed(seed)
    items = []
    item_id = 101

    periods = [
        {"name": "Next 30 Days (Peak Window)", "days_out": 14, "duration": 30, "surge_prob": 0.8},
        {"name": "60-90 Days Out (Advance Horizon)", "days_out": 45, "duration": 45, "surge_prob": 0.5},
        {"name": "Holiday Special (Year-End Peak)", "days_out": 30, "duration": 15, "surge_prob": 0.9},
    ]

    for dest in DESTINATIONS:
        # 1. Hotels for this destination
        for h_tmpl in HOTEL_TEMPLATES:
            for period in periods:
                spot_price = round(h_tmpl["base_spot"] * dest["seasonality_factor"] * (0.95 + random.random() * 0.15), -2)
                discount_rate = h_tmpl["discount"] + (random.random() * 0.06 - 0.03)
                prebuy_price = round(spot_price * (1.0 - discount_rate), -2)
                
                # Dynamic selling price recommendation (usually 10-15% margin above pre-buy, still beating spot!)
                recommended_sell = round(prebuy_price * 1.14, -2)
                
                # Search volume & Look-to-Book (L2B)
                searches = int(random.randint(4500, 32000) * dest["seasonality_factor"])
                has_event = random.random() < period["surge_prob"]
                if has_event:
                    searches = int(searches * dest["event_multiplier"])
                
                l2b_ratio = round(random.uniform(55.0, 220.0), 1)
                realized_bookings = int(searches / l2b_ratio)
                
                # Sold-out indicator (searches where users found 0 rooms)
                sold_out_rate = round(random.uniform(0.08, 0.38) if has_event else random.uniform(0.02, 0.16), 3)
                unmet_demand_units = int(realized_bookings * sold_out_rate * 1.8)
                total_latent_demand = realized_bookings + unmet_demand_units
                
                # Risk metrics
                cancellation_rate = round(random.uniform(0.06, 0.18), 3)
                lcd_days = random.choice([7, 14, 21, 30])
                spoilage_risk_score = round(random.uniform(0.12, 0.42), 2)

                item = {
                    "id": f"HTL-{item_id}",
                    "category": "Hotel",
                    "destination_code": dest["code"],
                    "destination_city": dest["city"],
                    "destination_country": dest["country"],
                    "name": f"{h_tmpl['name']} - {dest['city']}",
                    "stars": h_tmpl["stars"],
                    "property_type": h_tmpl["type"],
                    "travel_period": period["name"],
                    "days_until_travel": period["days_out"],
                    "duration_days": period["duration"],
                    "max_allotment": h_tmpl["allotment"],
                    "min_commitment_block": 20,
                    "spot_market_price": spot_price,
                    "prebuy_contract_price": prebuy_price,
                    "recommended_sell_price": recommended_sell,
                    "unit_margin_inr": recommended_sell - prebuy_price,
                    "margin_percentage": round(((recommended_sell - prebuy_price) / recommended_sell) * 100, 1),
                    "search_volume_30d": searches,
                    "look_to_book_ratio": l2b_ratio,
                    "realized_bookings": realized_bookings,
                    "sold_out_frequency": sold_out_rate,
                    "unmet_latent_demand": unmet_demand_units,
                    "total_forecasted_demand": total_latent_demand,
                    "demand_std_dev": round(total_latent_demand * random.uniform(0.15, 0.28)),
                    "cancellation_rate": cancellation_rate,
                    "lcd_days": lcd_days,
                    "spoilage_risk_score": spoilage_risk_score,
                    "upcoming_signal": dest["upcoming_event"] if has_event else "Standard High Season"
                }
                items.append(item)
                item_id += 1

        # 2. Flights for this destination
        for f_tmpl in FLIGHT_ROUTES:
            if dest["code"] in ["DXB", "LHR", "SIN", "BKK", "DPS", "GOI"]:
                for period in periods[:2]:
                    spot_fare = round(f_tmpl["base_spot"] * dest["seasonality_factor"] * (0.95 + random.random() * 0.15), -2)
                    discount_rate = f_tmpl["discount"]
                    prebuy_fare = round(spot_fare * (1.0 - discount_rate), -2)
                    recommended_sell = round(prebuy_fare * 1.12, -2)

                    searches = int(random.randint(6000, 45000) * dest["seasonality_factor"])
                    l2b_ratio = round(random.uniform(60.0, 190.0), 1)
                    realized_bookings = int(searches / l2b_ratio)
                    sold_out_rate = round(random.uniform(0.10, 0.45), 3)
                    unmet_demand_units = int(realized_bookings * sold_out_rate * 1.6)
                    total_latent_demand = realized_bookings + unmet_demand_units

                    item = {
                        "id": f"FLT-{item_id}",
                        "category": "Flight",
                        "destination_code": dest["code"],
                        "destination_city": dest["city"],
                        "destination_country": dest["country"],
                        "name": f"{f_tmpl['origin']} ⇄ {dest['code']} ({f_tmpl['airline']})",
                        "stars": None,
                        "property_type": f_tmpl["class"],
                        "travel_period": period["name"],
                        "days_until_travel": period["days_out"],
                        "duration_days": period["duration"],
                        "max_allotment": f_tmpl["allotment"],
                        "min_commitment_block": 15,
                        "spot_market_price": spot_fare,
                        "prebuy_contract_price": prebuy_fare,
                        "recommended_sell_price": recommended_sell,
                        "unit_margin_inr": recommended_sell - prebuy_fare,
                        "margin_percentage": round(((recommended_sell - prebuy_fare) / recommended_sell) * 100, 1),
                        "search_volume_30d": searches,
                        "look_to_book_ratio": l2b_ratio,
                        "realized_bookings": realized_bookings,
                        "sold_out_frequency": sold_out_rate,
                        "unmet_latent_demand": unmet_demand_units,
                        "total_forecasted_demand": total_latent_demand,
                        "demand_std_dev": round(total_latent_demand * random.uniform(0.12, 0.25)),
                        "cancellation_rate": round(random.uniform(0.04, 0.12), 3),
                        "lcd_days": random.choice([14, 21, 30]),
                        "spoilage_risk_score": round(random.uniform(0.10, 0.35), 2),
                        "upcoming_signal": f"Seat allotment surge for {dest['city']} corridor"
                    }
                    items.append(item)
                    item_id += 1

    return {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "destinations_count": len(DESTINATIONS),
            "total_inventory_items": len(items),
            "currency": "INR",
            "source": "TBO Simulated Production Feed"
        },
        "destinations": DESTINATIONS,
        "inventory": items
    }


if __name__ == "__main__":
    data = generate_travel_dataset()
    print(f"Generated {len(data['inventory'])} inventory items across {len(data['destinations'])} destinations.")
    with open("/Users/lavanayakhosla/.gemini/antigravity/scratch/tbo-inventory-optimizer/backend/app/data/sample_seed.json", "w") as f:
        json.dump(data, f, indent=2)
    print("Saved sample_seed.json successfully.")
