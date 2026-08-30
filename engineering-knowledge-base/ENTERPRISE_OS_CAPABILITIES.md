# Architecture Vault on the Enterprise OS Capability Model

Architecture Vault is a project/process running on top of the Enterprise OS model. It is **not** the Control Plane kernel.

The collector implementations in this repository are exposed as bounded **Capability Plane** primitives. Today the Vault runner can execute them locally. Later the Engineering Control Plane can discover the same manifests and own authorization, scheduling, execution-provider selection, resource policy, and cross-project run state without changing collector code.

## Boundary

```text
Enterprise OS / Control Plane
        |
        | discovers + authorizes
        v
Capability Plane
  vault.collect.web
  vault.collect.github
  vault.collect.catalog
  vault.collect.arxiv
  vault.collect.pdf
  vault.collect.youtube
  vault.collect.substack
        |
        | typed KnowledgeDocument[]
        v
Architecture Vault pipeline
  trust boundary
  normalization
  evidence fingerprints
  meaningful chunking
  source authority
  dedupe/evidence units
  deterministic concept candidates
  deterministic relation candidates
  incremental knowledge delta
        |
        v
Candidate Knowledge Spine context
  output/context/context.sqlite
        |
        | reviewed promotion only
        v
Curated Knowledge Spine / enterprise-architecture-graph
```

## Capability invariants

Every collector capability is declared in `config/capabilities.yaml` and must satisfy these rules:

- kind is `collector`;
- source types are explicitly declared;
- network and authentication requirements are declared;
- external writes are forbidden;
- collector output cannot promote or mutate canonical knowledge;
- external source text is `UNTRUSTED_EXTERNAL` and is always data, never an instruction;
- execution produces metadata/fingerprint evidence without duplicating raw third-party bodies;
- one failed source cannot erase the last good snapshot from another run.

The local `CapabilityExecutor` is deliberately small. It is not an agent runtime and it cannot choose tools or capabilities dynamically.

## Validation

From the repository root:

```bash
python engineering-knowledge-base/scripts/validate_capabilities.py --json
python engineering-knowledge-base/scripts/run_portfolio_knowledge_pipeline.py --validate-only
python -m unittest discover -s engineering-knowledge-base/tests -p "test_*.py"
```

## First safe run

Run one network collector without changing the Vault manifest/context:

```bash
python engineering-knowledge-base/scripts/run_portfolio_knowledge_pipeline.py \
  --source portfolio-enterprise-architecture-graph \
  --dry-run \
  --strict
```

The run writes only private execution evidence under:

```text
output/evidence/<run-id>/
```

## Small end-to-end ingestion run

```bash
python engineering-knowledge-base/scripts/run_portfolio_knowledge_pipeline.py \
  --source portfolio-enterprise-architecture-graph \
  --resume \
  --strict
```

Or a bounded public-source smoke run:

```bash
python engineering-knowledge-base/scripts/run_portfolio_knowledge_pipeline.py \
  --group canonical-public \
  --resume \
  --max-articles 5
```

The pipeline produces:

```text
output/
  manifest.json
  evidence/<run-id>/
  deltas/<run-id>.json
  deltas/latest.json
  state/source-state.json
  context/
    context.sqlite
    chunks.jsonl
    graph.json
    concepts.json
    relations.json
    duplicates.json
    learning-units.json
    quality-report.json
    CONTEXT_INDEX.md
```

Generated third-party evidence remains local/private and is ignored by Git.

## Incremental refresh contract

After a successful local write run, the Vault compares the previous and current manifests and emits deterministic changes:

- `ADDED`
- `CONTENT_CHANGED`
- `METADATA_CHANGED`
- `REMOVED`

The delta authority is always `CANDIDATE_ONLY`; `promotion_allowed` is false. Its purpose is to tell a downstream Knowledge Spine or Control Plane **what needs targeted re-evaluation**, not to rewrite curated knowledge automatically.

A failed source does not produce removal events because failure to observe something is not evidence that the knowledge disappeared.

## Context schema v3

`output/context/context.sqlite` now records:

- documents and meaningful chunks;
- collector capability and trust-boundary provenance;
- source authority tier and score;
- duplicate clusters and shared evidence units;
- taxonomy concepts;
- deterministic chunk-to-concept evidence links;
- deterministic statistical relation candidates;
- extractive multi-lens learning-unit candidates;
- latest knowledge deltas;
- FTS retrieval index.

Concept links are `EXTRACTED` candidates. Statistical relationships are `INFERRED` candidates. Neither becomes `VERIFIED` without the existing promotion/review requirements.

## LLM boundary

No LLM is required for collector selection, trust handling, manifest comparison, deduplication, source scoring, concept candidate matching, relation scoring, or knowledge-delta generation.

An LLM can later be introduced as a bounded reasoning capability for ambiguous semantic interpretation, but it must consume evidence/context and return a candidate result. It does not become the authority that executes collectors, writes canonical knowledge, or verifies its own output.
