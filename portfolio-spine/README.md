# Portfolio Knowledge Spine

A public-safe read model for the portfolio's curated architecture knowledge, articles, and labs.

This folder is **not another source of truth**. It renders a derived snapshot from the authorities frozen in `PORTFOLIO_KNOWLEDGE_SYSTEM.md`:

- Architecture Vault: discovery, ingestion, retrieval, source evidence.
- Enterprise Architecture Graph: curated concepts, relationships, maturity.
- Flagship labs: implementation and verification evidence.

The UI is intentionally dependency-light so it can run as a local demo now and be embedded into the portfolio site later.

## Experience

The default view is a compact knowledge feed. Every card is designed for a roughly **two-minute read**. Opening a card shows two synchronized surfaces:

1. **Read** — problem, mental model, how it works, failure/trade-off notes, takeaway.
2. **Knowledge Lens** — graph identity, maturity, connected concepts, typed relationships, labs/evidence, and provenance.

The lens is the differentiator: a visitor can read a short explanation and immediately see how that idea connects to the rest of the engineering portfolio.

## Run the checked-in snapshot

```bash
cd portfolio-spine
python -m http.server 8080
```

Open `http://localhost:8080`.

## Rebuild from the curated Enterprise Architecture Graph

Keep a local checkout of the graph beside Architecture Vault, then run:

```bash
python engineering-knowledge-base/scripts/build_portfolio_spine.py \
  --graph-root ../enterprise-architecture-graph
```

By default this writes:

```text
portfolio-spine/data/spine.json
```

You can override the output location with `--output`.

## Read-model contract

`spine.json` contains:

- `items`: portfolio-readable articles and labs;
- `nodes`: compact graph nodes used by the lens;
- `relationships`: curated typed graph edges;
- `authorities`: where truth for each class of data lives;
- `generated_at` and `schema_version` for reproducibility.

A graph `project`/`lab` becomes a Lab card. Other curated graph nodes become Article cards. Markdown sections such as `Problem`, `Mental model`, `Reference flow`, `Failure modes`, and `Trade-offs` are compressed into the two-minute read without copying third-party article bodies.

## Publishing rule

Only curated/original graph content and public-safe implementation evidence belong in this surface. Raw captures from `engineering-knowledge-base/output` must never be exposed by this UI.

## Next integration

The same JSON contract can later be consumed by the final portfolio application. Keep the UI replaceable; keep the spine contract stable.
