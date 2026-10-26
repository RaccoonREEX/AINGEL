# Privacy architecture — decision record

2026-10-26: choose Standard model IDs and keep credentials server-side. [Meta pricing](https://dev.meta.ai/docs/pricing-rate-limits) says Standard content is not used for training. The authenticated [billing UI](https://dev.meta.ai/billing) separately warns of product-improvement use with active free credits. Scope of the latter has not been reconciled with Standard terms. No account privacy/billing settings were changed.

Decision: initial live tests use known synthetic fixtures only. The server enforces a request assertion plus a configuration gate; this is not automated sensitive-content detection. Personal-data enablement requires resolving credit terms, retention, geographic policy and appropriate consent. `store=false` requests no Responses conversation storage; it is not proof of ZDR or a waiver of account terms.

Implemented: fixed Meta host, no redirects, bounded image processing, no image persistence, no raw provider-error forwarding and authenticated access. Planned: HTTPS, stable secrets, production database/storage, per-owner evidence permissions, Care grants, access auditing, retention worker, backup policy and deletion semantics. Those planned controls are release gates, not present guarantees.
