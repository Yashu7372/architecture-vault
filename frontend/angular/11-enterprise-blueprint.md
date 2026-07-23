# Enterprise Angular Application Blueprint

This reference architecture is for a large business application with authentication, feature teams, complex forms, real-time updates, shared UI, observability, and controlled deployment.

## 1. Architectural principles

1. Organize by business capability.
2. Keep feature internals private.
3. Make state ownership and lifetime explicit.
4. Separate transport DTOs from frontend domain/view models.
5. Prefer route-scoped feature state over application-wide state.
6. Keep global infrastructure small and stable.
7. Make failure, loading, security, accessibility, and telemetry part of feature design.
8. Enforce boundaries automatically.
9. Introduce distributed deployment only for organizational need.
10. Record major trade-offs as architecture decisions.

## 2. Reference repository structure

```text
apps/
  portal/
    src/app/
      core/
        auth/
        configuration/
        error-handling/
        feature-flags/
        http/
        observability/
        shell/
      features/
        orders/
        customers/
        reports/
        administration/
      app.config.ts
      app.routes.ts
      app.ts
libs/
  design-system/
    primitives/
    forms/
    layouts/
    feedback/
  domain/
    orders/
    customers/
  data-access/
    api-client/
    real-time/
  platform/
    auth/
    configuration/
    observability/
  testing/
    builders/
    fixtures/
    harnesses/
tools/
  architecture/
  migrations/
  ci/
docs/
  adr/
  runbooks/
```

A multi-project workspace or monorepo is optional. The same dependency model can exist in one Angular CLI project.

## 3. Feature anatomy

```text
features/orders/
  domain/
    order.ts
    order-id.ts
    order-policy.ts
    order.commands.ts
    order.events.ts
  data-access/
    order.dto.ts
    order.mapper.ts
    order.repository.ts
    http-order.repository.ts
    order-realtime.adapter.ts
  state/
    orders.store.ts
    orders.state.ts
    orders.selectors.ts
  feature-list/
    order-list-page.ts
  feature-detail/
    order-detail-page.ts
  feature-edit/
    order-edit-page.ts
  ui/
    order-card.ts
    order-status-badge.ts
    order-filter.ts
  orders.routes.ts
  orders.providers.ts
  public-api.ts
```

Small features should use fewer layers. Add structure to manage real complexity, not to satisfy a diagram.

## 4. Application bootstrap

Application-level providers should include only long-lived infrastructure:

```ts
export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(withInterceptors([
      correlationInterceptor,
      authenticationInterceptor,
      transportErrorInterceptor,
      telemetryInterceptor,
    ])),
    provideAppConfiguration(),
    provideAuthentication(),
    provideObservability(),
    provideGlobalErrorHandling(),
  ],
};
```

Do not register all feature stores globally.

## 5. Route composition

```ts
export const routes: Routes = [
  {
    path: '',
    component: AuthenticatedShell,
    canActivate: [authenticatedGuard],
    children: [
      {
        path: 'orders',
        loadChildren: () => import('./features/orders/orders.routes')
          .then(m => m.ORDERS_ROUTES),
      },
      {
        path: 'reports',
        loadChildren: () => import('./features/reports/reports.routes')
          .then(m => m.REPORT_ROUTES),
      },
    ],
  },
  {
    path: 'login',
    loadComponent: () => import('./core/auth/login-page')
      .then(m => m.LoginPage),
  },
  {
    path: '**',
    loadComponent: () => import('./core/shell/not-found-page')
      .then(m => m.NotFoundPage),
  },
];
```

Each top-level feature is lazy and can provide its own state/services.

## 6. Feature providers

```ts
export function provideOrdersFeature(): EnvironmentProviders {
  return makeEnvironmentProviders([
    OrdersStore,
    { provide: OrderRepository, useClass: HttpOrderRepository },
    OrderRealtimeAdapter,
  ]);
}
```

Attach at the route boundary so feature state is created when entered and released when the subtree is destroyed.

## 7. Data contracts

Maintain explicit models:

```text
OrderDto            backend transport representation
Order               frontend domain representation
OrderSummary        list/read model
OrderFormValue      UI form representation
UpdateOrderCommand  mutation intent
OrderEvent          real-time event representation
```

This prevents a backend schema change from spreading across every template.

## 8. API layer

Responsibilities:

- construct transport requests;
- validate/parse responses where required;
- map DTOs;
- apply endpoint-specific retry/caching policy;
- attach correlation and request identity;
- translate errors;
- expose domain-oriented operations.

Do not expose `HttpClient` directly to page components.

## 9. Real-time integration

Use a snapshot-plus-delta model:

1. load an authoritative snapshot;
2. subscribe using a cursor/version where supported;
3. apply idempotent ordered deltas;
4. detect gaps or stale versions;
5. refresh snapshot on inconsistency;
6. expose connection/recovery state;
7. unsubscribe when feature scope ends.

```ts
type VersionedEvent<T> = Readonly<{
  eventId: string;
  aggregateId: string;
  version: number;
  occurredAt: string;
  payload: T;
}>;
```

Do not merge real-time events without version/idempotency rules.

## 10. State design

Recommended split:

- URL: filters, paging, selected identity;
- form: edit draft and validation;
- route-scoped store: feature workflow and cached list/detail state;
- root session store: identity, tenant, permissions;
- backend: source of truth;
- real-time adapter: delta transport and reconnection state.

