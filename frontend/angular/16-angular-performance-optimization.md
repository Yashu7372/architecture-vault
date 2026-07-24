# Angular Performance Optimization

![Twelve Angular performance optimization techniques](assets/angular-performance-12-techniques.svg)

Performance engineering is not a checklist of decorators and operators. It is a controlled loop:

1. measure a user-visible problem;
2. identify whether the constraint is network, JavaScript, rendering, memory, backend, or architecture;
3. change one relevant mechanism;
4. verify the improvement against the same scenario;
5. add a budget or regression test.

## 1. Define performance targets

Track at least:

- initial JavaScript and CSS transfer size;
- route-level lazy chunk size;
- LCP, INP and CLS;
- route navigation time;
- API latency and duplicate request count;
- long tasks and scripting time;
- list rendering time;
- memory growth after repeated navigation;
- hydration duration for SSR applications.

Do not optimize synthetic component creation while real users are waiting on a slow API or oversized image.

## 2. Measure before changing code

Use:

- Angular DevTools to inspect component rendering and change-detection work;
- Chrome Performance panel for long tasks, style, layout, paint and interaction delay;
- Network panel for waterfall, cache status, compression, duplicate calls and chunk loading;
- Memory panel for detached nodes, retained services, subscriptions and caches;
- bundle analysis and Angular budgets for payload regressions;
- real-user monitoring for production Web Vitals and route timings.

Create a reproducible scenario such as:

```text
Route: /orders
Dataset: 5,000 rows
Action: type 8 characters in search and select a row
Network: Fast 4G
Device: 4x CPU slowdown
Expected: no long task over 100 ms; visible result under 300 ms
```

## 3. Use OnPush as an explicit rendering boundary

```ts
import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

@Component({
  selector: 'app-order-row',
  template: `
    <button type="button" (click)="selected.emit(order().id)">
      {{ order().customerName }}
    </button>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OrderRow {
  readonly order = input.required<OrderSummary>();
  readonly selected = output<OrderId>();
}
```

Use immutable state transitions:

```ts
this.orders.update(items =>
  items.map(item => item.id === changed.id ? changed : item)
);
```

Avoid mutating a nested object while keeping the same reference. `OnPush` is not a fix for unclear ownership or hidden mutation.

## 4. Use signals for current and derived state

```ts
private readonly orders = signal<readonly OrderSummary[]>([]);
private readonly query = signal('');

