# Angular and Frontend Interview Preparation

Use this file after studying the technical chapters. For every answer explain definition, internal mechanism, production use, trade-off, and failure mode.

## 1. How to answer technical questions

A strong structure:

1. State the concept precisely.
2. Explain how it works internally.
3. Give a real use case.
4. Compare alternatives.
5. Mention common failure or performance/security concern.
6. Connect it to something you implemented.

Avoid API-name dumping without reasoning.

---

# JavaScript Questions

## 2. `var`, `let`, and `const`

- `var` is function-scoped, hoisted, and initialized to `undefined`; repeated declarations are allowed.
- `let` and `const` are block-scoped and remain in the temporal dead zone until initialization.
- `const` prevents rebinding, not mutation of referenced objects.
- Prefer `const`, then `let`; avoid `var` in modern application code.

## 3. What is a closure?

A function retains access to lexical bindings from the scope where it was created, even after the outer function returns. Use cases include encapsulation, callback state, factories, memoization, and event handlers. A closure can retain large objects and contribute to memory leaks if a long-lived callback keeps unnecessary state reachable.

## 4. Explain `this`

For normal functions, `this` depends on the invocation form. Arrow functions capture lexical `this` and cannot be used as constructors. Discuss method extraction, `bind`, class callbacks, and the per-instance cost of arrow-function fields.

## 5. Explain prototypes

Objects delegate missing property lookup through a prototype chain. Class syntax creates constructor/prototype behavior with clearer syntax. Instance fields live per object; class methods generally live on the prototype.

## 6. Event loop, task, and microtask

Current stack runs to completion, then microtasks such as promise reactions are drained before the next task and usually before rendering. Timers schedule tasks. Excessive synchronous work or microtasks can delay interaction and paint.

Expected output:

```js
console.log('A');
setTimeout(() => console.log('B'));
Promise.resolve().then(() => console.log('C'));
queueMicrotask(() => console.log('D'));
console.log('E');
// A E C D B
```

## 7. Promise methods

- `Promise.all`: parallel, fail fast.
- `allSettled`: collect every outcome.
- `race`: settle with first settled promise.
- `any`: fulfill with first fulfillment, reject if all reject.

Mention cancellation: promises do not inherently cancel; use `AbortController` or a higher-level abstraction.

## 8. Debounce versus throttle

Debounce waits for inactivity; useful for search input. Throttle limits execution rate; useful for continuous scroll/resize telemetry. Explain leading/trailing behavior and cleanup.

## 9. Shallow versus deep copy

Object/array spread copies one level. Nested references remain shared. Deep cloning can lose prototypes or unsupported values depending on technique and can be expensive. Prefer normalized state and targeted immutable updates.

## 10. `==` versus `===`

`==` performs coercion; `===` compares without coercion. Prefer strict equality. Mention `Object.is` for `NaN` and signed zero differences.

## 11. Memory leaks in frontend applications

Common causes: unremoved global listeners, timers, subscriptions, detached DOM, closure retention, long-lived caches, unresolved third-party resources, root services retaining feature state.

Debug with repeated navigation, heap snapshots, allocation recording, and retaining paths.

---

# TypeScript Questions

## 12. `any` versus `unknown`

`any` disables checking and propagates unsafety. `unknown` requires narrowing before use. Receive untrusted values as `unknown`, validate, then convert.

## 13. `never` versus `void`

`void` means a function's useful return value is ignored/absent. `never` represents no possible value, such as a function that always throws or an exhaustively eliminated union.

## 14. Interface versus type alias

Both describe object shapes. Interfaces support declaration merging and are natural for extendable object contracts. Type aliases model unions, tuples, primitives, and computed types. Choose for semantics, not a universal rule.

## 15. Structural typing

Compatibility is based primarily on shape rather than declared identity. Explain excess-property checks and branded types when nominal distinction is needed.

## 16. Generics

Generics preserve relationships between input and output types. A good generic parameter appears in multiple meaningful positions or represents an intentional caller choice. Constraints express implementation requirements.

## 17. Narrowing

Explain `typeof`, `instanceof`, discriminants, `in`, predicates, assertion functions, equality, and control-flow analysis. Warn that type assertions do not validate runtime data.

## 18. Union versus intersection

Union means one of several alternatives. Intersection requires all combined members. Discriminated unions are excellent for UI and workflow states.

