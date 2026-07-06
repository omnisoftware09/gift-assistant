# Gift Assistant — Demo Slide Copy

Copy-paste into Google Slides. One section = one slide.

---

## Slide 1 — Title

**Gift Assistant**
*Slack-native AI gift concierge*

LangGraph · ChromaDB · MCP · Multi-agent

---

## Slide 2 — What it does

**What it does**

- Finds **personalized gifts** from stored interests + occasion
- **Remembers** past selections — won't suggest repeats
- **Verifies** top picks with live Amazon price + ★ rating
- **Nudges you** before birthdays & graduations (Google Calendar)
- **Refines** in one reply — "something more practical"

---

## Slide 3 — How it works (flow)

**How it works**

```
You ask in Slack
    → Profile + history loaded
    → Ideas generated (LLM)
    → Scored & ranked (embeddings + LLM)
    → Top picks verified (Amazon MCP)
    → You refine or choose
```

**4 agents, 1 orchestrator:** Gift · Profile · Calendar · eCard

---

## Slide 4 — Success & boundaries

**Success looks like**

| Users | System |
|-------|--------|
| Personal, not generic | Pipeline completes reliably |
| No repeat gifts | Real price + rating on top pick |
| One-reply refinement works | Sessions stay coherent |

**Boundaries we set**

- Fixed pipeline — not open-ended agent (predictable, lower cost)
- Suggests only — no checkout
- Shopping APIs optional & toggleable
- Verify top N only — quota control
- Human picks the gift — system proposes

---

## Slide 5 — Tech stack

**Tech stack**

| Layer | Tech |
|-------|------|
| Interface | Slack Bolt, Block Kit |
| Pipeline | LangGraph: search → evaluate → rank → verify |
| Memory | ChromaDB + SQLite + JSON sessions |
| Tools | MCP: Exa, Rainforest, SerpApi |
| LLM | OpenAI / Anthropic / Ollama |
| Observability | Logging + LangSmith |

---

## Slide 6 — Architecture (use image)

**System architecture**

Insert: `docs/architecture-diagram.svg`

*(File → Import → Upload → select architecture-diagram.svg)*

---

## Speaker notes (30 seconds)

> Gift Assistant is a Slack bot that helps you find personalized gifts. It remembers who people are through Chroma profiles and SQLite gift history, runs a fixed LangGraph pipeline to generate and score ideas, then verifies the top pick on Amazon for real price and ratings. It also reads your Google Calendar and nudges you before birthdays. We kept it bounded — fixed pipeline, no purchasing, optional APIs, and the user always makes the final choice.

---

## Speaker notes (2 minutes)

> **Problem:** Finding gifts is hard — you forget what you gave before, don't know what they'd like, and web search gives generic lists.
>
> **Solution:** Gift Assistant in Slack. You say "recommend gift for Mom's birthday."
>
> **Step 1 — Retrieve:** ChromaDB pulls Mom's interest profile. SQLite loads past gifts so we don't repeat categories.
>
> **Step 2 — Reason:** LangGraph pipeline — search node generates 5 ideas, evaluate node scores each 0–100, rank node combines embedding closeness with LLM rating.
>
> **Step 3 — Verify:** Rainforest MCP checks Amazon for live price and star rating on the top pick.
>
> **Step 4 — Human:** You see three options in Slack with price and rating. Pick 1/2/3, give feedback, or say done. Your choice saves to history.
>
> **Proactive:** Background worker scans calendar, DMs you 3 days before Sarah's birthday with a "Search gifts" button.
>
> **Boundaries:** Fixed pipeline not open ReAct. No checkout. APIs toggleable. User always decides.
