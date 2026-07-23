# Angular Internals

Understanding internals turns framework symptoms into explainable behavior. Internal implementation details can change, so depend on public APIs in application code while using this model for reasoning.

## 1. Compilation pipeline

Angular templates are not executed as arbitrary strings at runtime. In an AOT production build, Angular compiles component metadata and templates into JavaScript instructions.

Conceptual stages:

1. TypeScript and Angular metadata are analyzed.
2. Templates are parsed into an Angular template AST.
3. Template expressions are type-checked using generated type-checking code.
4. Components, directives, pipes, providers, and dependencies are linked.
5. Rendering instructions are emitted.
6. Bundling, optimization, chunking, minification, and source maps are applied.

AOT advantages:

- template errors are found during build;
- runtime compiler payload is avoided;
- templates can be optimized and tree-shaken;
- startup work is reduced;
- security is improved compared with runtime compilation of untrusted templates.

## 2. Component definition and creation

A compiled component carries framework-readable definition metadata. When Angular creates it, it conceptually:

1. selects or creates a host element;
2. creates a logical view data structure;
3. resolves the element/environment injector chain;
4. creates the component instance;
5. establishes inputs, outputs, queries, and host behavior;
6. executes creation-mode template instructions;
7. runs the first update pass and lifecycle hooks;
8. retains data required for later updates and destruction.

A component is therefore more than a class instance. It participates in a view tree, injector hierarchy, rendering context, lifecycle, and scheduler.

## 3. Logical views and templates

Angular maintains compact runtime structures representing views and static template metadata. Exact internal names and layouts are implementation details, but the useful model is:

- **template metadata:** shared information created once for a template;
- **view instance state:** bindings, nodes, directive instances, cleanup functions, and child views for one rendered instance;
- **containers:** insertion points for embedded or dynamically created views;
- **embedded views:** template instances created by control flow, template outlets, and similar constructs.

`@if`, `@for`, route outlets, deferred blocks, and dynamic components can create, attach, detach, move, or destroy views.

## 4. Binding updates

During an update pass, generated instructions evaluate template expressions and compare binding values with prior values. DOM writes are performed when relevant values change.

Implications:

- template expressions may run often; keep them cheap and free of side effects;
- returning a new object or array each evaluation can cause downstream work;
- getters are not automatically memoized;
- stable list tracking allows Angular to reuse DOM and view instances;
- signals can narrow which consumers need notification, but expensive derived work still requires sound design.

## 5. Change detection mental model

Change detection synchronizes application state with rendered views.

Questions to ask:

1. What state changed?
2. What notified Angular?
3. Which views are scheduled or considered?
4. Which bindings are reevaluated?
5. Which DOM operations occur?

### Default and OnPush

`OnPush` is an explicit rendering boundary. A view can still be checked when Angular receives a relevant notification, including input changes, events in the subtree, signal updates read by the template, explicit marking, or other supported scheduling paths.

`OnPush` does not mean “render only once,” and it does not repair mutable data flow automatically.

```ts
// Fragile: same object identity, hidden mutation
user.name = 'Updated';

// Clear state transition
user = { ...user, name: 'Updated' };
```

## 6. Zone-based and zoneless scheduling

Historically, ZoneJS patched many asynchronous browser APIs and let Angular schedule synchronization after async activity. This is broad because the framework may not know whether a particular task changed application state.

Modern Angular supports and, in current major versions, defaults toward zoneless operation. In a zoneless application, Angular relies on explicit framework notifications such as:

- signal updates observed by templates;
- input updates;
- event listeners registered through Angular;
- view attachment or explicit change-detection APIs;
- framework-managed async rendering behavior.

Zoneless benefits include less monkey patching, clearer scheduling, smaller overhead, and easier async stack reasoning. The application must avoid relying on accidental ZoneJS-triggered checks.

## 7. Signals internals

A signal graph consists conceptually of producers and consumers.

- Writable signals are producers with mutable values.
- Computed signals are both consumers of their dependencies and producers for downstream consumers.
- Templates and effects can act as consumers.

When a consumer runs, Angular records which signal reads occurred. When a producer changes, dependent consumers are invalidated or scheduled.

Key properties:

- dependencies are tracked dynamically;
- computed values are memoized and recalculated when stale and read;
- equality determines whether a writable update is considered changed;
- reading a signal establishes dependency only in a reactive consumer context;
- untracked reads intentionally avoid dependency registration.

Avoid cycles and effect-based propagation chains.

```ts
readonly subtotal = computed(() =>
  this.lines().reduce((sum, line) => sum + line.price * line.quantity, 0)
);
```

This is superior to an effect that writes subtotal into another signal.

## 8. Effects

Effects rerun when tracked dependencies change and are intended to synchronize reactive state with external effects.

Appropriate uses:

- persistence to a browser API;
- imperative chart or map synchronization;
- analytics based on a stable event policy;
- integration with non-reactive APIs.

Poor uses:

- copying one signal into another;
- orchestrating long business workflows without cancellation rules;
- replacing computed values;
- silently writing to multiple unrelated state owners.

Always consider cleanup and repeated execution.