## 19. Utility and mapped types

Discuss `Partial`, `Pick`, `Omit`, `Record`, `Readonly`, `Exclude`, `Extract`, `NonNullable`, `ReturnType`, mapped and conditional types. Warn against `Partial<Entity>` for unrestricted update commands.

## 20. Why interfaces cannot be Angular DI tokens

Interfaces are erased during JavaScript emission, so no runtime value exists. Use an `InjectionToken` or abstract class.

## 21. Does TypeScript validate HTTP responses?

No. Generic annotations and assertions affect compile-time checking only. Validate unknown external data with a parser/schema and map it to application models.

---

# Angular Fundamentals Questions

## 22. What is a component?

A component is a directive with a template and host view. It consists of class state/behavior, compiled template, styles, host bindings, DI context, lifecycle, and participation in a view tree.

## 23. Standalone components versus NgModules

Standalone APIs let components/directives/pipes declare imports directly and use functional bootstrap/providers. NgModules remain relevant in legacy code and some library patterns. Modern Angular defaults toward standalone architecture because dependencies and lazy boundaries are more explicit.

## 24. Binding types

- interpolation: text/string representation;
- property binding: DOM/component/directive property;
- event binding: listener;
- two-way binding: property plus corresponding update event/model contract;
- attribute/class/style binding: specialized output to DOM representation.

## 25. Input and output design

Inputs provide parent-owned data; outputs emit child events/intents. Prefer readonly input semantics and domain-specific output names. Do not mutate input objects or expose raw DOM events unnecessarily.

## 26. Lifecycle hooks

Explain initialization, input changes, content/view initialization, checks/render callbacks, and destruction. Emphasize choosing the correct ownership mechanism rather than placing all initialization in one hook.

## 27. Dependency injection

DI maps runtime tokens to provider recipes and resolves them through hierarchical injectors. Explain `useClass`, `useValue`, `useExisting`, `useFactory`, injection tokens, and scope/lifetime.

## 28. `providedIn: 'root'`

Creates an application-level tree-shakable provider when used. It is appropriate for shared stateless infrastructure or true application state, not every feature service.

## 29. Route-level providers

They create a feature environment scope tied to a route subtree. Useful for feature state/services that should be created on navigation and released when the feature is destroyed.

## 30. Content projection

Consumer content is placed into slots defined by a component. Explain logical ownership of projected bindings, multi-slot selection, queries, and when composition is better than huge configurable components.

## 31. Directive versus component

A component owns a view/template. An attribute directive adds behavior to an existing host. Use components for visual structure and directives for reusable host behavior.

## 32. Pure versus impure pipe

Pure pipes are invoked based on input changes and suit deterministic presentation. Impure pipes can run often and are risky for performance. Pipes should not perform side effects or network calls.

---

# Angular Internals Questions

## 33. AOT versus JIT

AOT compiles templates during build, enabling template checking, optimization, smaller runtime needs, and faster startup. JIT compiles at runtime and is mainly relevant to development/special scenarios.

## 34. How Angular renders a component

Describe compiled template instructions, host/view creation, injector resolution, component/directive instantiation, creation pass, binding update pass, lifecycle, child/embedded views, and cleanup.

## 35. Change detection

Change detection evaluates relevant bindings and synchronizes changed values with DOM/views. Explain notification/scheduling, view traversal, binding comparison, and DOM write behavior.

## 36. Default versus OnPush

OnPush creates an explicit checking boundary but can still be checked after input changes, events in its subtree, signal notifications, explicit marking, and supported framework activity. It requires clear immutable/reactive data flow; it is not “render once.”

## 37. Signals internally

Signals form a producer/consumer graph. Reads inside reactive consumers register dependencies. Writes invalidate dependent computations/consumers. Computed signals are memoized and dynamically track dependencies.

## 38. Computed versus effect

Computed derives a value and should be pure. Effect synchronizes state with external side effects. Copying signal A into signal B with an effect is usually inferior to a computed signal.

## 39. ZoneJS versus zoneless

ZoneJS patches async APIs and historically triggered broad Angular synchronization after tasks. Zoneless relies on explicit Angular notifications such as signals, inputs, and Angular listeners, reducing monkey patching and unnecessary checks. Current Angular major versions default toward zoneless operation.

