# TBO.com | SmartInventory Decision-Support Platform
### Autonomous Travel Inventory Procurement & Portfolio Optimization Engine

> **Built for the TBO Hackathon Challenge: Inventory Optimization for TBO.com**  
> *"Maximizing availability by making smarter travel inventory procurement decisions."*

---

## 🌟 Executive Summary

In B2B travel distribution, **inventory availability is revenue**. When high-demand hotels and flight seats sell out, TBO loses high-intent bookings to competitors. However, advance inventory commitments (**pre-buys**) carry acute **perishability risks** (unsold rooms/seats spoil with zero salvage value after check-in/flight departure).

The **TBO SmartInventory Decision-Support Platform** transforms raw search streams, booking histories, Look-to-Book (L2B) ratios, and sold-out signals into **actionable, risk-adjusted inventory investment recommendations**.

Given a maximum capital budget (e.g., ₹5 Crore), the system solves a **Mixed-Integer Linear Programming (MILP)** portfolio problem that:
1. **Unlocks Maximum Availability**: Targets high-velocity corridors (Dubai, London, Singapore, Bangkok, Bali, Goa, Paris, Tokyo).
2. **Captures Censored Latent Demand**: Recovers unfulfilled demand where searches returned zero availability.
3. **Protects Downside Risk**: Applies Newsvendor perishability models, cancellation hazard rates, and Last Cancellation Date (LCD) re-marketing windows.
4. **Generates Dispatch-Ready Supplier POs**: Exports structured RFPs ready for hotel chains and airline procurement teams.

---

## 🎯 Hackathon Objectives Checklist

| Problem Statement Objective | Platform Solution | Module & Implementation |
| :--- | :--- | :--- |
| **1. Predict Demand** | Latent demand recovery from Look-to-Book (L2B) and sold-out frequencies | `DemandForecaster` in `backend/app/engine/demand_forecaster.py` |
| **2. Identify Opportunities** | Pre-buy rate arbitrage (20–35% discount against spot market) | `travel_data_generator.py` & Opportunity Matrix in Dashboard |
| **3. Optimize Investments** | Constrained MILP allocation under budget, category, & corridor caps | `BudgetOptimizer` in `backend/app/optimizer/budget_optimizer.py` |
| **4. Maximize Profitability** | Optimal purchase quantities ($q^*$), negotiated buy rates, and dynamic retail markups | Newsvendor Critical Ratio ($CR$) & SciPy HiGHS Solver |
| **5. Manage Risk** | Spoilage loss modeling, LCD cut-off buffers, and 95% Value-at-Risk (VaR) | `RiskModel` in `backend/app/engine/risk_model.py` |
| **6. Decision-Support Platform** | Interactive budget sliders, real-time recalculation, and What-If simulator | FastAPI + Tailwind CSS + Chart.js dashboard (`backend/app/static/index.html`) |

---

## 📐 Mathematical Formulation

### 1. Censored Latent Demand Recovery
Traditional systems only record realized bookings $B$. When inventory sells out at frequency $f_{\text{soldout}}$, the true latent demand $D_{\text{latent}}$ is censored. We estimate latent demand using conversion intent velocity from the Look-to-Book ratio ($\text{L2B}$):

$$D_{\text{latent}} = B + \left( B \cdot \frac{f_{\text{soldout}}}{1 - f_{\text{soldout}}} \cdot \min\left(2.5, \frac{150}{\text{L2B}}\right) \right)$$

### 2. Newsvendor Perishability & Critical Ratio
For advance procurement:
- **Underage Cost** ($C_u$): Lost profit per unfulfilled traveller demand $= P_{\text{sell}} - C_{\text{prebuy}}$
- **Overage Cost** ($C_o$): Net loss per unsold perishable room/seat $= C_{\text{prebuy}} - S_{\text{salvage}}$
- **Critical Ratio** ($CR$):

$$CR = \frac{C_u}{C_u + C_o} = \frac{P_{\text{sell}} - C_{\text{prebuy}}}{(P_{\text{sell}} - C_{\text{prebuy}}) + (C_{\text{prebuy}} - S_{\text{salvage}})}$$

The unconstrained target quantity is $Q^* = \mu + \Phi^{-1}(CR) \cdot \sigma$.

### 3. Constrained Portfolio Optimization (MILP)
Given total budget $B_{\max}$ and risk aversion parameter $\lambda$:

$$\max_{q_1, \dots, q_n \in \mathbb{Z}^+} \sum_{i=1}^{n} \left[ \mathbb{E}[\text{Profit}_i(q_i)] - \lambda \cdot \text{RiskPenalty}_i(q_i) \right]$$

**Subject to:**
1. **Total Budget Constraint**: $\sum_{i=1}^{n} C_i^{\text{prebuy}} \cdot q_i \le B_{\max}$
2. **Category Allocation**: $\sum_{i \in \text{Hotel}} C_i \cdot q_i \le B_{\max} \cdot w_{\text{hotel}}$, $\sum_{i \in \text{Flight}} C_i \cdot q_i \le B_{\max} \cdot (1 - w_{\text{hotel}})$
3. **Corridor Concentration Cap**: $\sum_{i \in \text{Dest}_d} C_i \cdot q_i \le B_{\max} \cdot \kappa_{\text{dest}}$ (prevents over-exposure to a single market)
4. **Contractual Block Bounds**: $q_i \in \{0\} \cup [M_i^{\min}, \min(A_i^{\max}, Q_i^*)]$

Solved in real time using the **SciPy HiGHS Mixed-Integer Linear Programming Solver**.

---

## 🚀 Quickstart & Run Instructions

### Prerequisites
- Python 3.9+ (Python 3.12 recommended)
- Dependencies: `fastapi`, `uvicorn`, `scipy`, `numpy`, `pandas`, `pydantic`

### 1. Launch the Decision Support Server
From the project directory:
```bash
cd /Users/lavanayakhosla/.gemini/antigravity/scratch/tbo-inventory-optimizer
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Access the Platform
- **Interactive Decision-Support Dashboard**: [http://localhost:8000/](http://localhost:8000/)
- **Swagger / OpenAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Health Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

### 3. Run Automated Unit & Integration Tests
```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m unittest backend/tests/test_optimizer.py
```

---

## 🎬 3-Minute Demo Script for Judges

1. **The Problem Setup (30s)**:
   - *"In high season, TBO loses up to 38% of searches in corridors like Dubai and Goa because hotels and flights sell out. If we buy at spot price, margins vanish. If we pre-buy blind, unsold rooms spoil."*
2. **Interactive Budget Allocation (60s)**:
   - Open [http://localhost:8000/](http://localhost:8000/).
   - Drag the **Procurement Budget Slider** from ₹1 Cr to ₹10 Cr.
   - Show how the **SciPy HiGHS MILP Solver** instantly re-optimizes capital across Dubai, London, Bangkok, Bali, and Goa within milliseconds.
   - Toggle **Risk Tolerance** (Conservative $\to$ Balanced $\to$ Aggressive) and observe how capital shifts from defensive business corridors to high-margin holiday surges.
3. **Latent Demand & Censored Recovery (45s)**:
   - Point to the **Corridor Demand Chart**: Highlight the yellow bars indicating unfulfilled searches recovered from sold-outs.
4. **AI Strategic Investment Rationale (30s)**:
   - Click **"AI Rationale"** on *Atlantis The Palm - Dubai* or *DEL ⇄ BKK Flight Block*.
   - Show the generated investment underwriting thesis explaining the exact pre-buy discount, critical ratio, and LCD cut-off protection.
5. **PO Dispatch & Supplier Negotiation (15s)**:
   - Click **"Dispatch RFP / PO"** in the top navigation.
   - Inspect the generated procurement line items and click **"Download Procurement CSV"** ready for supplier commercial teams.

---

## 📂 Project Architecture

```
tbo-inventory-optimizer/
├── README.md                                # Comprehensive documentation & demo guide
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                          # FastAPI server & REST endpoints
│   │   ├── data/
│   │   │   ├── travel_data_generator.py     # High-fidelity TBO travel data synthesizer
│   │   │   └── sample_seed.json             # 180 realistic inventory items across 8 corridors
│   │   ├── engine/
│   │   │   ├── demand_forecaster.py         # Censored demand recovery & L2B forecasting
│   │   │   └── risk_model.py                # Newsvendor perishability, LCD, and 95% VaR
│   │   ├── optimizer/
│   │   │   ├── budget_optimizer.py          # SciPy HiGHS MILP constrained portfolio optimizer
│   │   │   └── scenario_simulator.py        # Macro shock & "What-If" stress testing
│   │   └── static/
│   │       └── index.html                   # Interactive executive decision-support dashboard
│   └── tests/
│       └── test_optimizer.py                # Comprehensive automated test suite
```
