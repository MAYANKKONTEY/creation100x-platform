# Session 1 Report — 2026-11-18

## Completed
- Repository inspected (README only; no prior instructions or code).
- Phase 1 research: 10 categories scanned, 10 products scored, 3 test candidates, 1 recommendation.
- Supplier landscape + outreach drafts (nothing sent).
- Unit-economics calculator with self-tests and 4 scenarios × 3 products.
- Payment, tax, customs and compliance research for an Indian founder.
- Brand and Shopify architecture proposals.

## Key findings
1. **Recommended product:** dog lick-mat bundle (2 textures + spatula + routine card), $22, US-warehouse fulfilment. Score 78/100. Base contribution **$7.82/order (35.6%)** on unverified costs.
2. **Markets:** US (US-warehouse stock only) + Australia. UK, EU and Canada blocked at launch by VAT registration / duty rules.
3. **Payments:** Shopify Payments not available in India. PayPal is the realistic first gateway (~11–12% all-in fees). Razorpay may refuse dropshipping.
4. **Paid ads are not viable** at these margins (−$4.18/order at $12 CAC). Organic only.
5. **₹0 is not achievable.** Floor ≈ ₹71 (Shopify promo) + sample (~₹1.5–3k, estimate) + recommended ~₹10k float.

## Tests performed
- `python3 finance/calculator.py` — 4 self-test assertions pass (fee arithmetic, break-even price, break-even CAC, revenue > contribution).
- Scorecard totals verified programmatically (all 10 rows).
- No storefront tests (nothing built yet).

## Problems discovered
See `testing/known-issues.md` (K1–K8).

## Costs required (none incurred)
| Item | Cost | Approval needed |
|---|---|---|
| Shopify (after 3-day trial) | ₹20/mo × 3, then ₹1,994/mo + 18% GST | Yes |
| Product sample | ~₹1,500–3,000 (estimate) | Yes |
| Domain (optional at launch) | ~USD 17 first year | Yes |
| IEC (if CA requires) | ~₹500 (verify) | Yes |
| CA consultation | Unknown | Yes |

## Pending approvals
1. Approve **dog enrichment / lick-mat** as the niche (or pick tech pouch / gym mount).
2. Approve launch markets US + Australia.
3. Approve a new brand-name round (current candidates have conflicts).
4. Approve contacting CJ / AliExpress sellers with the drafted messages.
5. Approve sample purchase budget.

## Next three actions
1. **You (30–60 min, free):** create a free CJdropshipping account, record lick-mat SKU prices, US-warehouse stock and shipping quotes; do the Trends/Reddit/TikTok checks in `research/market-research.md` §5.
2. **Me (Session 2):** with those numbers, update `finance/assumptions.json`, finalise competitor storefront teardown, run a 15-name brand round with domain + TM screening.
3. **Me (Session 2, after approval):** scaffold the OS 2.0 theme in `/theme` and run `shopify theme check` on a free development store.