## 40. Hierarchical injectors

Explain environment/application, route/feature, and element injector scopes. Resolution walks an appropriate hierarchy. Provider location controls lifetime and sharing.

## 41. Embedded views

Control flow, templates, deferred blocks, and similar features can create embedded views inside containers. These views have their own binding state, directives, and lifecycle and can be inserted, moved, or destroyed.

## 42. Why stable list tracking matters

It lets Angular associate items with existing DOM/view instances. Unstable tracking recreates nodes, loses local state/focus, and increases rendering work.

---

# Routing Questions

## 43. Lazy loading

Use `loadComponent` or `loadChildren` with dynamic imports. Lazy loading splits code and defers feature work. Verify actual chunks and avoid making shared dependencies dominate the initial bundle.

## 44. Guard versus resolver

A guard decides whether/how navigation proceeds. A resolver obtains data before activation. Backend authorization remains mandatory. Resolvers can delay navigation, so use only for route-critical data.

## 45. Path versus query parameters

Path parameters identify hierarchy/resource; query parameters represent optional filters, sort, pagination, and view state. URL state should be serializable and shareable.

## 46. Route reuse and state

Discuss component lifetime, parameter-only navigation, route-scoped stores, stale data, and explicit reuse strategies. Do not assume a component is reconstructed for every URL change.

## 47. Testing routing

Use actual router testing harnesses for redirects, guards, parameters, nested routes, and activation. Avoid mocking away the behavior being tested.

---

# Forms Questions

## 48. Template-driven versus reactive forms

Template-driven forms are suitable for simple forms and place more configuration in templates. Reactive forms provide explicit models, composability, typed controls, dynamic behavior, and testability, making them common for enterprise workflows.

## 49. `setValue` versus `patchValue`

`setValue` requires the complete control shape; `patchValue` updates a subset. Prefer explicitness for critical mapping and use patching intentionally.

## 50. Sync versus async validators

Sync validators return immediately. Async validators return promise/observable and place controls in pending state. Async validation should debounce/cancel and never replace backend validation.

## 51. Cross-field validation

Attach a validator to the common parent group and compare related controls. Decide where errors are displayed and keep validation logic independent from template rendering.

## 52. Custom form control

Explain value accessor callbacks, programmatic writes, touched state, disabled state, avoiding feedback loops, keyboard behavior, accessible labeling, and optional validation integration.

## 53. Prevent duplicate submission

Disable while pending and use an explicit concurrency policy such as `exhaustMap`, idempotency key, or backend duplicate protection. UI disabling alone is not distributed idempotency.

---

# RxJS and Signals Questions

## 54. Observable versus promise

Promises represent one eventual settlement and start when created by their producer logic. Observables can emit many values, may be lazy, are composable, and support unsubscription/cancellation semantics. HTTP observables in Angular are typically cold and single-emission.

## 55. Cold versus hot observable

Cold creates producer per subscription; hot source exists independently/shared. Explain duplicate HTTP requests and sharing trade-offs.

## 56. Subject types

- Subject: no current/replay value.
- BehaviorSubject: current value.
- ReplaySubject: buffered history.
- AsyncSubject: final value on completion.

Signals often replace BehaviorSubject for synchronous state, not asynchronous stream composition.

## 57. Flattening operators

- `switchMap`: latest wins/cancel previous.
- `concatMap`: queue and preserve order.
- `mergeMap`: concurrent work.
- `exhaustMap`: ignore new triggers while active.

Do not answer only with definitions; give search, queue, parallel upload, and login/submit examples.

## 58. `combineLatest` versus `forkJoin`

`combineLatest` emits whenever a source changes after all have emitted and suits ongoing streams. `forkJoin` emits once after all finite sources complete and suits parallel one-time requests.

## 59. `shareReplay` risks

Can retain stale values/errors/resources, create unclear ref-count behavior, leak memory, cross authorization scope, and hide invalidation. Use explicit cache policy.

## 60. Nested subscription problem

Creates difficult cancellation, ordering, error handling, and cleanup. Use flattening/composition unless separate independent side effects are truly intended.

## 61. Signal versus observable decision

Signals: current synchronous owned/derived state and template dependency tracking. Observables: asynchronous events, HTTP, time, cancellation, concurrency, real-time streams. Convert once at a clear boundary.