A feature store public API should expose readonly selectors/signals and intention-revealing methods.

## 11. Error architecture

Translate backend/platform errors into a stable frontend model:

```ts
type AppError =
  | NetworkError
  | AuthenticationError
  | AuthorizationError
  | ValidationError
  | ConflictError
  | NotFoundError
  | UnexpectedError;
```

Define:

- retry ownership;
- user message ownership;
- field error mapping;
- telemetry severity;
- correlation ID propagation;
- route/application fallback behavior.

## 12. Authentication architecture

Components:

- session bootstrap service;
- session store;
- authentication API adapter;
- route guard;
- HTTP credential attachment;
- 401 coordination;
- logout coordinator;
- permission evaluator;
- return URL validator.

Security requirements:

- backend-enforced authorization;
- secure cookie/token policy;
- no secrets in frontend config;
- no sensitive state in logs;
- CSRF policy aligned with session design;
- validated redirects.

## 13. Permission model

Prefer explicit permission policies:

```ts
export interface PermissionEvaluator {
  can(permission: Permission, context?: ResourceContext): boolean;
}
```

Use for presentation only. Backend remains authoritative.

Avoid scattering raw role string checks across templates.

## 14. Forms architecture

For complex forms separate:

- form construction;
- validators;
- form-to-command mapping;
- server error mapping;
- submission orchestration;
- unsaved-change policy;
- reference-data loading;
- child custom controls.

A page component can coordinate these through a feature facade/store.

## 15. Design system

Layers:

1. design tokens;
2. accessible primitives;
3. form controls;
4. layout primitives;
5. composite business-neutral patterns;
6. feature-specific UI outside the design system.

Each component requires:

- typed API;
- accessibility contract;
- component harness;
- visual stories/examples;
- unit/component tests;
- versioning/migration notes.

## 16. Observability architecture

Frontend telemetry should correlate with backend tracing.

Capture:

- application release and configuration version;
- route and user journey timing;
- HTTP method/template, status, duration, correlation/trace ID;
- unexpected errors and rejected promises;
- web vitals;
- real-time connection/reconnect/gap state;
- feature flag exposure;
- selected domain actions without sensitive payloads.

Do not use raw URLs containing identifiers as metric dimensions without cardinality control.

## 17. Logging policy

Define levels and payload rules:

- debug: local diagnostic, usually disabled in production;
- info: lifecycle and meaningful operational event;
- warn: recoverable abnormal condition;
- error: failed operation/unexpected defect.

Redact:

- tokens and cookies;
- passwords and personal data;
- full request/response bodies;
- payment/security data;
- unbounded objects.

## 18. Configuration

Load validated runtime configuration before protected features initialize.

```ts
interface RuntimeConfig {
  apiBaseUrl: string;
  telemetryEndpoint?: string;
  environmentName: string;
  featureFlags: Record<string, boolean>;
}
```

A runtime config file is public. It must not contain secrets.

## 19. Build and CI gates

Required gates:

- formatting and linting;
- strict TypeScript and template compilation;
- architecture dependency checks;
- unit/component tests;
- production build;
- bundle budgets;
- API contract checks;
- E2E smoke and critical workflows;
- accessibility checks;
- dependency and license scanning;
- SBOM/artifact metadata;
- deployment smoke test.

## 20. Deployment model

Preferred flow:

1. build immutable versioned assets;
2. publish to artifact storage/CDN;
3. deploy runtime config;
4. serve short-cached HTML and immutable hashed assets;
5. run smoke checks;
6. progressively expose release;
7. monitor errors, web vitals, and key journeys;
8. roll back or disable feature if thresholds fail.

## 21. Migration strategy

For legacy Angular applications:

1. inventory Angular/Node/TypeScript/RxJS versions and unsupported dependencies;
2. establish tests and production telemetry;
3. remove deprecated APIs incrementally;
4. use official migrations one major at a time where required;
5. move to standalone APIs feature by feature;
6. establish lazy route boundaries;
7. migrate local state toward signals where beneficial;
8. remove ZoneJS only after zoneless readiness testing;
9. modernize build/test tooling;
10. measure bundle/runtime behavior after each stage.

Do not combine framework upgrade, design-system replacement, state rewrite, and product redesign in one uncontrolled release.

## 22. Architecture decision records

Record decisions such as:

- signals/RxJS/state library responsibilities;
- SSR or CSR;
- cookie or token session model;
- monorepo strategy;
- design-system ownership;
- micro-frontends decision;
- runtime configuration;
- real-time transport;
- API client generation;
- testing and observability standards.

ADR format:

```text
Context
Decision
Alternatives considered
Consequences
Migration/rollback plan
Review date
```

## 23. Enterprise review questions

- Can a feature be removed without breaking unrelated features?
- Are provider lifetimes aligned with business state lifetimes?
- Can backend DTOs change without rewriting every component?
- Can a user reproduce/share important view state through the URL?
- Is duplicate or stale server data handled explicitly?
- Can frontend and backend traces be correlated?
- Can the team detect and roll back a bad release?
- Are accessibility contracts enforced in reusable components?
- Is authorization enforced without trusting the client?
- Are boundaries enforceable by tooling rather than convention alone?
