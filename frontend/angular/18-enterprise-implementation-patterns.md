# Enterprise Angular Implementation Patterns

![Twelve enterprise Angular implementation patterns](assets/angular-enterprise-12-patterns.svg)

Enterprise Angular architecture should reduce ambiguity about ownership, state lifetime, dependencies, security, failure and deployment. It should not add layers merely to make the repository look sophisticated.

## 1. Feature boundaries by business capability

Prefer:

```text
features/
  orders/
  reports/
  customers/
  administration/
```

Avoid primary organization by technical type:

```text
components/
services/
models/
guards/
pipes/
```

A feature owns:

- routes;
- pages and business-neutral local UI;
- use cases/workflows;
- feature state;
- API ports and adapters;
- domain/view models;
- tests;
- its public entry point.

A feature should not import another feature's internal files.

## 2. Route-scoped providers

Feature state should often live for the route subtree rather than for the whole application.

```ts
export function provideOrdersFeature(): EnvironmentProviders {
  return makeEnvironmentProviders([
    OrdersStore,
    OrdersFacade,
    { provide: OrderRepository, useClass: HttpOrderRepository },
    OrderRealtimeAdapter,
  ]);
}
```

```ts
export const ORDERS_ROUTES: Routes = [
  {
    path: '',
    providers: [provideOrdersFeature()],
    children: [
      { path: '', component: OrderListPage },
      { path: ':id', component: OrderDetailPage },
    ],
  },
];
```

Benefits:

- feature stores are released when the route subtree is destroyed;
- tests can replace providers at one boundary;
- tenant/flight/customer context can be scoped correctly;
- root DI remains limited to stable platform services.

## 3. Facade/application layer

Use a facade when pages would otherwise coordinate many repositories, state transitions, dialogs, router calls and side effects.

```ts
@Injectable()
export class OrdersFacade {
  private readonly store = inject(OrdersStore);
  private readonly repository = inject(OrderRepository);
  private readonly router = inject(Router);

  readonly orders = this.store.orders;
  readonly status = this.store.status;
  readonly error = this.store.error;

  load(query: OrderQuery): void {
    this.store.loading(query);

    this.repository.search(query).subscribe({
      next: result => this.store.loaded(result),
      error: error => this.store.failed(toAppError(error)),
    });
  }

  open(id: OrderId): Promise<boolean> {
    return this.router.navigate(['/orders', id]);
  }
}
```

A facade is useful when it represents application use cases. A facade that merely forwards every service method adds little value.

## 4. Ports and adapters

Define application-facing contracts:

```ts
export abstract class OrderRepository {
  abstract search(query: OrderQuery): Observable<Page<OrderSummary>>;
  abstract findById(id: OrderId): Observable<Order | null>;
  abstract update(command: UpdateOrderCommand): Observable<Order>;
}
```

Infrastructure adapter:

```ts
@Injectable()
export class HttpOrderRepository implements OrderRepository {
  private readonly http = inject(HttpClient);
  private readonly mapper = inject(OrderMapper);

  search(query: OrderQuery): Observable<Page<OrderSummary>> {
    return this.http.get<OrderPageDto>('/bff/orders', {
      params: toHttpParams(query),
    }).pipe(map(dto => this.mapper.toSummaryPage(dto)));
  }
}
```

Adapters can be replaced for tests, offline mode, migration or alternate transports without rewriting pages.

## 5. Backend for Frontend

The BFF is valuable when the frontend requires:

- server-side OAuth/token handling;
- UI-specific API composition;
- protocol translation;
- multiple downstream APIs;
- consistent error/session policy;
- same-origin real-time and file operations;
- protection from exposing internal topology to the browser.

Keep BFF operations explicit. It must not become an unrestricted generic proxy.

See [Enterprise Authentication, SSO, and BFF](17-authentication-sso-bff.md).

## 6. Typed boundary models

Separate representations:

```text
OrderDto            backend wire contract
Order               frontend domain model
OrderSummary        list projection
OrderFormValue      editable UI representation
UpdateOrderCommand  mutation intent
OrderEvent          real-time message contract
```