## 62. Signal state store

Keep writable state private, expose readonly/computed selectors, implement intention-revealing methods, scope provider correctly, and model loading/errors explicitly.

---

# Architecture and Design Pattern Questions

## 63. How would you structure a large Angular application?

Feature-first lazy boundaries; private feature internals; small core infrastructure; reusable design system; explicit data-access/domain/state/UI layers based on complexity; route-scoped state; DTO mapping; enforced dependency rules; CI/observability/security/accessibility.

## 64. Facade pattern

A facade exposes a stable feature API while hiding state/repository orchestration. It reduces component coupling but can become a god object or meaningless pass-through layer.

## 65. Repository and adapter patterns

Repository exposes domain-oriented data operations. Adapter isolates external representation or SDK. Use where transport change, mapping, caching, testing, or external-system isolation justify it.

## 66. Smart versus presentational components

Feature components coordinate routes/state/use cases. UI components render inputs and emit intent. Do not apply mechanically; local view state can remain inside reusable components.

## 67. Global state decision

Use global state only for genuinely application-wide or cross-feature long-lived state. URL state belongs in router; forms in form model; local UI in component; server state requires freshness/cache policy; feature workflows often route-scoped.

## 68. Micro-frontends

Useful for independent team release/ownership at significant scale. Costs include duplicated dependencies, performance, integration tests, shared session/routing/design system, version drift, and operational complexity. Prefer modular monolith until organizational autonomy requires distribution.

## 69. Modular monolith

One deployable frontend with strong feature/library boundaries. It preserves simpler runtime integration while allowing team modularity. Enforce boundaries with tooling.

## 70. State machine use case

Use for multi-step, asynchronous, failure-prone workflows where impossible combinations must be prevented. Model states and allowed events/transitions explicitly.

---

# Testing Questions

## 71. Testing strategy

Pure logic at unit level, component tests for template interaction, integration tests for router/HTTP/forms, contract tests for API compatibility, E2E for critical journeys, accessibility and performance checks for system qualities.

## 72. What should not be mocked?

Do not mock Angular/router behavior when testing that integration. Avoid mocking every internal collaborator. Mock external boundaries and nondeterministic sources.

## 73. Component test versus class test

Class test verifies isolated logic. Component test verifies class-template-DOM interaction, inputs/outputs, event behavior, and accessibility. Use based on risk.

## 74. How do you test time?

Inject a clock or scheduler; use fake timers where appropriate. Avoid depending on real wall-clock delays.

## 75. E2E locator strategy

Prefer role, accessible name, label, and stable semantic identifiers. Avoid brittle CSS hierarchy and arbitrary sleeps.

## 76. Flaky test diagnosis

Look for uncontrolled time, network, animation, shared state, order dependence, race conditions, unstable selectors, environment variance, and missing cleanup. Fix root cause instead of adding retries/sleeps blindly.

---

# Performance Questions

## 77. How do you improve Angular performance?

Measure first. Check bundle, network, long tasks, repeated bindings, list tracking, template functions, state fan-out, DOM/layout, duplicate requests, large data, third-party scripts, memory. Apply targeted lazy/defer, computed memoization, stable identity, virtualization, server aggregation, and caching.

## 78. What causes unnecessary rerendering?

Broad notifications, unstable object/list identity, poor tracking, expensive template expressions, impure pipes, duplicated state/effects, large component subtrees, frequent async events, manual detection misuse.

## 79. Virtual scrolling

Renders only visible subset and reuses views. Useful for large fixed/known-height collections. Consider variable height, focus, screen-reader expectations, server pagination, and selection state.

## 80. SSR versus CSR

SSR improves initial HTML/SEO for suitable public pages but adds server complexity and hydration constraints. CSR is simpler and often sufficient for authenticated applications. Decide using user/device/network and SEO requirements.

## 81. Hydration mismatch

Caused by invalid or non-deterministic server/client DOM, browser-only code, direct DOM mutation, random/time differences, configuration mismatch, and incompatible third-party behavior.

## 82. Memory leak investigation

Reproduce repeated navigation/action, record heap snapshots, compare retained objects, inspect listeners/subscriptions/timers/caches, identify retaining paths, fix cleanup/scope, and validate stable memory.

---

# Security and Accessibility Questions

## 83. Does a route guard secure a route?