## 9. Dependency injection internals

DI resolves a token through injector hierarchies.

Conceptual injector scopes:

- environment/application injector;
- lazy route or feature environment injector;
- element injectors associated with rendered nodes/components/directives.

Resolution generally searches the appropriate injector chain based on where injection occurs and provider flags/configuration.

A provider describes how to obtain a value:

```ts
{ provide: LOGGER, useClass: BrowserLogger }
{ provide: API_URL, useValue: environment.apiUrl }
{ provide: USER_REPOSITORY, useExisting: HttpUserRepository }
{ provide: FEATURE_CONFIG, useFactory: createConfig, deps: [ENV] }
```

Provider scope controls lifetime and sharing. Incorrect scope can create:

- duplicated API clients or state stores;
- state leaking across features;
- unexpectedly shared mutable state;
- circular dependencies;
- memory retained for the whole application.

## 10. Injection context

Some APIs such as `inject()` require an active injection context. This exists during supported framework-managed creation or can be established explicitly with public APIs.

Do not call `inject()` from arbitrary asynchronous callbacks and assume it will work. Resolve dependencies during creation, then retain the resulting collaborator.

## 11. Directives and matching

During template compilation/runtime creation, Angular determines which directives and components match template nodes. Inputs, outputs, host bindings, providers, and lifecycle behavior become associated with the node and its view.

Structural behavior conceptually uses templates and embedded views, even though modern built-in control-flow syntax is compiler-integrated rather than ordinary user directives.

## 12. Content projection

Projection assigns consumer-provided content to component-defined slots.

```html
<app-card>
  <h2 card-title>Title</h2>
  <p>Body</p>
</app-card>
```

The projected nodes belong logically to the consumer's view for binding context, while the receiving component controls placement. Understand this distinction when reasoning about queries, styling, lifecycle, and DI.

## 13. Queries

View queries inspect a component's own view. Content queries inspect projected content. Query timing depends on when matching nodes exist.

Avoid using queries as a general communication mechanism. Prefer inputs, outputs, DI contracts, or state services unless direct child/view access is genuinely required.

## 14. Pipes

Pure pipes can reuse results when input references/primitives have not changed according to Angular's invocation rules. They are suitable for deterministic presentation transformations.

Impure pipes run frequently and can be expensive. Avoid using a pipe to perform HTTP requests, mutate state, or conceal large computations.

## 15. Router internals mental model

A navigation conceptually includes:

1. URL parsing and recognition;
2. redirects;
3. guard checks;
4. lazy configuration loading;
5. resolver execution where configured;
6. component tree activation/deactivation;
7. URL and browser history updates;
8. navigation events and scroll/title behavior.

Navigations can be canceled, redirected, superseded, or fail. Treat route data and parameters as streams/state, not immutable constructor values for the component lifetime.

## 16. HTTP internals mental model

`HttpClient` creates an observable request pipeline. Interceptors wrap the request/response chain. The backend implementation eventually uses a browser transport.

A new subscription to a cold HTTP observable normally initiates a new request. Operators can transform, retry, share, cancel, or cache it.

Never use unbounded retry for non-idempotent operations. Decide retry policy based on method semantics, error type, backoff, and user impact.

## 17. Destruction and cleanup

Destroying a view must release:

- component/directive instances;
- DOM/event listeners registered through framework cleanup;
- child and embedded views;
- subscriptions tied to destruction utilities;
- effect cleanup;
- custom imperative resources.

Framework-managed template listeners are cleaned up. Manually registered global listeners, timers, workers, observers, and third-party instances remain your responsibility.

## 18. SSR and hydration internals

SSR renders HTML on the server. Hydration reuses server-rendered DOM on the client and attaches Angular behavior rather than discarding and rebuilding everything.

Hydration requires deterministic compatible structure. Invalid HTML, direct DOM mutation, inconsistent server/client configuration, browser-only assumptions, and unstable generated content can cause mismatch.

Incremental or deferred hydration can reduce startup work by hydrating only when needed, depending on current Angular capabilities and configuration.

## 19. Debugging internals

When UI is stale:

1. verify state actually changed;
2. verify mutation versus replacement semantics;
3. verify the template read the signal/observable result;
4. verify the update occurred in a framework-supported notification path;
5. inspect provider scope and duplicate store instances;
6. inspect detached views or route reuse;
7. reduce the issue to a minimal component.

When rendering is slow:

1. measure with DevTools and Angular tooling;
2. count repeated work, not only component count;
3. inspect list tracking and DOM churn;
4. inspect template functions/getters/pipes;
5. inspect large synchronous tasks and layout work;
6. inspect signal/effect dependency fan-out;
7. inspect duplicate network requests and parsing.

## 20. Internal concepts to explain in interviews

- AOT versus JIT.
- Template type checking.
- Component creation and view trees.
- Binding comparison and DOM updates.
- Default versus OnPush behavior.
- ZoneJS versus zoneless scheduling.
- Signal dependency tracking and memoized computed values.
- Hierarchical DI and provider lifetime.
- Embedded views and control flow.
- SSR versus hydration.
- Why direct DOM mutation can conflict with Angular rendering.