readonly visibleOrders = computed(() => {
  const normalized = this.query().trim().toLowerCase();
  return normalized
    ? this.orders().filter(order => order.customerName.toLowerCase().includes(normalized))
    : this.orders();
});
```

Guidelines:

- keep writable signals private;
- expose readonly signals or computed values;
- derive instead of copying state through effects;
- avoid expensive computation inside frequently changing computed graphs;
- split unrelated state to reduce invalidation fan-out;
- scope stores to the route or feature when the state is not application-wide.

## 5. Track lists by stable identity

```html
@for (order of visibleOrders(); track order.id) {
  <app-order-row [order]="order" />
} @empty {
  <p>No orders found.</p>
}
```

A stable domain identifier lets Angular reuse DOM nodes and view instances. Avoid tracking by array index when rows can be inserted, deleted, filtered, or reordered.

For expensive row trees, also consider:

- paging;
- server-side filtering;
- virtual scrolling;
- progressively rendering detail;
- flattening unnecessary wrapper components.

## 6. Split routes by business feature

```ts
export const routes: Routes = [
  {
    path: 'orders',
    loadChildren: () => import('./features/orders/orders.routes')
      .then(module => module.ORDERS_ROUTES),
  },
  {
    path: 'reports',
    loadChildren: () => import('./features/reports/reports.routes')
      .then(module => module.REPORTS_ROUTES),
  },
];
```

A useful lazy boundary:

- represents a user-visible capability;
- has a stable public API;
- owns its route-level providers and state;
- does not import the internals of another feature;
- does not duplicate large shared libraries across chunks.

Avoid creating hundreds of tiny chunks without measuring request and execution overhead.

## 7. Defer noncritical template dependencies

```html
@defer (on viewport; prefetch on idle) {
  <app-analytics-chart [data]="chartData()" />
} @placeholder (minimum 200ms) {
  <app-chart-skeleton />
} @loading (after 150ms; minimum 300ms) {
  <app-spinner label="Loading chart" />
} @error {
  <app-inline-error message="Chart could not be loaded" />
}
```

Choose triggers based on user intent:

- `viewport`: below-the-fold sections;
- `interaction`: editors, dialogs or complex controls opened by the user;
- `hover`: pre-emptive loading for discoverable controls;
- `idle`: low-priority dependencies;
- `when`: explicit domain readiness.

Placeholders and loading UI must reserve enough space to avoid layout shift.

## 8. Virtualize large lists and grids

Rendering 20 visible rows is usually cheaper than keeping 20,000 live DOM rows.

Virtualization requires careful handling of:

- fixed or measurable row height;
- keyboard navigation;
- screen-reader behavior;
- sticky headers;
- dynamic row expansion;
- browser find behavior;
- selection state outside recycled row components.

Use server-side paging when the user does not need local access to the entire dataset.

## 9. Control high-frequency streams

Search:

```ts
readonly results$ = this.query.valueChanges.pipe(
  map(value => value.trim()),
  debounceTime(250),
  distinctUntilChanged(),
  switchMap(query => query.length < 2
    ? of([])
    : this.repository.search(query).pipe(
        catchError(error => {
          this.errors.report(error);
          return of([]);
        }),
      )),
);
```

Scroll or resize:

```ts
fromEvent(window, 'resize').pipe(
  auditTime(100),
  map(() => window.innerWidth),
  distinctUntilChanged(),
);
```

Operator choice is a concurrency decision:

| Requirement | Operator |
|---|---|
| newest result wins | `switchMap` |
| preserve order | `concatMap` |
| bounded parallel work | `mergeMap` with concurrency |
| ignore duplicate submit while active | `exhaustMap` |

## 10. Optimize images

```ts
import { NgOptimizedImage } from '@angular/common';

@Component({
  imports: [NgOptimizedImage],
  template: `
    <img
      ngSrc="/assets/hero.avif"
      width="1280"
      height="640"
      sizes="(max-width: 768px) 100vw, 1280px"
      priority
      alt="Operational dashboard overview"
    />
  `,
})
export class LandingHero {}
```

Rules:

- specify intrinsic width and height;
- mark only the actual LCP image as priority;
- lazy-load off-screen images;
- generate responsive sources;
- use modern formats where supported;
- do not ship desktop-size images to mobile;
- use CDN transformation for large image catalogs.

## 11. Use SSR and hydration when the product benefits

SSR is useful for:

- public content requiring search indexing;
- content-heavy landing or catalogue pages;
- reducing time to visible HTML on slower devices;
- consistent social previews.

Hydration reuses server-rendered DOM instead of rebuilding it. Incremental hydration can leave selected `@defer` regions inactive until a trigger occurs.

Avoid SSR merely because it is fashionable. Authenticated internal dashboards may receive more benefit from a small CSR shell, route splitting, caching, and fast APIs.

Hydration requires deterministic compatible server and browser output. Audit direct DOM manipulation, browser-only globals, random values and time-dependent rendering.

## 12. Enforce bundle budgets

```json
{
  "budgets": [
    {
      "type": "initial",
      "maximumWarning": "650kb",
      "maximumError": "800kb"
    },
    {
      "type": "anyComponentStyle",
      "maximumWarning": "8kb",
      "maximumError": "12kb"
    }
  ]
}
```

Inspect:

- duplicated framework or utility packages;
- importing an entire library for one function;
- CommonJS or side-effect-heavy dependencies;
- locale and timezone data;
- chart, editor, PDF and mapping libraries in the initial chunk;
- source maps and build mode;
- design-system barrel files that destroy lazy boundaries.

Every performance PR should include before/after bundle or runtime evidence.

## 13. Colocate state and shorten lifetime

Bad design:

```text
root store
  ├── every temporary filter
  ├── every open dialog
  ├── every edit draft
  └── every feature result forever
