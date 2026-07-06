# Gift Assistant — Evaluation

How we assessed performance, reliability, and limitations.

---

## Overview

Evaluation used **three layers**:

1. **Automated tests** — pytest unit and integration tests (mocked LLM/MCP where needed)
2. **Manual Slack end-to-end runs** — real gift flows with live APIs
3. **Operational criteria** — graceful degradation, cost control, and startup reliability

We did **not** run a formal benchmark with human raters or A/B tests. Evaluation focuses on **functional correctness, reliability, and known limitations**.

---

## Evaluation Criteria

| Dimension | What we measured |
|-----------|------------------|
| **Correctness** | Routing, parsing, scoring math, data persistence, MCP integration |
| **Pipeline behavior** | search → evaluate → rank → verify completes; only top N verified |
| **Reliability** | Graceful fallbacks when LLM/MCP fails; no crashes on bad data |
| **Slack UX** | Messages under Block Kit limits; clean price/rating display; no link spam |
| **Memory integrity** | Sessions, gift history, excluded categories, recipient handoff |
| **Config control** | Feature toggles (`EXA_ENABLED`, `AMAZON_RAINFOREST_ENABLED`, etc.) |
| **Gift quality** | Subjective — assessed manually in Slack, not scored automatically |

---

## Automated Tests

**Run:**

```bash
cd gift-assistant
PYTHONPATH=. python -m pytest tests/ -q
```

**Result:** 93 tests passing (as of last full run).

| Area | Test file(s) | What they verify |
|------|--------------|------------------|
| Gift recommender | `test_gift_recommender.py` | JSON parsing from LLM output; weighted rank (70/30); default ratings on failure |
| Product search / MCP | `test_product_search.py` | Exa query building; env toggles; verify node enriches top pick; Rainforest price dict parsing; MCP arg templates |
| Slack formatting | `test_gift_slack_format.py` | Blocks under 3000 chars; price + rating only in text; Amazon button; no raw JSON leak |
| Orchestrator routing | `test_orchestrator_routing.py` | eCard vs event disambiguation; stale session cleared on recipient change; same recipient keeps session |
| Gift sessions & history | `test_gift_session.py`, `test_gift_parser.py` | Reply parsing (1/2/3, done, feedback); SQLite save + excluded categories |
| Rainforest MCP | `test_rainforest_server.py` | Compact product shape; invalid API params omitted |
| Retail queries | `test_retail_query.py` | Amazon search uses gift title only (no noisy suffix) |
| Proactive alerts | `test_proactive_alerts.py` | Event parsing; notification store; empty/invalid JSON handled |
| Event monitor | `test_event_parser.py` | today / tomorrow / upcoming parsing |
| Profiles | `test_profile_chunker.py`, `test_profile_file_source.py` | Chunking and file import |
| eCard | `test_ecard_*.py` | Parser, render, session flow, quota fallback |
| Slack unfurl | `test_slack_unfurl.py` | `unfurl_links=false` on gift responses |

### Test approach

- Pipeline tests **mock the LLM and MCP** for fast, deterministic checks without API keys or cost.
- Scoring tests use fixed numeric inputs to validate the 70% closeness + 30% rating formula.
- Slack tests use long synthetic descriptions to confirm Block Kit limits are respected.

---

## Manual / End-to-End Examples (Slack)

Real-world scenarios exercised in Slack DMs:

| Example | Expected outcome | Result |
|---------|------------------|--------|
| `recommend gift for Mom birthday` | 3 ideas with price + rating on top pick | Works after Rainforest 400 fix and query cleanup |
| Switch recipient mid-session (Alex → Mom) | Fresh flow for Mom, not Alex | Bug found and fixed — stale session cleared |
| `/gift Mom birthday` | New session even if old one exists | Fixed — slash command clears existing session |
| Gift message with Amazon link | Button opens product; no duplicate preview below | Fixed with `unfurl_links=false` + accessory button |
| Rainforest quota exhausted | Graceful degradation, no crash | Circuit breaker + structured error JSON |
| Empty `notified_events.json` | Bot starts without crash | Fixed — store treats empty file as `{}` |
| Refinement: "something more practical" | Re-runs pipeline with feedback | Works — session feedback accumulated |
| Pick `2` | Saves to SQLite, excludes category next time | Verified via store tests + manual run |

