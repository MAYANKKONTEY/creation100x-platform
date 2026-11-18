# Cash-Flow Model

## The core problem at ₹0
Dropshipping still requires **paying the supplier before the customer's money is withdrawable**.

```
Day 0   Customer pays $22 via PayPal → sits in PayPal balance (may be held/reserved for new accounts)
Day 0-1 You must pay CJ ~$10.80 (product + shipping + insert) by card/PayPal BEFORE they ship
Day 3+  Withdraw to Indian bank (needs purpose code; INR conversion at PayPal rate + 3% spread)
```
Can supplier payment come from the PayPal balance? CJ accepts PayPal (per CJ's payment options — **verify**). If yes, the order is self-funding **unless PayPal places a hold**. New PayPal sellers commonly see holds (up to 21 days reported anecdotally — **unverified**). Plan for it.

## Minimum cash required before first sale (INR, approx.)
| Item | Cost | Avoidable? |
|---|---|---|
| Shopify 3-day trial | ₹0 | — |
| Shopify months 1–3 (₹20 × 3 + 18% GST) | ~₹71 | No (needed to sell) |
| Shopify month 4+ Basic | ₹1,994 + GST ≈ ₹2,353/mo | No, once live |
| Domain (.com first year) | ~USD 17 (≈₹1,500) | **Yes** — launch on `*.myshopify.com` first |
| Sample(s): 1 bundle shipped to India | ~₹1,500–3,000 incl. import duty (**estimate**) | Strongly not recommended to skip |
| Udyam registration (KYC doc for PayPal) | ₹0 | — |
| IEC (if required for goods export purpose code) | ₹500 DGFT fee (**verify**) | Depends on CA advice |
| Float for 10 orders if PayPal holds funds | 10 × $10.80 ≈ ₹9,500 | Risk buffer |
| **Minimum realistic start** | **≈ ₹3,000–5,000 + ₹9,500 float buffer** | |

**Conclusion:** a strict ₹0 start is not possible. The unavoidable floor is ~₹71 for Shopify promo months plus a sample. A float of ~₹10k is needed to survive payout holds without cancelling orders.

## 90-day plan (base case, 20 orders/month from month 2)
| Month | Orders | Revenue | Contribution | Fixed | Operating profit | Cash low-point risk |
|---|---|---|---|---|---|---|
| 1 (build, promo) | 0 | $0 | $0 | $1.69 | −$1.69 | Sample cost |
| 2 (promo) | 5 | $110 | $39 | $1.69 | $37 | PayPal hold |
| 3 (promo) | 20 | $440 | $156 | $1.69 | $155 | PayPal hold |
| 4 (Basic) | 20 | $440 | $156 | $28.16 | $128 | — |
These are **scenarios, not forecasts**. Order volume from organic content is unknown until tested.

## Refund exposure
At 5% refund rate and 20 orders/month: ~1 refund/month ≈ $11–22 at risk (PayPal does not return its fixed fee on refunds).

## Supplier payment requirement
Prepaid per order. Never auto-pay: each order needs human approval (see `operations/order-workflow.md`, Session 2).
