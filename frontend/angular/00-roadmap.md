# Angular Learning Roadmap

## Goal

Move from web fundamentals to production Angular engineering without memorizing framework APIs in isolation.

## Phase 1 — Browser and frontend foundations

Study:

- URL, DNS, TCP/TLS, HTTP, caching, cookies, CORS;
- HTML semantics, forms, DOM tree, events, event propagation;
- CSS cascade, specificity, box model, layout, stacking contexts, responsive design;
- browser parsing, style calculation, layout, paint, compositing;
- accessibility tree, keyboard navigation, ARIA, focus management;
- DevTools: Elements, Network, Performance, Memory, Application.

Exit criteria:

- Explain how a page loads from navigation to first paint.
- Diagnose a layout, network, and event-propagation issue.
- Build an accessible responsive page without a framework.

## Phase 2 — JavaScript runtime

Study:

- values, coercion, equality, scope, execution context;
- lexical environments, closures, `this`, call/apply/bind;
- objects, property descriptors, prototypes, classes;
- functions, higher-order functions, composition, immutability;
- event loop, tasks, microtasks, promises, async/await;
- iterators, generators, modules, dynamic imports;
- errors, cancellation, memory, garbage collection basics.

Exit criteria:

- Predict execution order for async code.
- Explain closure and prototype behavior without guessing.
- Implement debounce, throttle, memoization, retry, and concurrency limiting.

## Phase 3 — TypeScript

Study:

- inference, annotations, unions, intersections, literals;
- narrowing and discriminated unions;
- interfaces, type aliases, structural typing;
- generics and constraints;
- `keyof`, `typeof`, indexed access, mapped and conditional types;
- utility types, template literal types, overloads;
- module resolution, declaration files, compiler options;
- strictness, nullability, variance, type erasure.

Exit criteria:

- Keep `strict` enabled.
- Model API states without `any` or boolean combinations.
- Design reusable generic helpers with clear constraints.

## Phase 4 — Angular fundamentals

Study:

- CLI workspace and build pipeline;
- standalone bootstrap and application configuration;
- components, templates, bindings, control flow;
- input/output contracts and content projection;
- dependency injection, services, injection tokens;
- lifecycle, queries, host bindings and listeners;
- routing, forms, HTTP, error handling.

Exit criteria:

- Build a CRUD application with lazy routes, typed forms, HTTP, validation, and tests.
- Explain why each dependency is provided at its chosen scope.

## Phase 5 — Angular internals and reactivity

Study:

- AOT compilation and generated template instructions;
- logical views, embedded views, containers, injectors;
- change detection, signal dependency tracking, scheduling;
- zoneless operation and explicit notification;
- RxJS observable lifecycle, flattening operators, sharing;
- signal/observable interop and state ownership.

Exit criteria:

- Explain exactly why a component re-renders.
- Diagnose duplicate HTTP calls, leaks, stale UI, and unnecessary work.

## Phase 6 — Architecture and production readiness

Study:

- feature-first architecture and public APIs;
- smart/presentational separation where useful;
- facade, adapter, repository, strategy, factory, mediator patterns;
- server state versus client state versus URL state;
- testing pyramid, contract tests, E2E boundaries;
- performance budgets, lazy loading, defer blocks, SSR, hydration;
- security, accessibility, observability, CI/CD;
- migrations, monorepos, libraries, micro-frontends trade-offs.

Exit criteria:

- Produce an architecture decision record for a large Angular application.
- Defend state, routing, API, testing, deployment, and migration choices.

## Suggested 16-week plan

| Weeks | Focus | Deliverable |
|---|---|---|
| 1–2 | Browser, HTML, CSS, accessibility | Responsive accessible dashboard shell |
| 3–4 | JavaScript runtime | Utility library plus async exercises |
| 5 | TypeScript fundamentals | Strictly typed domain model |
| 6 | Advanced TypeScript | Typed API and reusable utilities |
| 7–8 | Angular core | Standalone CRUD application |
| 9 | Routing, forms, HTTP | Multi-page workflow with guards and validation |
| 10 | Signals and RxJS | Reactive search and optimistic update flow |
| 11 | Internals and debugging | Performance and change-detection investigation |
| 12 | Architecture and patterns | Feature-oriented refactor |
| 13 | Testing | Unit, component, integration, E2E suite |
| 14 | SSR, performance, security, a11y | Production-readiness pass |
| 15 | Enterprise project | Reference architecture implementation |
| 16 | Interview preparation | Mock interviews and system-design review |

## Daily study loop

1. Read one concept from a primary source.
2. Write the mechanism in your own words.
3. Implement a minimal example.
4. Break it deliberately.
5. Debug it with browser and Angular tooling.
6. Record one interview explanation and one production use case.

## Revision system

For every topic, maintain four answers:

- **Definition:** what it is.
- **Mechanism:** how it works internally.
- **Decision:** when to use or avoid it.
- **Failure mode:** what commonly goes wrong.

## Portfolio evidence

A credible Angular portfolio should contain:

- one accessible responsive application;
- one application with complex reactive forms;
- one application with search, pagination, caching, cancellation, and optimistic updates;
- unit, component, integration, and E2E tests;
- performance measurements before and after optimization;
- an architecture document explaining boundaries and trade-offs;
- CI validation and a reproducible production build.
