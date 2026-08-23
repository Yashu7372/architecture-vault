# Portfolio Knowledge System — Canonical Context

## Purpose

This document freezes how the portfolio learning, knowledge, implementation, evidence, and publishing systems connect.

The portfolio is not a collection of disconnected tutorials or scraped articles. It is a **learning-to-evidence system** for enterprise architecture and AI engineering:

```text
Discover credible engineering knowledge
  -> understand and connect it
  -> turn it into a curated architecture graph
  -> apply it in production-shaped flagship systems
  -> verify the implementation with evidence
  -> publish original explanations, diagrams, articles, and project stories
```

## Repository responsibilities

### 1. Architecture Vault — discovery and retrieval knowledge layer

Repository: `Yashu7372/architecture-vault`

Owns:

- external source registry;
- collectors/scrapers;
- bookmark/catalog import;
- Substack/public-course collection boundaries;
- normalized notes and metadata;
- deduplication and indexes;
- retrieval chunks and SQLite FTS context;
- lightweight source/document/tag/reference relationships;
- day-by-day learning material generation;
- bounded context packs for research and AI-assisted work.

Architecture Vault answers:

> What should I read, what does the source contain, how do I retrieve the relevant parts, and what source evidence is available for this topic?

It is an **intake/research layer**, not the final public knowledge graph.

### 2. Enterprise Architecture Graph — curated semantic knowledge layer

Repository: `Yashu7372/enterprise-architecture-graph`

Owns:

- canonical architecture concepts;
- problems and failure modes;
- patterns and trade-offs;
- typed relationships;
- architecture nodes;
- role-oriented learning paths;
- Chronicle and Forge reference architectures;
- the 69-day public build journey;
- maturity progression from discovered knowledge to mastered/published evidence.

The graph answers:

> What do I now understand, how does it relate to other architecture knowledge, where is it used, and what evidence proves that understanding?

Only curated/original knowledge should be promoted from Architecture Vault into this graph.

### 3. Flagship implementation repositories — executable proof

Primary current repository: `Yashu7372/engineering-control-plane`

This is the implementation/evidence side of the portfolio. Its Knowledge Spine, Agent Runtime, Capability Plane, Evidence Plane, verification loop, and governed engineering workflows are not replacements for Architecture Vault.

Architecture Vault gathers external engineering knowledge. The Engineering Control Plane gathers and reasons over **application/repository/runtime engineering knowledge** while performing real engineering work.

The two systems therefore complement one another:

```text
Architecture Vault
  external engineering knowledge
          |
          v
Enterprise Architecture Graph
  curated architecture understanding
          |
          v
Engineering Control Plane / other flagship labs
  implementation + verification + evidence
          |
          v
Enterprise Architecture Graph
  maturity/evidence links updated
```

### 4. Portfolio publishing — original public output

Publishing consumes only:

- curated graph nodes and relationships;
- original learning notes;
- architecture decisions;
- diagrams generated from our models;
- implementation excerpts that are safe to publish;
- tests, benchmarks, failure experiments, and verification evidence;
- project milestones and lessons learned.

Publishing must not directly copy raw third-party article captures from `engineering-knowledge-base/output`.

Typical downstream outputs are:

- portfolio-site project pages;
- GitHub architecture articles;
- LinkedIn posts/articles;
- diagrams and visual explainers;
- interview-ready explanations;
- the 69-day learning/build series.

## Canonical flow

```text
Sources
  |
  |-- engineering blogs
  |-- white papers / PDFs
  |-- GitHub repositories
  |-- Substack/public curricula
  |-- arXiv
  |-- YouTube metadata/transcripts
  |-- Chrome bookmarks
  v
ARCHITECTURE VAULT
  collectors
  -> normalized KnowledgeDocument
  -> manifest + indexes
  -> retrieval chunks
  -> context.sqlite / FTS
  -> lightweight source graph
  -> bounded context packs
  -> course/learning builders
  |
  |  human/AI curation; never blind promotion
  v
ENTERPRISE ARCHITECTURE GRAPH
  concepts
  <-> problems
  <-> patterns
  <-> failures
  <-> architectures
  <-> labs/projects
  <-> evidence
  |
  v
FLAGSHIP SYSTEMS
  Chronicle / Forge / Engineering Control Plane / future labs
  |
  -> source code
  -> ADRs
  -> tests
  -> failure scenarios
  -> benchmarks
  -> screenshots/traces
  -> verification evidence
  |
  v
PORTFOLIO CONTENT
  original articles + visuals + project stories + LinkedIn + site
```