```ts
interface OrderDto {
  order_id: string;
  status_code: 'O' | 'C' | 'X';
  amount_minor: number;
  currency_code: string;
}

interface Order {
  readonly id: OrderId;
  readonly status: 'open' | 'closed' | 'cancelled';
  readonly total: Money;
}
```

Mapping protects the UI from transport naming, nullable legacy fields and backend release changes.

For untrusted/external data, add runtime validation at the boundary. TypeScript types alone do not validate JSON.

## 7. Explicit state ownership

Classify every state value:

| State | Owner |
|---|---|
| route identity, filters, paging | URL/router |
| field values and validity | form |
| expanded row, open panel | component |
| feature workflow and cache | route-scoped feature store |
| identity, tenant and stable permissions | root session store |
| durable truth | backend |
| temporary server cache | repository with freshness policy |

Duplicating one filter in URL, component and global store creates synchronization bugs.

Prefer intention-revealing transitions:

```ts
store.searchRequested(query);
store.searchSucceeded(result);
store.searchFailed(error);
```

Avoid exposing writable signals or subjects publicly.

## 8. Snapshot plus delta for real-time screens

Real-time transport should update an authoritative read model rather than becoming the only source of truth.

```text
1. GET authoritative snapshot with version/cursor.
2. Subscribe to deltas from that position.
3. Reject duplicate event IDs.
4. Apply only expected next versions.
5. Detect gaps or stale state.
6. Reload snapshot when consistency cannot be proven.
7. Expose reconnect/recovery state to the UI.
```

```ts
type VersionedEvent<T> = Readonly<{
  eventId: string;
  aggregateId: string;
  version: number;
  occurredAt: string;
  payload: T;
}>;
```

The frontend adapter should handle:

- bounded reconnect backoff with jitter;
- cursor or last-event ID resumption;
- ordering by domain version, not assumed network order;
- idempotency;
- tenant and active-route scoping;
- snapshot refresh on gaps;
- cleanup when the route ends.

## 9. Stable application error model

Translate transport/platform errors into product-level errors:

```ts
type AppError =
  | { kind: 'network'; retryable: true; correlationId?: string }
  | { kind: 'authentication' }
  | { kind: 'authorization'; permission?: string }
  | { kind: 'validation'; fields: Readonly<Record<string, string>> }
  | { kind: 'conflict'; currentVersion?: string }
  | { kind: 'not-found' }
  | { kind: 'rate-limited'; retryAfterSeconds?: number }
  | { kind: 'unexpected'; correlationId?: string };
```

Define ownership for:

- retry;
- user message;
- field mapping;
- telemetry severity;
- navigation fallback;
- conflict resolution;
- support correlation ID.

Do not show backend stack traces or raw status bodies to users.

## 10. Runtime configuration

Build one immutable artifact and supply validated public configuration at deployment.

```ts
export interface RuntimeConfig {
  readonly apiBaseUrl: string;
  readonly environmentName: string;
  readonly release: string;
  readonly telemetryEndpoint?: string;
  readonly featureFlags: Readonly<Record<string, boolean>>;
}
```

Validation:

```ts
function parseRuntimeConfig(value: unknown): RuntimeConfig {
  // Use a runtime schema or explicit checks.
  // Throw a controlled startup error when required values are invalid.
  return runtimeConfigSchema.parse(value);
}
```

Rules:

- runtime config is public and must contain no secrets;
- validate before protected routes initialize;
- include configuration version in telemetry;
- prevent arbitrary API origins unless explicitly allowed;
- distinguish release artifact from environment configuration.

## 11. Observability as architecture

Instrument the user journey, not only console errors.

Capture:

- route transition start/end/failure;
- API operation template, status and duration;
- correlation/trace identifiers;
- application release and configuration version;
- Web Vitals;
- real-time reconnect/gap state;
- global errors and rejected promises;
- feature flag exposure;
- major domain actions without sensitive payloads.

Use low-cardinality names:

```text
Good:  /orders/:id
Bad:   /orders/9328201837
```

Redact tokens, cookies, personal data and full response bodies.

## 12. Automated dependency rules

