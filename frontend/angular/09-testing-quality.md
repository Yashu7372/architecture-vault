# Testing and Engineering Quality

Testing should provide fast, trustworthy evidence about behavior. The goal is not maximum test count or coverage percentage.

## 1. Test levels

| Level | Best for | Cost |
|---|---|---|
| Pure unit | reducers, mappers, validators, policies | lowest |
| Service/unit | orchestration with controlled collaborators | low |
| Component | template-class interaction, inputs, outputs, accessibility | medium |
| Integration | router, HTTP, forms, feature boundaries | medium |
| Contract | frontend/backend schema expectations | medium |
| E2E | critical user journeys in real browser | highest |
| Visual | design regressions across states/viewports | medium-high |
| Performance | budgets, interaction and rendering regressions | specialized |

Use the cheapest test that can reliably prove the behavior.

## 2. Test behavior, not implementation

Fragile test:

```ts
expect(component['loading']).toBeFalse();
expect(service.load).toHaveBeenCalledTimes(1);
```

Stronger test:

```ts
expect(screen.getByRole('heading', { name: 'Orders' })).toBeVisible();
expect(screen.getByText('No orders found')).toBeVisible();
```

Implementation details may change while behavior remains correct.

## 3. Current Angular unit testing

Current Angular documentation uses modern test tooling such as Vitest together with Angular's `TestBed`, `ComponentFixture`, and testing utilities. Match the framework-supported builder and project configuration for the selected version.

A component test should verify the template and class together when DOM behavior matters.

```ts
describe('UserCard', () => {
  it('emits selected user id', async () => {
    await TestBed.configureTestingModule({ imports: [UserCard] }).compileComponents();

    const fixture = TestBed.createComponent(UserCard);
    fixture.componentRef.setInput('user', { id: 'U1', name: 'Yaswanth' });

    const emitted: string[] = [];
    fixture.componentInstance.selected.subscribe(id => emitted.push(id));

    fixture.detectChanges();
    fixture.nativeElement.querySelector('button').click();

    expect(emitted).toEqual(['U1']);
  });
});
```

## 4. Pure logic tests

Extract business logic so it can be tested without Angular:

```ts
describe('calculateBaggageSeverity', () => {
  it('returns critical above threshold', () => {
    expect(calculateSeverity({ count: 31, windowMinutes: 30 })).toBe('critical');
  });
});
```

These tests are fast, deterministic, and easy to diagnose.

## 5. Signal tests

Test writable transitions and computed values directly:

```ts
it('filters orders by customer name', () => {
  const store = TestBed.inject(OrderListStore);
  store.setOrders([
    { id: '1', customerName: 'Alice' },
    { id: '2', customerName: 'Bob' },
  ]);
  store.setQuery('ali');

  expect(store.filtered().map(order => order.id)).toEqual(['1']);
});
```

For effects, test observable external behavior and cleanup rather than internal dependency tracking.

## 6. RxJS tests

Simple synchronous pipelines can be tested normally. Time-sensitive and concurrency behavior may use fake timers or marble-style tests.

Test:

- cancellation with `switchMap`;
- sequencing with `concatMap`;
- duplicate prevention with `exhaustMap`;
- error placement and stream survival;
- retry/backoff limits;
- subscription cleanup.

Do not overuse marble syntax for straightforward behavior if it reduces readability.

## 7. HTTP tests

Use Angular's HTTP testing utilities to assert request method, URL, headers, body, response mapping, and error behavior.

```ts
it('maps order DTO to domain model', () => {
  const repository = TestBed.inject(HttpOrderRepository);
  const http = TestBed.inject(HttpTestingController);

  let result: Order | undefined;
  repository.findById(asOrderId('O1')).subscribe(value => result = value ?? undefined);

  const request = http.expectOne('/api/orders/O1');
  expect(request.request.method).toBe('GET');
  request.flush({ order_id: 'O1', status_code: 'OPEN' });

  expect(result?.status).toBe('open');
});
```

Always call verification to detect unexpected pending requests.

## 8. Router tests

Use `RouterTestingHarness` or supported router testing APIs for:

- redirects;
- guards;
- route parameter behavior;
- nested route activation;
- lazy feature integration;
- resolver success/failure;
- navigation after commands.

Avoid mocking the entire router when actual routing behavior is the subject.

## 9. Form tests

Test form logic separately when possible:

- initial values;
- sync and async validators;
- cross-field validation;
- disabled/pending state;
- command mapping;
- server error mapping;
- reset behavior.

Render a component for label association, error announcements, focus, keyboard behavior, and custom control integration.

## 10. Component harnesses

Harnesses provide stable semantic test APIs for reusable UI components. They reduce dependence on internal markup and CSS selectors.

