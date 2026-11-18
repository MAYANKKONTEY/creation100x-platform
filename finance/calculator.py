#!/usr/bin/env python3
"""Unit economics + scenario calculator.

Usage:
    python3 finance/calculator.py                 # prints report, writes finance/unit-economics.csv
    python3 finance/calculator.py --check         # runs self-tests only

No third-party dependencies. All inputs live in finance/assumptions.json.
Revenue is never reported as profit; every fee is itemised.
"""
from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSUMPTIONS = HERE / "assumptions.json"
OUT_CSV = HERE / "unit-economics.csv"


@dataclass
class UnitResult:
    product_id: str
    scenario: str
    market: str
    price: float
    supplier_cost: float
    shipping_cost: float
    duty: float
    packaging: float
    paypal_fee: float
    paypal_fx_spread: float
    gst_on_fees: float
    shopify_txn_fee: float
    refund_allowance: float
    cac: float
    variable_costs: float
    gross_margin_pct: float
    contribution_per_order: float
    contribution_margin_pct: float
    breakeven_price: float
    breakeven_cac: float
    orders_per_month: int
    revenue_month: float
    contribution_month: float
    fixed_month: float
    operating_profit_month: float
    breakeven_orders_month: float
    cash_needed_per_order: float


def unit_economics(p: dict, sc: dict, fees: dict, fixed_usd: float, scenario: str) -> UnitResult:
    price = round(p["price_usd"] * sc["price_multiplier"], 2)
    supplier = p["supplier_cost_usd"] * sc["cost_multiplier"]
    shipping = p["shipping_cost_usd"] * sc["cost_multiplier"]
    duty = p["duty_and_import_usd"] * sc["cost_multiplier"]
    pack = p["packaging_insert_usd"]
    cogs = supplier + shipping + duty + pack

    paypal_fee = price * fees["paypal_pct"] + fees["paypal_fixed_usd"]
    fx_spread = (price - paypal_fee) * fees["paypal_conversion_spread_pct"]
    gst = paypal_fee * fees["gst_on_gateway_fees_pct"]
    shopify_fee = price * fees["shopify_third_party_fee_pct"]
    refund_rate = min(p["refund_rate"] * sc["refund_multiplier"], 1.0)
    # Refund allowance: lost price on refunded orders + share of COGS not recoverable.
    # PayPal does not return its fixed fee on refunds; we conservatively treat full price as lost
    # on refunded orders and add back nothing.
    refund_allowance = refund_rate * (price * p.get("return_cost_share", 0.5) + cogs * 0.5)
    cac = sc["cac_usd"]

    variable = cogs + paypal_fee + fx_spread + gst + shopify_fee + refund_allowance + cac
    contribution = price - variable
    pct_fees = fees["paypal_pct"] * (1 + fees["gst_on_gateway_fees_pct"]) + fees["shopify_third_party_fee_pct"]
    pct_fees += (1 - fees["paypal_pct"]) * fees["paypal_conversion_spread_pct"]
    pct_refund = refund_rate * p.get("return_cost_share", 0.5)
    fixed_per_order_costs = (cogs + fees["paypal_fixed_usd"] * (1 + fees["gst_on_gateway_fees_pct"])
                             - fees["paypal_fixed_usd"] * fees["paypal_conversion_spread_pct"]
                             + refund_rate * cogs * 0.5 + cac)
    denom = 1 - pct_fees - pct_refund
    breakeven_price = fixed_per_order_costs / denom if denom > 0 else float("inf")

    n = sc["orders_per_month"]
    revenue = price * n
    contribution_m = contribution * n
    operating = contribution_m - fixed_usd
    cm_without_cac = contribution + cac
    breakeven_orders = fixed_usd / contribution if contribution > 0 else float("inf")

    return UnitResult(
        product_id=p["id"], scenario=scenario, market=p["market"], price=price,
        supplier_cost=supplier, shipping_cost=shipping, duty=duty, packaging=pack,
        paypal_fee=paypal_fee, paypal_fx_spread=fx_spread, gst_on_fees=gst,
        shopify_txn_fee=shopify_fee, refund_allowance=refund_allowance, cac=cac,
        variable_costs=variable,
        gross_margin_pct=(price - cogs) / price * 100,
        contribution_per_order=contribution,
        contribution_margin_pct=contribution / price * 100,
        breakeven_price=breakeven_price,
        breakeven_cac=cm_without_cac,
        orders_per_month=n, revenue_month=revenue, contribution_month=contribution_m,
        fixed_month=fixed_usd, operating_profit_month=operating,
        breakeven_orders_month=breakeven_orders,
        cash_needed_per_order=supplier + shipping + duty + pack,
    )


