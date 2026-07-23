# Angular Platform Features

This chapter covers the framework features used in most real applications and the design decisions behind them.

## 1. Component contracts

A component API consists of:

- inputs;
- outputs;
- projected content;
- injectable contracts where appropriate;
- public methods only when direct imperative control is justified.

Prefer domain-specific contracts:

```ts
readonly order = input.required<OrderSummary>();
readonly cancelRequested = output<OrderId>();
```

Avoid outputs such as `clicked` when the meaningful event is `cancelRequested`.

## 2. Input transformation and validation

Input transforms are useful for small representation normalization. They are not a substitute for complex validation or domain mapping.

Treat inputs as immutable from the child's perspective. A child that mutates an input object creates hidden shared state.

## 3. Outputs and event design

Outputs are synchronous event notifications unless surrounding code introduces async behavior. Emit facts or user intents, not commands that force a parent to understand child implementation details.

Avoid event chains that bounce through many component levels. For deeper feature communication, use a clearly scoped feature state/facade or route state.

## 4. Content projection

Use projection for flexible layout components:

```html
<app-panel>
  <h2 panel-title>Payment details</h2>
  <form>...</form>
  <button panel-actions>Submit</button>
</app-panel>
```

Projection is appropriate for presentational composition. Avoid creating highly magical components with many selectors, hidden assumptions, and difficult accessibility behavior.

## 5. Directives

Use attribute directives for reusable DOM behavior that does not require a separate visual component.

Good cases:

- permission-aware presentation where backend authorization still exists;
- focus behavior;
- intersection observation;
- reusable keyboard interaction;
- analytics instrumentation;
- host class/state behavior.

Do not hide core business logic in directives attached throughout templates.

## 6. Pipes

Use pure pipes for deterministic display transformation.

```ts
@Pipe({ name: 'initials', standalone: true, pure: true })
export class InitialsPipe implements PipeTransform {
  transform(name: string): string {
    return name
      .split(/\s+/)
      .filter(Boolean)
      .map(part => part[0]?.toUpperCase())
      .join('');
  }
}
```

Do not use pipes for side effects, network calls, or state mutation.

## 7. Router configuration

A scalable route tree should express feature boundaries.

```ts
export const ORDERS_ROUTES: Routes = [
  {
    path: '',
    providers: [provideOrdersFeature()],
    children: [
      {
        path: '',
        loadComponent: () => import('./feature-list/order-list-page')
          .then(m => m.OrderListPage),
      },
      {
        path: ':orderId',
        loadComponent: () => import('./feature-detail/order-detail-page')
          .then(m => m.OrderDetailPage),
      },
    ],
  },
];
```

Use route-level providers for state and services whose lifetime should match the feature route subtree.

## 8. Route parameters and query parameters

Use path parameters for resource identity and query parameters for optional view/filter/sort/pagination state.

Examples:

```text
/orders/ORD-100
/orders?status=open&page=2&sort=createdAt,desc
```

URL state should be serializable, bookmarkable, and backward-compatible where practical.

## 9. Guards

Common guard responsibilities:

- authenticated session prerequisite;
- coarse permission-based navigation UX;
- unsaved-change confirmation;
- feature availability;
- redirect decisions.

A guard does not secure data. The backend must authorize every protected operation.

Functional guard example:

```ts
export const authenticatedGuard: CanActivateFn = (_, state) => {
  const session = inject(SessionStore);
  const router = inject(Router);

  return session.isAuthenticated()
    ? true
    : router.createUrlTree(['/login'], {
        queryParams: { returnUrl: state.url },
      });
};
```

Prefer returning a `UrlTree`/redirect result over manually navigating and returning false.

## 10. Resolvers

Resolvers can load data before route activation. Use them when the route cannot render meaningfully without the data or when route-level error handling is desirable.

Do not resolve every request automatically. Blocking navigation can worsen perceived performance. Skeleton states and component-driven loading may be better for secondary data.

## 11. Router events and cancellation

Navigation can be superseded. Avoid starting unmanaged side effects from route event subscriptions.

Use router testing harnesses and integration tests for redirects, guards, parameter handling, and nested activation.

## 12. Reactive forms

Reactive forms model form state explicitly.

```ts
interface ProfileFormModel {
  name: FormControl<string>;
  email: FormControl<string>;
  preferences: FormGroup<{
    notifications: FormControl<boolean>;
  }>;
}
```

Typed construction:

```ts
readonly form = new FormGroup<ProfileFormModel>({
  name: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
  email: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.email] }),
  preferences: new FormGroup({
    notifications: new FormControl(true, { nonNullable: true }),
  }),
});
```

## 13. Form validation