```

Better ownership:

```text
URL             shareable filters, paging, sort, selected identity
form            values, validation, dirty/pending state
component       local display state
route store     feature workflow and short-lived cache
root session    user, tenant, stable permissions
backend         durable source of truth
```

Route-scoped providers release state and subscriptions when the user leaves the feature.

## 14. Avoid expensive template work

Fragile:

```html
@for (order of calculateVisibleOrders(); track order.id) { ... }
```

Prefer precomputed state:

```ts
readonly visibleOrders = computed(() => applyFilters(this.orders(), this.filters()));
```

Also avoid:

- impure pipes for large transformations;
- getters that allocate arrays or objects;
- calling formatting libraries for every binding pass;
- nested loops in templates;
- repeated date parsing;
- DOM measurement inside loops;
- effects that trigger other effects.

## 15. Batch DOM reads and writes

Layout thrashing occurs when code alternates a layout read and a style write repeatedly.

Bad:

```ts
for (const element of elements) {
  const width = element.offsetWidth;
  element.style.width = `${width + 8}px`;
}
```

Better:

```ts
const widths = elements.map(element => element.offsetWidth);
elements.forEach((element, index) => {
  element.style.width = `${widths[index] + 8}px`;
});
```

Prefer Angular templates and CSS layout over imperative DOM measurement.

## 16. Prevent duplicate HTTP work

A cold `HttpClient` observable usually creates a request per subscription.

Do not scatter `shareReplay(1)` as an accidental cache. Create a repository cache with:

- explicit key including tenant/user/filter context;
- freshness and TTL policy;
- in-flight request deduplication;
- mutation invalidation;
- maximum size;
- logout clearing;
- metrics for hit, miss and stale refresh.

## 17. Memory discipline

Common leaks:

- root services retaining feature data indefinitely;
- global listeners not removed;
- third-party chart/editor instances not destroyed;
- manually created subscriptions without destruction binding;
- timers, observers and workers not closed;
- route reuse retaining large component trees;
- replay caches with unbounded history.

Use Angular destruction utilities where appropriate and explicitly clean up non-Angular resources.

## 18. Performance implementation checklist

Before release:

- [ ] critical route tested on representative device/network;
- [ ] no unexplained duplicate API calls;
- [ ] list tracking uses stable IDs;
- [ ] feature routes are lazy where useful;
- [ ] heavy optional UI uses `@defer` or dynamic loading;
- [ ] LCP image is correctly sized and prioritized;
- [ ] high-frequency streams are rate controlled;
- [ ] temporary state is not application-scoped;
- [ ] bundle budgets pass;
- [ ] memory remains stable after repeated navigation;
- [ ] performance evidence is attached to the change;
- [ ] production monitoring can detect regression.

## 19. Interview scenarios

Be ready to explain:

1. why `OnPush` does not mean a component renders only once;
2. how signals reduce unnecessary dependency fan-out;
3. why `track order.id` matters;
4. route lazy loading versus `@defer`;
5. `debounceTime` versus `auditTime`;
6. why `switchMap` is correct for search but dangerous for required writes;
7. SSR versus hydration versus incremental hydration;
8. how to find a frontend memory leak;
9. why state colocation is a performance technique;
10. how to prove an optimization worked.

## Official references

- Angular performance overview: <https://angular.dev/best-practices/performance>
- Angular runtime performance: <https://angular.dev/best-practices/runtime-performance>
- Deferrable views: <https://angular.dev/guide/templates/defer>
- Image optimization: <https://angular.dev/guide/image-optimization>
- Hydration: <https://angular.dev/guide/hydration>
- Incremental hydration: <https://angular.dev/guide/incremental-hydration>