def load() -> dict:
    return json.loads(ASSUMPTIONS.read_text())


def fixed_monthly_usd(a: dict, promo: bool = False) -> float:
    f = a["fixed_monthly"]
    shop = f["shopify_promo_inr"] if promo else f["shopify_basic_inr"]
    inr = (shop * 1.18) + f["domain_inr_per_month"] + f["apps_inr"]  # 18% GST on Shopify invoice
    return inr / a["fx"]["inr_per_usd"]


def run(a: dict) -> list[UnitResult]:
    fixed = fixed_monthly_usd(a)
    out = []
    for p in a["products"]:
        for name, sc in a["scenarios"].items():
            out.append(unit_economics(p, sc, a["fees"], fixed, name))
    return out


def write_csv(rows: list[UnitResult]) -> None:
    with OUT_CSV.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(asdict(rows[0]).keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 2) if isinstance(v, float) else v) for k, v in asdict(r).items()})


def report(rows: list[UnitResult], a: dict) -> str:
    lines = [f"Fixed monthly (Shopify Basic + GST + domain): ${fixed_monthly_usd(a):.2f} "
             f"| during INR 20 promo: ${fixed_monthly_usd(a, promo=True):.2f}", ""]
    hdr = f"{'product':<12}{'scenario':<17}{'price':>7}{'var':>8}{'contrib':>9}{'CM%':>7}{'BE px':>8}{'BE CAC':>8}{'orders':>7}{'revenue':>9}{'op.profit':>10}{'BE ord':>8}"
    lines.append(hdr)
    lines.append("-" * len(hdr))
    for r in rows:
        lines.append(f"{r.product_id:<12}{r.scenario:<17}{r.price:>7.2f}{r.variable_costs:>8.2f}"
                     f"{r.contribution_per_order:>9.2f}{r.contribution_margin_pct:>6.1f}%{r.breakeven_price:>8.2f}"
                     f"{r.breakeven_cac:>8.2f}{r.orders_per_month:>7}{r.revenue_month:>9.2f}"
                     f"{r.operating_profit_month:>10.2f}{r.breakeven_orders_month:>8.1f}")
    return "\n".join(lines)


def self_test() -> None:
    fees = {"paypal_pct": 0.044, "paypal_fixed_usd": 0.30, "paypal_conversion_spread_pct": 0.03,
            "gst_on_gateway_fees_pct": 0.18, "shopify_third_party_fee_pct": 0.02}
    p = {"id": "t", "market": "US", "price_usd": 20.0, "supplier_cost_usd": 5.0, "shipping_cost_usd": 5.0,
         "duty_and_import_usd": 0.0, "packaging_insert_usd": 0.0, "refund_rate": 0.0, "return_cost_share": 0.5}
    sc = {"orders_per_month": 10, "cac_usd": 0.0, "price_multiplier": 1.0, "cost_multiplier": 1.0, "refund_multiplier": 1.0}
    r = unit_economics(p, sc, fees, 0.0, "t")
    # paypal = 0.88+0.30 = 1.18; fx = (20-1.18)*0.03 = 0.5646; gst = 0.2124; shopify = 0.40
    expected_var = 10 + 1.18 + 0.5646 + 0.2124 + 0.40
    assert abs(r.variable_costs - expected_var) < 1e-6, r.variable_costs
    assert abs(r.contribution_per_order - (20 - expected_var)) < 1e-6
    # Break-even price must yield ~zero contribution
    p2 = dict(p, price_usd=r.breakeven_price)
    r2 = unit_economics(p2, sc, fees, 0.0, "t")
    assert abs(round(r2.contribution_per_order, 1)) < 0.06, r2.contribution_per_order
    # Revenue is not profit
    assert r.revenue_month > r.contribution_month
    # Break-even CAC equals contribution before CAC
    sc_cac = dict(sc, cac_usd=r.breakeven_cac)
    r3 = unit_economics(p, sc_cac, fees, 0.0, "t")
    assert abs(r3.contribution_per_order) < 1e-6
    print("self-test: OK (4 assertions)")


if __name__ == "__main__":
    self_test()
    if "--check" in sys.argv:
        sys.exit(0)
    a = load()
    rows = run(a)
    write_csv(rows)
    print(report(rows, a))
    print(f"\nWrote {OUT_CSV.relative_to(HERE.parent)}")