See [SLACK_APP_SETUP.md](SLACK_APP_SETUP.md) for manual test steps.

---

## In-Pipeline Evaluation (runtime)

The system evaluates gift ideas **automatically during each request** — this is not a separate offline benchmark:

| Step | Method |
|------|--------|
| 1. LLM evaluate node | 0–100 rating per candidate with reason; penalizes excluded categories |
| 2. Embedding closeness | Cosine similarity vs Chroma profile chunks |
| 3. Weighted rank | `0.7 × closeness + 0.3 × rating` |
| 4. Retail verify | Live Amazon price/rating on top N |
| 5. Human | User picks 1/2/3 or gives feedback |

There is no labeled gift-quality dataset. Quality is judged by whether the top 3 feel plausible in manual Slack runs.

---

## Main Results

### What works well

- **93/93 automated tests pass** — core logic, routing, formatting, and MCP wiring are stable
- **Full gift pipeline runs** in Slack with Rainforest-only config (`VERIFY_TOP_N=1`)
- **Personalization path works** when profiles exist: Chroma retrieval → scoring → ranked output
- **Memory works**: selected gifts persist; excluded categories feed back into prompts
- **Slack delivery is reliable** after fixes: no `invalid_blocks`, clean price display, no unfurl spam
- **Resilience improved**: MCP circuit breaker, fallback candidates, empty store handling

### Reliability issues caught during evaluation

| Issue | Fix |
|-------|-----|
| Rainforest `400` from invalid `include_products_count=0` | Removed invalid param; return structured `api_error` |
| Rainforest `402` quota burn | Batch MCP session; circuit breaker; `VERIFY_TOP_N` |
| Stale gift session showing wrong recipient | Orchestrator clears session on recipient change |
| Raw price dict in Slack text | `normalize_display_price()` |
| Startup crash on empty notification JSON | `NotificationStore` treats empty/invalid file as `{}` |
| Slack `invalid_blocks` (3000 char limit) | One block per gift; truncation helpers |

---

## Known Limitations

| Limitation | Impact |
|------------|--------|
| No formal gift-quality benchmark | Cannot quantify "% of good recommendations" |
| LLM-dependent | Idea quality varies by provider (Ollama vs GPT); tests mock LLM |
| Sparse profiles | Weak personalization when user has not shared interests |
| Retail APIs are best-effort | Amazon search may not match abstract gift ideas (e.g. "subscription") |
| Single-user local stores | JSON/SQLite files — not multi-tenant production scale |
| No automated Slack UI tests | Block formatting tested in unit tests, not against live Slack API |
| Proactive alerts | Tested manually with `/check-alerts`; depends on calendar setup |
| Cost/latency not benchmarked | `VERIFY_TOP_N` controls cost but no formal latency SLA |

---

## Summary

> We evaluated Gift Assistant through **93 automated pytest tests** covering routing, scoring math, MCP integration, Slack formatting, session/memory behavior, and error handling — with LLM and external APIs mocked for determinism. We supplemented this with **manual Slack end-to-end runs** for gift search, refinement, recipient switching, Amazon verification, and proactive alerts. Success criteria were functional: correct pipeline execution, reliable Slack delivery, graceful API failure handling, and non-repetitive gifts when history exists. **All 93 tests pass.** Main results: the search → evaluate → rank → verify pipeline works in production-like Slack use; several real bugs were found and fixed through this process. **Limitations:** no formal human-rated gift-quality benchmark, quality depends on profile richness and LLM choice, and retail verification is best-effort for abstract gift ideas.

---

## Related docs

- [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) — architecture and component design
- [PRODUCT_SEARCH.md](PRODUCT_SEARCH.md) — MCP shopping pipeline setup
- [SLACK_APP_SETUP.md](SLACK_APP_SETUP.md) — manual Slack testing steps
