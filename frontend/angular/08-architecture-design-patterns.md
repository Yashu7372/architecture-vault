# Angular Architecture and Design Patterns

Architecture is the set of boundaries and dependency rules that keep change local. Folder names alone do not create architecture.

## 1. Architecture goals

A scalable Angular design should optimize for:

- clear ownership;
- predictable dependency direction;
- feature isolation;
- independent testing;
- lazy loading and deployable performance;
- safe evolution of APIs and models;
- observability and failure isolation;
- accessibility and security by default;
- low cognitive load for developers.

## 2. Feature-first structure

Prefer grouping by business capability:

```text
src/app/
  core/
    auth/
    configuration/
    error-handling/
    http/
    observability/
  shared/
    ui/
    directives/
    pipes/
    utilities/
  features/
    orders/
      data-access/
      domain/
      feature-list/
      feature-detail/
      ui/
      orders.routes.ts
      public-api.ts
    customers/
  app.config.ts
  app.routes.ts
```

`core` contains application-wide infrastructure. `shared` contains truly reusable, stateless or carefully scoped building blocks. Feature-specific code stays in its feature.

A giant `shared` directory is usually a dependency dumping ground.

## 3. Dependency direction

A practical direction:

```text
feature page/orchestrator
        ↓
feature facade/store/use-case
        ↓
domain policies and ports
        ↓
data-access adapters
        ↓
HTTP/browser/framework infrastructure
```

UI may depend on stable domain/view contracts. Domain policy should not depend on Angular components, router, or HTTP DTOs.

Not every application needs a pure domain layer. Apply separation where business complexity and change justify it.

## 4. Public API boundaries

Expose only intended feature/library entry points:

```ts
// features/orders/public-api.ts
export { ORDERS_ROUTES } from './orders.routes';
export type { OrderSummary } from './domain/order-summary';
```

Avoid deep imports into another feature's internals. Enforce rules with linting, workspace tags, package boundaries, or architectural tests.

## 5. Smart and presentational components

Useful distinction:

- **feature/page component:** understands route, orchestration, feature state, and use cases;
- **UI component:** receives data and emits intent, with minimal business knowledge.

Do not force every component into one category. A local component can manage its own view state while remaining reusable.

## 6. Facade pattern

A facade gives the UI a stable feature-facing API.

```ts
@Injectable()
export class OrdersFacade {
  private readonly repository = inject(OrderRepository);
  private readonly state = signal<OrdersState>(initialState);

  readonly orders = computed(() => this.state().orders);
  readonly loading = computed(() => this.state().status === 'loading');

  load(): void { /* orchestration */ }
  cancel(id: OrderId): void { /* use case */ }
}
}
```

Benefits:

- hides RxJS/store/repository details;
- centralizes use-case orchestration;
- gives components a narrow contract;
- supports later state implementation changes.

Risks:

- “god facade” with every feature responsibility;
- pass-through methods with no value;
- hiding important asynchronous/error semantics.

## 7. Adapter pattern

Adapters isolate external representations.

```ts
function toOrder(dto: OrderDto): Order {
  return {
    id: asOrderId(dto.order_id),
    status: mapStatus(dto.status_code),
    total: { amountMinor: dto.total_minor, currency: dto.currency },
  };
}
```

Use adapters for:

- backend DTOs;
- browser storage;
- third-party widgets;
- analytics providers;
- authentication SDKs;
- date/time and localization libraries.

## 8. Repository pattern

A repository represents access to a collection or aggregate in domain terms.

```ts
export abstract class OrderRepository {
  abstract findById(id: OrderId): Observable<Order | null>;
  abstract search(query: OrderQuery): Observable<Page<OrderSummary>>;
  abstract cancel(id: OrderId): Observable<Order>;
}
```

Do not add repositories around every HTTP endpoint mechanically. They are valuable when they isolate transport details, caching, mapping, and domain-oriented operations.

## 9. Strategy pattern

Use strategy when behavior varies by policy:

```ts
export interface PricingStrategy {
  calculate(context: PricingContext): Money;
}
```

Provide strategies through tokens or registries. Avoid long `if/else` chains spread across components.

## 10. Factory pattern

Use a factory when construction depends on runtime configuration or subtype selection.

```ts
export const PAYMENT_HANDLER = new InjectionToken<PaymentHandler>('PAYMENT_HANDLER');

export function createPaymentHandler(config: PaymentConfig): PaymentHandler {
  switch (config.provider) {
    case 'provider-a': return new ProviderAHandler(config);
    case 'provider-b': return new ProviderBHandler(config);
    default: return assertNever(config);
  }
}
```

Prefer DI-managed factories when dependencies should be injected rather than manually instantiated.

## 11. Command pattern

A command models user intent with the data required to execute it.

```ts
type SubmitOrderCommand = Readonly<{
  customerId: CustomerId;
  lines: readonly OrderLineInput[];
  idempotencyKey: string;
}>;
```

Commands help separate form models from backend DTOs and make validation/auditing clearer.

## 12. Mediator/event bus pattern

Use a mediator for decoupled feature events only when ownership and event contracts are explicit.

Risks of a global event bus:

- invisible control flow;
- difficult tracing;
- ordering assumptions;
- accidental application-wide coupling;
- memory leaks;
- events used as commands.