Validation layers:

1. field format and required rules;
2. cross-field rules;
3. async uniqueness or remote validation where necessary;
4. backend/domain validation on submission.

Cross-field validator:

```ts
const dateRangeValidator: ValidatorFn = control => {
  const start = control.get('start')?.value as Date | null;
  const end = control.get('end')?.value as Date | null;
  return start && end && start > end ? { invalidDateRange: true } : null;
};
```

Async validators require cancellation/debouncing and clear pending UI. Do not call a backend on every keypress without policy.

## 14. Dynamic forms

Dynamic forms need a schema, component registry, validation model, conditional visibility rules, and serialization contract.

Avoid a single universal form renderer that becomes an untyped programming language. Keep supported field types and behavior intentionally constrained.

## 15. Custom form controls

Implement a custom value accessor when a reusable component must integrate as an Angular form control.

Requirements:

- value write;
- change callback;
- touched callback;
- disabled state;
- correct accessible labeling and keyboard behavior;
- no feedback loop when programmatic values are written.

Complex controls may also expose validation.

## 16. Signal forms

Current Angular documentation includes signal-oriented form APIs. Evaluate maturity and support status for the selected Angular version before standardizing enterprise use.

The architectural principles remain:

- form value is not the same as domain entity;
- validation should be testable independently;
- submission is an explicit state machine;
- server errors must map to global or field-level presentation;
- accessibility is part of the control contract.

## 17. HTTP client

Use typed methods, but remember generic types are compile-time expectations, not runtime validation.

```ts
create(command: CreateOrderCommand): Observable<Order> {
  return this.http
    .post<OrderDto>('/api/orders', toDto(command))
    .pipe(map(toOrder));
}
```

Separate:

- transport DTO;
- mapping;
- domain/view model;
- error translation;
- cache policy.

## 18. Interceptors

Typical interceptor order concerns:

- correlation/tracing;
- authentication headers;
- request normalization;
- retry for eligible requests;
- error translation;
- timing/observability.

Be explicit about ordering because interceptors wrap one another.

Never:

- retry every request blindly;
- refresh tokens recursively without coordination;
- swallow errors;
- log sensitive headers or bodies;
- put feature-specific state changes into a global interceptor.

## 19. Authentication flow

A robust flow handles:

- bootstrap session restoration;
- authenticated and anonymous routes;
- token/cookie expiry;
- coordinated refresh if token-based;
- logout across tabs where required;
- redirect after login;
- permission refresh;
- API 401/403 differences;
- XSS/CSRF threat model.

Prefer secure, HTTP-only cookie sessions when backend and deployment architecture support them. If tokens are exposed to JavaScript, minimize lifetime and storage exposure.

## 20. Error handling

Create a stable application error model:

```ts
type AppError =
  | { kind: 'network'; retryable: boolean }
  | { kind: 'unauthorized' }
  | { kind: 'forbidden' }
  | { kind: 'validation'; fields: Record<string, readonly string[]> }
  | { kind: 'conflict'; message: string }
  | { kind: 'unexpected'; correlationId?: string };
```

The component should not parse arbitrary backend error shapes.

## 21. Internationalization

Plan for:

- translation extraction and loading;
- locale-aware date/number/currency formatting;
- pluralization;
- right-to-left layout;
- text expansion;
- localizable validation and server messages;
- URL strategy and SEO for localized SSR pages.

Do not concatenate translated fragments into sentences.

## 22. Browser APIs

Wrap browser-only APIs when SSR or testing requires an abstraction.

Examples:

- local storage;
- window/document access;
- observers;
- media queries;
- geolocation;
- notifications;
- workers.

Use Angular platform checks and injection abstractions rather than scattering `typeof window` throughout features.

## 23. Web workers

Workers are appropriate for CPU-heavy isolated computations that can be serialized. They do not make network waits faster and cannot directly manipulate the DOM.

Consider:

- message serialization cost;
- cancellation;
- error handling;
- worker lifecycle;
- browser support;
- test strategy.

## 24. Dynamic component rendering

Use dynamic rendering for controlled registries such as dashboards, dialogs, plugin slots, or schema-backed fields.

Avoid accepting arbitrary component names/configuration from untrusted sources. Define a whitelist registry and typed configuration contract.

## 25. Feature checklist

For every feature confirm:

- route ownership and lazy boundary;
- state owner and lifetime;
- loading/empty/error/retry behavior;
- API mapping and validation;
- form submission state machine;
- permission UX and backend enforcement;
- accessibility and keyboard behavior;
- tests for routing, form, and HTTP behavior;
- observable/signal cleanup;
- performance and bundle impact;
- analytics/observability requirements.