Architecture must be enforceable in CI.

Example policy:

```text
feature page may import:
  feature application/state
  feature UI
  shared design system

feature domain may import:
  no Angular HTTP/router/browser infrastructure

feature A may import feature B only through B/public-api

data-access may implement domain/application ports

shared UI may not import business features
```

Use lint rules, dependency graph tools or custom scripts to fail builds on forbidden direction.

A barrel file is not automatically a public API. Define intentional exports.

## 13. CQRS-inspired frontend separation

Do not reproduce backend CQRS mechanically, but separate query/read concerns from commands when workflows differ.

```ts
interface OrdersQueryPort {
  search(query: OrderQuery): Observable<Page<OrderSummary>>;
}

interface OrderCommandPort {
  update(command: UpdateOrderCommand): Observable<CommandReceipt>;
}
```

Useful when:

- read models are optimized projections;
- commands are asynchronous;
- optimistic updates need operation IDs;
- status arrives through real-time events;
- permissions differ between query and command paths.

## 14. State machine for complex workflows

Boolean combinations become invalid quickly:

```ts
loading = true;
saving = true;
completed = true;
error = ...;
```

Prefer explicit states:

```ts
type EditWorkflow =
  | { state: 'loading' }
  | { state: 'ready'; order: Order; form: OrderFormValue }
  | { state: 'saving'; order: Order; commandId: string }
  | { state: 'conflict'; local: OrderFormValue; server: Order }
  | { state: 'saved'; order: Order }
  | { state: 'failed'; error: AppError };
```

State machines help when there are retries, approvals, conflicts, step-up authentication, cancellation or asynchronous command completion.

## 15. Strategy pattern for variable behavior

```ts
export interface ExportStrategy {
  supports(format: ExportFormat): boolean;
  export(request: ExportRequest): Observable<ExportResult>;
}
```

Use strategies for:

- report formats;
- tenant-specific rules;
- authentication providers;
- feature rollout variants;
- data-source selection;
- rendering adapters.

Avoid giant `switch` statements spread across components.

## 16. Adapter anti-corruption layer for legacy APIs

Legacy transport model:

```ts
interface LegacyFlightDto {
  FLT_NO: string;
  STD: string | null;
  BAG_CNT: string;
  SEEN_FLG: 'Y' | 'N' | null;
}
```

Frontend model:

```ts
interface FlightSummary {
  readonly flightNumber: FlightNumber;
  readonly scheduledDeparture: Instant | null;
  readonly bagCount: number;
  readonly seen: boolean;
}
```

The mapper owns legacy defaults and conversion errors. Templates should not know that counts arrived as strings or flags as `Y/N`.

## 17. Design-system layering

```text
1. design tokens
2. accessible primitives
3. form controls
4. layout primitives
5. feedback and overlays
6. business-neutral composites
7. feature-specific UI outside the design system
```

Each reusable component requires:

- typed API;
- accessibility contract;
- keyboard behavior;
- visual states;
- harness or stable test API;
- examples/stories;
- migration/versioning policy.

Do not move business rules into the design system.

## 18. Micro-frontends decision

Use micro-frontends only when independent team ownership and deployment justify distributed complexity.

Costs include:

- duplicate dependencies;
- design-system drift;
- routing and authentication coordination;
- shared-state ambiguity;
- operational overhead;
- cross-application testing;
- version compatibility.

Before choosing micro-frontends, attempt:

- feature boundaries in one workspace;
- ownership rules;
- lazy routes;
- independent library packages;
- release flags;
- enforced dependency direction.

A modular monolith frontend is often the stronger default.

## 19. Bounded cache pattern

A server-data cache should define:

```text
key             tenant + user/permission + query identity
freshness       when data may be served without validation
TTL             maximum retained age
in-flight       request deduplication
invalidation    mutations and events
size            bounded entries/memory
logout          user-specific data cleared
observability   hit/miss/stale/error metrics
```

Do not use `shareReplay(1)` as a permanent hidden cache with no invalidation policy.

## 20. Optimistic command pattern