A design-system component should expose harness methods around user-observable behavior such as:

- reading value/state;
- opening/closing;
- selecting an option;
- entering text;
- querying validation/error state.

## 11. E2E testing

Use browser E2E tests for critical cross-system journeys:

- login/session restoration;
- search and navigation;
- create/edit workflows;
- authorization boundaries;
- payment or other business-critical submission;
- real-time updates;
- failure/retry/reconnect paths.

Prefer resilient locators based on role, accessible name, label, or dedicated stable test IDs when semantics are insufficient.

Do not rely on arbitrary sleeps. Wait for observable conditions.

## 12. API mocking strategy

Options:

- controlled test backend;
- network interception in E2E;
- mock service worker-style interception;
- contract-generated fixtures.

Fixtures must represent real schema and edge cases. Keep them versioned and reusable.

Test at least:

- happy path;
- empty data;
- validation error;
- unauthorized/forbidden;
- conflict;
- transient failure;
- slow response;
- malformed/partial response where boundary validation exists.

## 13. Contract testing

Frontend and backend can drift despite compiling independently.

Use:

- OpenAPI schema validation/generation;
- consumer-driven contracts where useful;
- runtime schema tests;
- shared fixture validation;
- compatibility checks in CI.

Generated clients reduce duplication but do not replace domain mapping or compatibility strategy.

## 14. Accessibility testing

Automated tools detect only part of accessibility problems.

Automate:

- common semantic/ARIA violations;
- label associations;
- focusable hidden elements;
- color-contrast checks where supported;
- page title and landmark presence.

Manually test:

- keyboard-only flow;
- focus order and restoration;
- screen-reader announcements;
- zoom/reflow;
- high contrast and reduced motion;
- error recovery.

## 15. Visual regression

Capture stable component/page states:

- default;
- hover/focus/disabled;
- error/loading/empty;
- long text and localization;
- RTL;
- mobile/tablet/desktop;
- high contrast/theme variants.

Control fonts, animation, time, data, and viewport to reduce noise.

## 16. Performance tests

Track budgets for:

- initial and lazy chunks;
- route navigation;
- LCP, INP, CLS;
- large list rendering;
- memory growth during repeated navigation;
- duplicate API requests;
- SSR response/hydration timing.

A performance test should compare a baseline and fail on meaningful regression, not unstable absolute timing alone.

## 17. Test data builders

Avoid huge inline objects:

```ts
function buildOrder(overrides: Partial<Order> = {}): Order {
  return {
    id: asOrderId('O1'),
    status: 'open',
    customerName: 'Default Customer',
    total: { amountMinor: 1000, currency: 'AED' },
    ...overrides,
  };
}
```

Use explicit builders for valid domain defaults. Add separate invalid DTO fixtures for boundary tests.

## 18. Mocking guidance

Mock external collaborators, not every internal function.

Good mocking targets:

- HTTP/backend ports;
- time and randomness;
- browser APIs;
- analytics and third-party SDKs;
- feature flags.

Over-mocking creates tests that verify the test setup instead of integration behavior.

## 19. Time-dependent code

Inject a clock abstraction:

```ts
export abstract class Clock {
  abstract now(): Date;
}

@Injectable({ providedIn: 'root' })
export class SystemClock implements Clock {
  now(): Date {
    return new Date();
  }
}
```

Tests can provide a fixed clock. This avoids flaky timing and scattered mocking of global time.

## 20. Quality gates

Recommended CI sequence:

1. dependency install using lockfile;
2. formatting/linting;
3. TypeScript and Angular template compilation;
4. unit/component tests;
5. architecture/dependency rule checks;
6. production build and bundle budgets;
7. contract checks;
8. E2E critical journeys;
9. accessibility/visual/performance checks as appropriate;
10. artifact and source-map publication with controlled access.

## 21. Code review checklist

Reviewers should ask:

- Is ownership clear?
- Are inputs and API data typed and validated?
- Is there duplicated state?
- Is async concurrency intentional?
- Can subscriptions/resources leak?
- Are provider scopes correct?
- Are loading, empty, error, and retry states present?
- Does the route create an appropriate lazy boundary?
- Is DOM interaction accessible?
- Are tests at the correct level?
- Is sensitive data logged or stored?
- Does the change create bundle or rendering regressions?

## 22. Common testing anti-patterns

- testing private methods;
- snapshots as the only assertion;
- selectors coupled to CSS implementation;
- mocking Angular internals;
- ignoring async completion;
- arbitrary sleeps in E2E;
- one giant end-to-end test for every behavior;
- 100% coverage as the goal;
- tests sharing mutable global state;
- production code altered only to satisfy tests without design value;
- no tests for failure, cancellation, or empty states.
