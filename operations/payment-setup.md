# Payment Setup Guide — Indian founder selling internationally

Status: **research only. No account has been created, applied for, or connected.**

## 1. Options compared (2026-11-18)
| Gateway | Available to Indian merchant on Shopify? | Cost to you | Dropshipping acceptance | Notes |
|---|---|---|---|---|
| **Shopify Payments** | **No** — India not a supported country (S2) | — | — | Ruled out. Do not use a foreign address to obtain it. |
| **PayPal (India business)** | Yes | 4.4% + $0.30 per receipt, 3% FX spread to INR, 18% GST on fees, + Shopify 2% (S1, S3) | Not explicitly excluded in sources found; account limitation risk for new sellers is widely reported but **unquantified** | Best realistic first gateway. Needs PAN, matching bank account, purpose code, and a KYC business document (S4). |
| **Razorpay International** | Yes, on request after domestic KYC (S5) | Not verified this session | **One merchant report of rejection for dropshipping** (S6) | Ask Razorpay in writing *before* applying. |
| Others (Cashfree, PayU, Stripe India) | Not researched this session | — | Cashfree reportedly declines dropshippers (S6, anecdotal) | Session 2. Stripe India is invite-only per prior knowledge — **unverified**, do not rely on it. |

## 2. Recommended path
1. **Free KYC document:** register on Udyam (free, Govt. of India MSME portal) as a sole proprietor → satisfies PayPal's sole-proprietor document list (S4).
2. **Ask a CA (see `compliance/professional-review-questions.md`)** which PayPal purpose code applies to dropshipped goods that never enter India, and whether an IEC is required. Do not pick a code yourself — a wrong code mis-declares the foreign-exchange purpose.
3. Open **PayPal Business (India)** with your real name, address, PAN, and an Indian bank account in the same name.
4. Write to Razorpay support with an honest description ("Shopify store, products shipped by third-party suppliers from China/US warehouses directly to overseas customers") and ask whether international card payments can be enabled. Keep the reply on file.
5. Connect the gateway to Shopify **only after founder approval and only on a paid plan**. Keep the store password-protected until launch.

## 3. Requirements checklist
- [ ] PAN (individual)
- [ ] Indian bank account in same name as PAN
- [ ] Udyam certificate (or GSTIN / IEC / shop licence)
- [ ] Purpose code confirmed by CA
- [ ] IEC — only if CA says goods-export code applies
- [ ] Published policies: refund, shipping (incl. international terms), privacy, terms, contact with real address (Razorpay compliance review requires these — S5)
- [ ] Store domain/business name consistent across PayPal, Shopify, bank

## 4. Chargebacks, refunds, payouts
- Refund through PayPal returns the variable fee? **Unverified** — model assumes fees are lost.
- Chargebacks: PayPal seller protection requires tracked delivery to the address on the transaction. Always use tracked shipping.
- Payout: PayPal → Indian bank requires the purpose code; conversion at PayPal's rate + 3%. Holds/reserves possible for new sellers — keep a float (see `finance/cashflow-model.md`).

## 5. Never
Fake addresses · someone else's account · foreign entity without real presence to unlock Shopify Payments · bypassing KYC · going live without approval.