## Knowledge maturity rule

External information is never automatically treated as mastered knowledge.

```text
DISCOVERED
  -> INGESTED
  -> RETRIEVABLE
  -> REVIEWED
  -> CURATED
  -> IMPLEMENTED
  -> VERIFIED
  -> PUBLISHED
  -> MASTERED
```

Architecture Vault primarily owns `DISCOVERED -> RETRIEVABLE` and learning support.

Enterprise Architecture Graph owns curated semantic status and cross-topic relationships.

Flagship repositories own `IMPLEMENTED -> VERIFIED` evidence.

Portfolio publishing owns the public explanation, but publication alone does not imply implementation maturity.

## Source tiers

### Tier A — primary/authoritative

- official engineering blogs;
- vendor/platform documentation;
- research papers;
- original project repositories;
- white papers and architecture publications.

### Tier B — strong curated engineering references

- respected engineering catalogs;
- high-quality open-source repositories;
- practitioner publications with clear technical depth.

### Tier C — discovery only

- social posts;
- aggregators;
- general videos/articles without strong primary evidence.

Tier C can create a discovery lead, but important portfolio claims should be grounded in Tier A/B evidence or our own implementation evidence.

## Branch consolidation decision

Canonical integration branch:

`feature/portfolio-knowledge-source-of-truth`

It is based on the most complete SDCourse/collector line and incorporates the collector hardening and first-25 learning work.

Historical branches remain useful for history only:

- `feature/substack-system-design-course-context` — initial Substack/context integration;
- `feature/sdcourse-daily-learning-builder` — daily scheduler/course builder line;
- `feature/sdcourse-learning` — experimental course configuration line;
- `feature/sdcourse-first-25-lessons` — first-25 hardening/review-pack line and canonical branch base;
- `feature/system-design-academy-context-layer` — academy/context integration line.

From now on, new work for this path should target the canonical branch rather than extending those branches independently.

## Canonical source registry

External sources remain in:

- `engineering-knowledge-base/config/sources.manual.yaml`
- `engineering-knowledge-base/config/sources.generated.yaml`

Logical execution groups live in:

- `engineering-knowledge-base/config/source-groups.yaml`

The groups separate routine safe/public refreshes from authenticated/manual sources and make the pipeline reproducible.

## Canonical execution

Full public portfolio knowledge build:

```bash
python engineering-knowledge-base/scripts/run_portfolio_knowledge_pipeline.py --group canonical-public --resume
```

List groups:

```bash
python engineering-knowledge-base/scripts/run_portfolio_knowledge_pipeline.py --list-groups
```

Focused collection remains available through `scripts/collect.py` and the specialized course/catalog scripts.

## Automation rule

GitHub Actions may schedule public-source collection and validation, but raw captures are never committed. Generated runtime knowledge remains in ignored/private output or cache storage and can be rebuilt from the source registry.

Authenticated/paywalled sources must not be scraped by a public scheduled job. Public-course collectors must preserve the existing public/preview/curriculum-only boundaries.

## Promotion contract: Vault -> Architecture Graph

A source becomes a graph candidate only after review. A promoted item should contain:

- concept/problem/pattern name;
- original summary in our own words;
- why it matters;
- trade-offs/failure modes;
- related graph node IDs;
- source URLs/provenance;
- confidence/maturity;
- where it can be demonstrated in a lab or flagship project.

No raw article body should be copied into the public graph.

## Evidence contract: Flagship project -> Portfolio

A portfolio claim should ideally point to one or more of:

- implementation commit/file;
- architecture decision record;
- executable test;
- failure/recovery scenario;
- benchmark/performance result;
- verification report;
- screenshot/trace/log;
- graph node or architecture relationship.

This is what turns the portfolio from content creation into evidence-backed engineering work.

## Final source-of-truth rule

For this path:

- **Architecture Vault canonical branch** = source registry + ingestion/retrieval/learning implementation.
- **Enterprise Architecture Graph main branch** = curated portfolio knowledge and architecture relationships.
- **Flagship repository main/approved feature branches** = executable implementation evidence.
- **Publishing layer** = derived original content, never an independent knowledge authority.

When there is a conflict, prefer curated graph facts and verified implementation evidence over generated summaries or raw scraped text.
