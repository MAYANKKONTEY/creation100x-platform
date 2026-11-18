# Profit Calculator

Run: `python3 finance/calculator.py` → prints report, writes `finance/unit-economics.csv`, runs self-tests.
Edit inputs in `finance/assumptions.json`. Every input carries a `status` field — values marked **UNVERIFIED** must be replaced with quotes before launch.

## Formulas (as implemented)
```
COGS               = supplier + shipping + duty + packaging
PayPal fee         = price × 4.4% + $0.30                         (S3)
FX spread          = (price − PayPal fee) × 3.0%                  (S3: converting balance to INR)
GST on fees        = PayPal fee × 18%                             (Indian GST on gateway service – CA to confirm recoverability)
Shopify txn fee    = price × 2%                                   (S1: Basic plan, third-party gateway)
Refund allowance   = refund_rate × (price × return_cost_share + COGS × 50%)
Variable costs     = COGS + all fees + refund allowance + CAC
Contribution/order = price − variable costs
Contribution margin= contribution ÷ price
Gross margin       = (price − COGS) ÷ price
Revenue/month      = price × orders
Operating profit   = contribution × orders − fixed monthly costs
Break-even price   = price at which contribution = 0 (solved algebraically)
Break-even CAC     = contribution before CAC
Break-even orders  = fixed monthly ÷ contribution per order
```

## Base-case results (2026-11-18, UNVERIFIED supplier costs)
| Product | Price | Variable | Contribution | CM % | Break-even price | Max CAC |
|---|---|---|---|---|---|---|
| Lick mat bundle (US) | $22.00 | $14.18 | **$7.82** | 35.6% | $13.05 | $7.82 |
| Tech pouch (AU) | $24.00 | $15.12 | **$8.88** | 37.0% | $13.78 | $8.88 |
| Gym mount (US) | $29.00 | $18.25 | **$10.75** | 37.1% | $16.50 | $10.75 |

Fixed monthly: **$28.16** (Shopify Basic ₹1,994 + 18% GST + domain) — **$1.69** during the ₹20 promo months.

## What the numbers say
- **Organic-only is mandatory.** At a $12 CAC every product goes negative (`paid_ads_stress` rows). Paid ads are not viable until AOV rises (bundles, upsells) or costs fall.
- **Conservative case** (−10% price, +25% costs, 2× refunds) cuts contribution to ~$2.4–3.2/order. Costs must be verified before pricing is locked.
- **Fees ≈ 11–12% of price** (PayPal 4.4% + $0.30, FX 3%, GST on fees, Shopify 2%). Moving to Grow plan (1%) costs ₹5,453/month more, so it only pays off above ~₹5.45 lakh (~$6,200) monthly revenue — not relevant at launch.
- Revenue is never profit: base-case lick mat at 20 orders = $440 revenue → **$128 operating profit**.
