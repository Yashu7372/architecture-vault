# Hands-on Angular Projects

Reading should produce working evidence. Each project below adds one layer of complexity and includes acceptance criteria.

## Project 1 — Accessible frontend shell

Build without Angular first.

Features:

- responsive header, navigation, main content, and footer;
- keyboard-accessible mobile navigation;
- accessible form with validation summary;
- dark/light preference;
- reduced-motion handling;
- table that remains usable on narrow screens.

Evidence:

- semantic HTML audit;
- keyboard-only recording;
- performance trace;
- explanation of layout and event propagation.

## Project 2 — JavaScript utility library

Implement and test:

- debounce and throttle;
- memoize-one;
- deep-path safe getter;
- retry with exponential backoff and jitter;
- async concurrency limiter;
- event emitter with unsubscribe;
- immutable update helpers;
- LRU cache.

Explain time/space complexity and memory behavior.

## Project 3 — TypeScript domain model

Create a small order domain with:

- branded IDs;
- money/value objects;
- discriminated workflow states;
- command and event types;
- DTO validation/mapping;
- generic pagination and result types;
- exhaustive reducer;
- strict compiler flags.

No `any`, unsafe non-null assertions, or direct DTO use in UI models.

## Project 4 — Angular CRUD foundation

Build a customer portal:

- standalone application;
- lazy customer feature;
- list/detail/create/edit routes;
- typed reactive forms;
- HTTP adapter and DTO mapping;
- loading, empty, error, and retry states;
- route guard for unsaved changes;
- signal-based local/feature state;
- unit, component, router, and HTTP tests.

## Project 5 — Search and server-state behavior

Add:

- query parameter-backed search, filters, sort, pagination;
- debounced search with `switchMap` cancellation;
- request deduplication;
- explicit cache key and stale policy;
- retry only for eligible failures;
- optimistic update with rollback;
- conflict error handling;
- offline/slow-network presentation.

Document why each RxJS flattening operator was selected.

## Project 6 — Complex dynamic form

Build an onboarding workflow:

- multiple steps;
- conditional sections;
- nested arrays/groups;
- reusable custom controls;
- synchronous, cross-field, and asynchronous validation;
- autosave draft;
- server validation mapping;
- unsaved-change protection;
- keyboard and screen-reader behavior;
- restore from draft with schema version migration.

Create a state-machine diagram for valid transitions.

## Project 7 — Real-time operations dashboard

Build a dashboard using mock SSE/websocket data:

- initial snapshot;
- versioned delta updates;
- reconnect with backoff;
- event de-duplication;
- gap detection and snapshot refresh;
- connection status;
- route-scoped subscriptions;
- large list optimization;
- attention/critical thresholds;
- observable telemetry.

Test out-of-order, duplicate, missing, and delayed events.

## Project 8 — Design system

Create a reusable library with:

- tokens and themes;
- button, input, select, checkbox, dialog, tabs, table, toast;
- accessible keyboard/focus contracts;
- typed APIs;
- component harnesses;
- documentation/examples;
- visual regression states;
- RTL and long-text cases;
- migration/versioning notes.

Do not include business-specific components.

## Project 9 — SSR content application

Build a content/catalog application with:

- SSR;
- hydration;
- prerendered static routes;
- browser-only API abstraction;
- route metadata and SEO;
- deferred below-the-fold content;
- caching strategy;
- hydration mismatch tests;
- web-vitals comparison against CSR baseline.

Document whether SSR materially improved the target scenario.

## Project 10 — Enterprise reference portal

Combine:

- authenticated shell;
- application and route-scoped providers;
- customers, orders, reports, administration features;
- permission policy;
- runtime configuration;
- design system;
- API and real-time adapters;
- correlation IDs and telemetry;
- feature flags;
- CI quality gates;
- production deployment configuration.

Required documentation:

- system context and container diagrams;
- dependency rules;
- state ownership matrix;
- route map;
- error taxonomy;
- threat model;
- accessibility checklist;
- observability plan;
- ADRs for major choices;
- migration and rollback plan.

## Capstone acceptance criteria

### Architecture

- feature internals are not imported externally;
- root providers contain only application infrastructure;
- temporary state is route/component scoped;
- DTOs are mapped at boundaries;
- URL holds shareable view state;
- no circular dependencies.

### Functionality

- critical workflows cover loading, empty, success, error, retry, and conflict;
- duplicate submission is prevented;
- real-time updates reconcile correctly;
- authentication expiry is handled;
- permission UX matches backend behavior.

### Quality

- strict build passes;
- relevant unit/component/integration/E2E tests pass;
- architecture rules pass;
- accessibility checks and manual keyboard flow pass;
- bundle budgets pass;
- no repeated-navigation memory growth;
- telemetry correlates frontend actions with backend requests.

## Review template for every project

```markdown
# Project Review

## Problem and users
## Functional scope
## Architecture and boundaries
## State ownership
## Data and API contracts
## Reactive/concurrency decisions
## Failure handling
## Security and privacy
## Accessibility
## Performance measurements
## Testing evidence
## Deployment and observability
## Trade-offs
## What I would change at larger scale
```

## Portfolio presentation

For each major project, prepare a five-minute explanation:

1. problem and constraints;
2. architecture diagram;
3. hardest technical decision;
4. failure/performance issue found;
5. measurement and result;
6. trade-off and future improvement.

This is stronger interview evidence than listing Angular APIs.