No. It controls client navigation and UX. Backend authorization must protect all data and operations.

## 84. XSS in Angular

Angular applies context-aware escaping/sanitization to template bindings. Risk appears with unsafe DOM APIs, sanitizer bypass, untrusted HTML/resource URLs, dynamic code, and compromised dependencies. Use CSP and minimize bypass.

## 85. Token storage

JavaScript-readable storage is exposed to XSS. Prefer secure HTTP-only cookies when architecture supports them, with CSRF protection. Otherwise use short-lived tokens, minimal storage exposure, and coordinated refresh.

## 86. What is CORS?

A browser security policy controlling cross-origin requests based on server response headers. It is not authentication and usually cannot be solved solely in Angular. Explain preflight.

## 87. Accessible custom control

Define semantic role, accessible name, keyboard interaction, focus behavior, state properties, error/help association, disabled behavior, and screen-reader announcements. Prefer native elements when possible.

## 88. Dialog focus

Move focus into dialog, constrain interaction appropriately, support Escape/close, provide accessible name, and restore focus to meaningful trigger after closing.

---

# Scenario Questions

## 89. Search sends stale results

Likely race between requests. Use debounced distinct query stream with `switchMap`, display request/error state, and store query in URL if shareable.

## 90. API is called twice

Check multiple subscriptions to cold observable, duplicate effects/lifecycle calls, template subscriptions, router activation, retry, SSR/client duplication, and cache/share configuration.

## 91. OnPush component does not update

Check object mutation, duplicate provider/store instance, whether template reads the changed signal, whether update occurs through supported scheduling, track key, detached view, or incorrect computed dependency.

## 92. Memory increases after navigation

Check root-scoped feature store, global listeners, timers, subscriptions, third-party widgets, cached route handles, effects, detached DOM, and retained HTTP/real-time streams.

## 93. Large table is slow

Measure DOM size and interaction. Use server pagination/filtering, virtual scrolling, stable tracking, computed formatting, smaller row components only if useful, avoid impure pipes/functions, and reduce change fan-out.

## 94. Complex form is unmaintainable

Separate form construction, validators, mapping, submission state, server errors, sections/custom controls, and workflow state. Use typed models and state machine for multi-step behavior.

## 95. Need shared state between two routes

First consider URL, parent route scope, backend/server state, or route-scoped feature store. Avoid root global state unless lifetime is truly application-wide.

## 96. Real-time events arrive out of order

Use event/aggregate IDs and versions, idempotent application, buffering/rejection policy, gap detection, and authoritative snapshot refresh. Transport arrival order alone is insufficient.

## 97. Token refresh causes multiple refresh requests

Coordinate refresh through one shared in-flight operation, queue/retry eligible failed requests once, avoid interceptor recursion, fail session consistently, and prevent non-idempotent duplicate writes.

## 98. Upgrade from legacy Angular

Inventory versions/dependencies, add tests/telemetry, use official migrations incrementally, remove deprecated APIs, establish lazy/feature boundaries, migrate standalone/signals where valuable, test zoneless separately, and measure after each stage.

## 99. Replace a UI library

Create an inventory and adapter/design-system boundary, map behavior/accessibility not only appearance, migrate by component category, add visual/harness tests, support compatibility period, and avoid product rewrite in same release.

## 100. Design an Angular reporting portal

Discuss:

- lazy report catalog/run/history/admin features;
- typed generalized report request envelope;
- form/schema rendering constraints;
- async generation and progress;
- large download streaming/link strategy;
- permission and audit;
- server-side pagination/search;
- cache/freshness;
- route state;
- error taxonomy;
- observability and correlation;
- accessibility of forms/tables;
- test and deployment strategy.

---

# Coding Exercises

## 101. Implement debounce

Requirements: preserve `this`, latest arguments, cancel/reset timer, optional cancel/flush extensions.

## 102. Implement typed `groupBy`

```ts
function groupBy<T, K extends PropertyKey>(
  values: readonly T[],
  keySelector: (value: T) => K,
): Map<K, T[]>;
```

Explain complexity.

## 103. Model request state

Use a discriminated union and exhaustive rendering instead of booleans.

## 104. RxJS typeahead

Requirements: minimum length, debounce, distinct, cancellation, loading, error recovery, stale result prevention, cleanup.

