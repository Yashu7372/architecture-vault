# Angular Visual Engineering Guide

This guide connects the most important runtime and architecture diagrams to the detailed chapters. The SVG sources are stored under [`assets/`](assets/) and can be edited directly without proprietary design tools.

## 1. Browser navigation and rendering

![Browser navigation and rendering pipeline](assets/browser-rendering-pipeline.svg)

Use this diagram to reason from URL entry through DNS, transport, HTTP, parsing, layout, paint, compositing, and user-centric performance metrics.

Detailed chapter: [Frontend and browser foundations](01-frontend-browser-foundations.md#1-navigation-to-rendering)

## 2. JavaScript event loop

![JavaScript event loop](assets/javascript-event-loop.svg)

The important ordering is: execute the current stack, drain microtasks, allow a rendering opportunity, and then run the next eligible task. This explains promise/timer ordering, UI starvation, and many Angular scheduling questions.

Detailed chapter: [JavaScript deep dive](02-javascript-deep-dive.md#10-event-loop)

## 3. Angular compilation and runtime

![Angular compilation and runtime pipeline](assets/angular-compilation-runtime.svg)

Angular templates are compiled into framework instructions. At runtime Angular bootstraps providers, creates logical views and component instances, evaluates bindings, and writes only relevant DOM changes.

Detailed chapter: [Angular internals](05-angular-internals.md#1-compilation-pipeline)

## 4. Dependency injection hierarchy

![Angular dependency injection hierarchy](assets/angular-di-hierarchy.svg)

Provider placement controls visibility, sharing, lifetime, and cleanup. Prefer application scope only for truly application-wide concerns and route scope for feature state.

Detailed chapter: [Angular internals](05-angular-internals.md#9-dependency-injection-internals)

## 5. Signals and targeted change detection

![Signals and Angular change detection](assets/signals-change-detection.svg)

Signal reads establish dynamic dependencies. Updates invalidate dependent consumers, Angular schedules affected views, and binding comparison determines actual DOM writes.

Detailed chapter: [Angular internals](05-angular-internals.md#7-signals-internals)

## 6. RxJS flattening operator selection

![RxJS flattening operator decision guide](assets/rxjs-flattening-operator-decision.svg)

Choose a flattening operator by defining cancellation, ordering, concurrency, and duplicate-trigger behavior. The operator is the implementation of that policy.

Detailed chapter: [RxJS, signals, and state management](07-reactivity-and-state.md#5-essential-operators)

## 7. Enterprise Angular architecture

![Enterprise Angular reference architecture](assets/enterprise-angular-architecture.svg)

The blueprint separates a small application shell, lazy business features, route-scoped state, domain models, infrastructure adapters, external systems, and business-neutral cross-cutting capabilities.

Detailed chapter: [Enterprise Angular application blueprint](11-enterprise-blueprint.md)

## 8. Testing strategy

![Angular testing strategy](assets/testing-pyramid.svg)

Most behavior should be proven with fast unit and component tests. Integration, contract, and E2E tests provide broader evidence at greater execution and diagnosis cost. Accessibility, visual, performance, architecture, and security checks run across the pyramid.

Detailed chapter: [Testing and engineering quality](09-testing-quality.md#1-test-levels)

## Diagram usage rules

- Keep diagrams focused on one mental model.
- Prefer stable engineering concepts over screenshots tied to a temporary UI version.
- Store editable SVG in the repository.
- Include an SVG `title`, `desc`, and meaningful Markdown alternative text.
- Update both diagram and explanation when architecture changes.
- Do not treat a diagram as proof that implementation boundaries are actually enforced; validate with code and tooling.
