# Market Research — Session 1 (2026-11-18)

Source IDs (S#, T#, P#) refer to `research/sources.md`.

## 1. Executive summary
- **The product question is secondary to two structural constraints**: (a) cross-border tax/customs changes in 2025–2026, and (b) payment-gateway access for an Indian founder. Both shape which markets and products are viable at ₹0.
- **US**: duty-free de minimis is gone for all origins (T1). China-to-US direct parcels now carry ad-valorem duty plus brokerage friction. Viable route: products **already stocked in US warehouses** (CJ US warehouse or similar), where the importer of record paid duty on bulk stock. Must be confirmed per SKU.
- **UK**: overseas sellers shipping ≤£135 direct to consumers must register for UK VAT from the first sale (T4). **Exclude UK at launch.**
- **EU**: €3 duty per item from 1 July 2026 plus import VAT; IOSS needs an EU intermediary for non-EU sellers (cost). **Exclude EU at launch.**
- **Australia**: no GST registration obligation for overseas vendors under A$75k turnover (T5). **Viable secondary market** for China-direct shipping.
- **Canada**: CA$20 threshold for non-US/Mexico origin (T6) → customers likely pay tax + broker fees on delivery. **Exclude at launch** unless shipped from US warehouse in CUSMA commerce (confirm).
- **Payments**: Shopify Payments unavailable in India (S2). PayPal India works for export receipts but costs ~4.4% + $0.30 + 3% FX + 18% GST on fees + Shopify 2% (S1, S3). Razorpay may decline dropshipping (S6, single report). **Payment approval is the #1 launch risk.**

**Recommended launch geography:** US (US-warehouse SKUs only) first, Australia second. Re-evaluate UK/EU/CA once revenue justifies VAT/IOSS registration.

## 2. Product selection criteria applied
Light (<300 g packed), non-electrical, no batteries, no strong-claim categories (medical, supplements, cosmetics, children's toys), demonstrable in <30 s video, low defect surface (few moving parts), not patent-encumbered, price headroom ≥3× landed cost.

## 3. Category scan (10 categories required)
| Category | Representative products examined | Verdict |
|---|---|---|
| 1. Creator workspace | Magnetic gym/creator phone mount (P9) | Shortlist |
| 2. Desk organisation | Under-desk cable tray (P10), cable clips | Tray: weight & adhesive-failure risk; clips: low ticket |
| 3. Home improvement accessories | Adhesive hooks, drain catchers | Low ticket, commoditised |
| 4. Travel organisation | Tech pouch (P8), packing cubes (P11), silicone bottles (P12) | Tech pouch shortlisted; cubes saturated; bottles leak-return risk |
| 5. Pet accessories | Lick mat (P1–P5), paw cleaner (P6), pet hair roller (P7), snuffle mat | Lick mat lead; paw cleaner bulky; hair roller **patent risk – rejected** |
| 6. Lifestyle | Gym mount (overlaps 1) | — |
| 7. Non-electrical productivity | Desk pegboard, monitor shelf | Heavy/bulky → shipping kills margin |
| 8. Personal organisation | Tech pouch (overlaps 4) | — |
| 9. Hobby & creative | Brush organisers, craft storage | Weak evidence gathered; not pursued this session |
| 10. Emerging | Pet enrichment as a "routine" category (AKC, trainers promoting cooperative-care grooming) (P4) | Supports pet-enrichment niche |

## 4. Demand evidence (what we actually have)
| Product | Evidence type | Strength |
|---|---|---|
| Lick mat | 17,248 reviews on one LickiMat 2-pack listing; stocked by Chewy, Walmart, Target; AKC editorial | **Strong** category demand; weak price power |
| Paw cleaner | 61,281 ratings on MudBuster Amazon listing | Strong demand, dominated by one brand |
| Tech pouch | Many buying guides; brands from $15 to $60 | Strong, crowded |
| Gym mount | A2C 393 ratings; multiple brands at $15–42 | Moderate, growing niche |
| Under-desk tray | ~6,500 ratings on leading adhesive tray | Moderate–strong |

**Not yet measured** (blocked): search volume, Google Trends direction, TikTok/IG hashtag volume. These must be collected manually before committing (≈30 min task, free) — see §5.

## 5. Manual validation tasks for you (free)
1. Google Trends (worldwide + US + AU, past 5 yrs): `lick mat`, `dog lick mat`, `tech pouch`, `magsafe gym mount`. Screenshot and save to `research/evidence/`.
2. TikTok + Instagram search: note top-10 view counts for `#lickmat`, `#dogenrichment`, `#techpouch`, `#gymmount`.
3. Reddit: search r/dogs, r/DogTraining, r/puppy101 for "lick mat"; record 10 recurring complaints verbatim with URLs.
4. Log in to CJdropshipping (free account) and record: SKU, price, US-warehouse stock, CJPacket/US shipping quote to ZIP 10001 and to Sydney 2000.

## 6. Strategic conclusion
Build a **dog-enrichment & calm-grooming brand**, launching with a lick-mat bundle sold from US warehouse stock, with an Australian China-direct option. Keep tech pouch and gym mount as alternate test candidates. Full scoring in `niche-scorecard.csv`, reasoning in `product-opportunities.md`.