## 105. Signal store

Private writable state, readonly selectors, computed filtered values, load action, error handling, route scope, test.

## 106. Custom form validator

Create typed date-range or password-confirmation validator and component test for accessible error display.

## 107. HTTP interceptor

Attach correlation ID without mutating request, record timing, avoid logging body/token, preserve error.

## 108. Optimistic update

Update local entity, send command with operation ID, reconcile success, rollback/conflict on failure, test duplicate response.

## 109. Route guard

Return redirect result/URL tree, preserve validated return URL, test authenticated and anonymous states.

## 110. Real-time reducer

Apply versioned events idempotently; reject duplicates, detect gaps, trigger snapshot refresh.

---

# Frontend System Design Interview

## 111. Clarify requirements

Ask about:

- users and scale;
- authenticated/public;
- browser/device/network support;
- SEO/SSR;
- data volume and update rate;
- offline/real-time needs;
- accessibility/localization;
- security/compliance;
- team ownership and release model;
- observability and SLA;
- migration constraints.

## 112. Present architecture

Cover:

1. app shell and routes;
2. feature boundaries;
3. state classification/ownership;
4. API and real-time data flow;
5. component/design-system strategy;
6. authentication/authorization;
7. error/loading/offline behavior;
8. performance and caching;
9. testing;
10. deployment and observability;
11. trade-offs and evolution.

## 113. State ownership matrix

Always identify:

```text
State             Owner                  Lifetime
Current user      root session store     application/session
Search filters    URL                    navigation/shareable
Edit form         form/page              route/component
Order list        feature server cache   route/TTL
Modal open        component              component
Reference data    repository cache       policy-defined
```

## 114. Scale discussion

Discuss frontend scale as:

- bundle and route size;
- DOM/data volume;
- API request volume;
- real-time event rate;
- team/repository complexity;
- release frequency;
- browser/device constraints;
- telemetry cardinality;
- cache correctness.

## 115. Trade-off language

Use explicit comparisons:

- “I would start with a route-scoped signal store because the state is local and synchronous; I would introduce a reducer library if transitions and cross-feature coordination become complex.”
- “SSR is valuable for public indexed pages, but for an internal authenticated portal I would first measure startup and use CSR unless initial rendering requirements justify server complexity.”
- “A modular monolith gives boundary enforcement without runtime integration cost; micro-frontends become justified when independent release ownership is a hard requirement.”

---

# Behavioral and Project Questions

## 116. Most complex frontend problem

Answer with:

- business context and constraints;
- architecture before issue;
- evidence and diagnosis;
- options considered;
- decision and implementation;
- measurable outcome;
- remaining trade-off.

## 117. Performance issue example

Use numbers: route time, bundle size, duplicate calls, long task, memory growth, before/after result. Explain measurement method.

## 118. Production incident

Explain detection, impact, mitigation, root cause, permanent fix, tests/monitoring added, and communication. Avoid blaming individuals.

## 119. Disagreement on architecture

Explain shared goals, evidence, prototypes, decision criteria, ADR, and commitment after decision. Show ability to revise based on new evidence.

## 120. Code quality improvement

Describe incremental boundary enforcement, tests, lint rules, migration strategy, developer experience, and measured reduction in defects or change time.

---

# Mock Interview Checklist

Before interview, be able to answer without notes:

- browser rendering and event loop;
- closure, prototype, `this`, promise concurrency;
- strict TypeScript, generics, narrowing, runtime validation;
- Angular bootstrap, components, DI, lifecycle, routing, forms, HTTP;
- AOT, views, change detection, signals, zoneless;
- RxJS flattening and sharing;
- feature architecture and provider scopes;
- testing pyramid and failure testing;
- bundle/render/network/memory optimization;
- SSR/hydration decision;
- XSS, CSRF, token storage, backend authorization;
- accessibility of forms, dialogs, and dynamic content;
- enterprise system design with state ownership and trade-offs.

## Final preparation routine

1. Explain ten core concepts aloud in two minutes each.
2. Solve one JavaScript and one TypeScript exercise daily.
3. Implement one Angular/RxJS scenario without copying.
4. Review one architecture trade-off and ADR.
5. Run one 45-minute system-design mock.
6. Prepare three project stories with measurable results.
7. Practice saying what you do not know and how you would verify it.
