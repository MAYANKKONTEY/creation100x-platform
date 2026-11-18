# CLAUDE.md — Project rules

Global Shopify dropshipping business, Indian founder, ₹0 starting budget, organic acquisition.

## Non-negotiables
- Evidence before assumptions: every factual claim cites `research/sources.md` with date. Never invent statistics, reviews, testimonials, supplier verifications or test results.
- Never spend money, create accounts, contact suppliers, place orders, publish the store, connect live payments, change live prices, issue refunds or process customer PII without explicit founder approval.
- No fake urgency, fake scarcity, fake reviews, fake trust badges or medical/behavioural claims.
- No credentials in Git. Use `.env` (gitignored); template in `.env.example`.
- No unofficial Shopify APIs or admin automation.
- Revenue ≠ profit. All financials go through `finance/calculator.py`.

## Current state
- Phase 1 research complete (Session 1). Recommended product: dog lick-mat bundle. **Awaiting founder approval** of niche + name before storefront build.
- Launch markets: US (US-warehouse SKUs) + Australia. UK/EU/CA blocked by VAT/duty rules.

## Commands
- `python3 finance/calculator.py` — unit economics + self-tests; writes `finance/unit-economics.csv`.

## Layout
research · brand · theme · suppliers · finance · marketing · seo · integrations · operations · support · analytics · compliance · testing · docs
