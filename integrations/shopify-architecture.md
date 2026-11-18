# Shopify Architecture — PROPOSAL

## 1. Environments (₹0 path)
| Env | What | Cost |
|---|---|---|
| Local theme code | This repo `/theme`, Online Store 2.0 structure | Free |
| Development store | Shopify Partner dev store; test orders via Bogus Gateway only (S7) | Free |
| Production store | Basic plan, password-protected until launch | ₹20/mo × 3 then ₹1,994/mo (S1) — **needs approval** |

Tooling: Shopify CLI (`shopify theme dev`, `shopify theme check`) — install in Session 2; requires a Partner login by you (I cannot create accounts).

## 2. Theme architecture (Online Store 2.0)
```
theme/
  layout/theme.liquid
  templates/        index.json, product.json, collection.json, page.*.json, cart.json, 404.json, search.json
  sections/         announcement-bar, header, hero, featured-product, problem-solution, benefits,
                    demo-gallery, bundles, trust-delivery, faq, footer, main-product, main-collection, main-cart
  snippets/         product-card, price, icon, responsive-image, structured-data
  blocks/           (theme blocks where useful)
  assets/           base.css, theme.js (vanilla, no framework), cart.js
  config/           settings_schema.json, settings_data.json
  locales/          en.default.json
```
Principles: vanilla JS with progressive enhancement; Section Rendering API for cart updates; `image_url` + `image_tag` with `srcset` and lazy loading; Product JSON-LD in `snippets/structured-data`; no fake urgency components.

**Base theme decision:** build from Shopify's **Dawn**/**Horizon** reference structure vs. from scratch. Recommendation: start from Shopify's official free reference theme (MIT-licensed Dawn) and restyle — faster, accessible, maintained. Confirm in Session 2 which reference theme Shopify currently recommends.

## 3. Metafields (product)
`custom.dimensions`, `custom.materials`, `custom.care`, `custom.ship_estimate_us`, `custom.ship_estimate_au`, `custom.safety_notes`, `custom.faq` (metaobject list).

## 4. Integrations (build only when needed)
| Integration | Purpose | When |
|---|---|---|
| CJ or DSers app | Product import, order routing | After supplier verified |
| Shopify webhooks `orders/create`, `orders/paid`, `fulfillments/create`, `refunds/create` | Order-approval queue + logging | Only if Shopify Flow/admin isn't enough |
| Shopify Email (free tier) | Order notifications | Launch |
| GA4 + Search Console | Analytics/SEO | Launch |

Custom backend standards (if built): HMAC webhook verification, idempotency key = `X-Shopify-Webhook-Id`, retry with backoff on 429, pinned API version, tokens in env vars only, least-privilege scopes (`read_orders`, `read_products` until write is needed).

## 5. Out of scope
Unofficial APIs, scraping, browser automation of Shopify admin, auto-fulfilment or auto-payment without human approval.