Prefer direct calls, route state, or a scoped facade for local communication.

## 13. Observer pattern

RxJS and signals embody observer-like reactive relationships. Use reactive composition instead of manually maintaining arrays of listeners.

Understand that observability can create hidden fan-out. Keep dependency graphs small and effects controlled.

## 14. State machine pattern

Use explicit states for complex workflows:

```ts
type CheckoutState =
  | { step: 'cart'; cart: Cart }
  | { step: 'payment'; cart: Cart; payment: PaymentDraft }
  | { step: 'submitting'; command: SubmitOrderCommand }
  | { step: 'completed'; orderId: OrderId }
  | { step: 'failed'; error: AppError; recoverable: boolean };
```

State machines prevent impossible combinations and make transitions/test cases explicit.

## 15. Container/presenter pattern

A container integrates data and behavior; a presenter focuses on rendering and interaction.

Use when:

- the same UI can be reused with different data sources;
- a complex page needs smaller testable UI contracts;
- server state orchestration would clutter the template component.

Avoid creating empty wrapper components with no meaningful boundary.

## 16. Composition pattern

Prefer composition through:

- small UI components;
- directives;
- injectable policies;
- functional providers;
- content projection;
- pure helper functions;
- route configuration.

Deep base component inheritance often causes lifecycle coupling, unclear templates, and difficult testing.

## 17. Dependency inversion

High-level feature policy depends on an abstraction; infrastructure implements it.

Because TypeScript interfaces are erased, use an abstract class or injection token for DI.

```ts
export const AUDIT_SINK = new InjectionToken<AuditSink>('AUDIT_SINK');
```

Do not abstract every dependency preemptively. Introduce a port where variation, testing, or external-system isolation is real.

## 18. CQRS-inspired frontend separation

Commands change state; queries read projections. A frontend can benefit from separating:

- mutation commands;
- read models optimized for views;
- optimistic command state;
- real-time projection updates.

This does not require a large CQRS framework. It is a modeling technique.

## 19. Server-state architecture

A robust server-state layer should define:

- query key identity;
- deduplication;
- freshness/staleness;
- caching scope;
- invalidation after mutation;
- optimistic update and rollback;
- pagination/infinite query behavior;
- offline behavior if required;
- error/retry policy;
- observability.

Scattered HTTP calls in components usually fail these concerns.

## 20. Micro-frontends

Consider micro-frontends only when independent team ownership and release autonomy outweigh cost.

Costs:

- duplicated framework/runtime dependencies;
- cross-app routing and state complexity;
- design-system/version drift;
- authentication/session coordination;
- performance overhead;
- integration testing burden;
- local development complexity;
- distributed ownership of accessibility and observability.

A modular monolith is often the better starting point.

Possible approaches include build-time packages, runtime federation, web components, and route-level composition. Choose based on deployment independence, not fashion.

## 21. Monorepos and libraries

Libraries are appropriate for:

- design systems;
- stable domain contracts shared by multiple apps;
- infrastructure adapters;
- reusable utilities with clear ownership.

Avoid a library for every folder. Libraries create versioning and dependency surfaces.

Enforce dependency constraints such as:

```text
app-shell → feature → domain/ui/data-access
feature A ✕ feature B internals
shared-ui ✕ feature code
infrastructure ✕ page components
```

## 22. Design system architecture

A design system needs:

- tokens for color, spacing, typography, motion, elevation;
- accessible primitives;
- interaction and keyboard contracts;
- theming and RTL support;
- documentation and examples;
- visual regression tests;
- versioning and migration guidance;
- escape hatches without arbitrary inconsistency.

A UI library is not merely a collection of styled components.

## 23. Configuration architecture

Separate build-time and runtime configuration.

- Build-time configuration changes the compiled artifact.
- Runtime configuration allows one artifact to run in multiple environments.

Never place secrets in either frontend configuration; all delivered frontend code is inspectable.

Validate runtime configuration at startup and fail clearly.

## 24. Cross-cutting concerns

Centralize carefully:

- authentication/session;
- authorization presentation policy;
- error translation;
- correlation and tracing;
- feature flags;
- internationalization;
- logging/telemetry;
- configuration;
- HTTP transport policy.

Do not centralize feature-specific behavior merely because it is repeated twice.

## 25. Architecture anti-patterns

- type-based root folders only: `components`, `services`, `models`;
- every service `providedIn: 'root'`;
- shared module/library importing everything;
- backend DTO as universal frontend model;
- one global state store for all features;
- components calling multiple APIs and coordinating complex workflows directly;
- inheritance-heavy base components/services;
- circular feature imports;
- business logic in templates, pipes, directives, or interceptors;
- micro-frontends used to solve poor modularity;
- abstract factories/repositories with only one trivial pass-through implementation;
- path aliases mistaken for boundaries.

## 26. Architecture review checklist

For a new feature ask:

1. What business capability owns it?
2. What is its public API?
3. Which route/lazy boundary contains it?
4. What state exists and who owns each class?
5. Which data is backend DTO, domain model, form model, or view model?
6. What are the external adapters?
7. Which dependencies are application, route, component, or request scoped?
8. What failure and retry behavior is required?
9. What can be tested without rendering?
10. What are performance, security, accessibility, and observability requirements?
11. Can another feature import its internals?
12. How will it migrate when backend or framework contracts change?