```text
1. assign operation/command ID;
2. preserve previous state/version;
3. update local read model;
4. submit idempotent command;
5. reconcile immediate response or later event;
6. rollback or enter conflict state on failure;
7. ignore duplicate/out-of-order confirmations.
```

Use only when the user benefit exceeds conflict complexity.

## 21. Feature public API

```ts
// features/orders/public-api.ts
export { ORDERS_ROUTES } from './orders.routes';
export type { OrderId, OrderSummary } from './domain/order';
```

Do not export internal stores, adapters and implementation components unless another bounded context truly needs the contract.

## 22. Application bootstrap boundary

Root providers should be small and stable:

```ts
export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(withInterceptors([
      correlationInterceptor,
      authenticationFailureInterceptor,
      transportErrorInterceptor,
      telemetryInterceptor,
    ])),
    provideRuntimeConfiguration(),
    provideAuthentication(),
    provideObservability(),
    provideGlobalErrorHandling(),
  ],
};
```

Avoid registering every feature store and repository in root.

## 23. Secure file download pattern

For protected generated files:

```text
Angular requests export command from BFF.
BFF authorizes request and starts generation.
Angular receives operation ID.
Progress arrives through polling or real-time event.
BFF returns a short-lived same-origin download endpoint.
Download endpoint rechecks session and authorization.
Response uses safe Content-Disposition and content type.
```

Avoid exposing permanent storage URLs or access tokens in query strings.

## 24. Offline and reconnect pattern

Classify operations:

- safe local draft;
- retryable idempotent query;
- queued idempotent command;
- non-repeatable sensitive command;
- real-time state that requires snapshot refresh.

Show connectivity and staleness explicitly. Never claim a command succeeded until the authoritative system confirms it.

## 25. Migration/strangler pattern

For a legacy Angular application:

1. add production telemetry and tests;
2. define target feature boundaries;
3. introduce a shell and lazy routes;
4. create ports around legacy services;
5. migrate one capability at a time;
6. map legacy DTOs at the edge;
7. move state from root to route scope;
8. replace old UI components behind adapters;
9. remove old path only after behavior comparison;
10. keep framework upgrade separate from broad product redesign.

## 26. Architecture decision record

```text
Title
Status
Context
Decision
Alternatives considered
Consequences
Security/privacy impact
Migration and rollback
Validation evidence
Review date
```

Record decisions for:

- BFF versus browser-only OAuth;
- state-library responsibilities;
- SSR/CSR;
- monorepo structure;
- micro-frontends;
- design-system ownership;
- real-time transport;
- API client generation;
- runtime configuration;
- testing and observability standards.

## 27. Enterprise implementation checklist

- [ ] features map to business capabilities;
- [ ] temporary state has bounded lifetime;
- [ ] DTOs are not used directly by every template;
- [ ] API calls are behind ports/repositories;
- [ ] workflows have one clear coordinator;
- [ ] errors have stable product semantics;
- [ ] authentication and authorization boundaries are explicit;
- [ ] real-time updates have snapshot, version and recovery rules;
- [ ] runtime configuration is validated and secret-free;
- [ ] telemetry correlates frontend and backend behavior;
- [ ] dependency rules fail CI when violated;
- [ ] design-system components include accessibility contracts;
- [ ] caches have freshness and invalidation policies;
- [ ] major decisions have ADRs and rollback plans.

## 28. Interview system-design scenario

**Question:** Design an Angular enterprise portal with SSO, orders, reporting, real-time updates and multiple teams.

Strong answer structure:

1. same-origin Angular + BFF deployment;
2. OIDC Authorization Code + PKCE at BFF;
3. secure cookie session; no tokens in browser;
4. feature-oriented lazy routes;
5. route-scoped stores/facades;
6. DTO mapping through repository adapters;
7. URL/form/feature/session/server state ownership;
8. snapshot-plus-delta real-time projections;
9. server-enforced resource authorization;
10. stable error and retry model;
11. design-system and accessibility contracts;
12. bundle, test, architecture and contract CI gates;
13. frontend/backend trace correlation;
14. incremental migration and rollback.

The strongest answer explains trade-offs and failure handling, not only folder names.
