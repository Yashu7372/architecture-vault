# Angular Cheat Sheets and Official References

Last reviewed: 23 July 2026. Angular v22 is the active major release in the official release table. Recheck support, compatibility, and API stability before upgrading production applications.

---

# 1. Angular CLI

```bash
# Create strict standalone app
npx @angular/cli@latest new my-app --standalone --routing --style=scss --strict

# Development
npm start
npx ng serve

# Generate
npx ng g component features/orders/ui/order-card
npx ng g service features/orders/data-access/order-api
npx ng g guard core/auth/authenticated --functional
npx ng g interceptor core/http/correlation --functional

# Build and inspect
npx ng build
npx ng build --configuration production
npx ng version
npx ng update
```

Use a Node.js version supported by the chosen Angular release.

---

# 2. Component

```ts
@Component({
  selector: 'app-order-card',
  standalone: true,
  imports: [CurrencyPipe],
  templateUrl: './order-card.html',
  styleUrl: './order-card.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OrderCard {
  readonly order = input.required<OrderSummary>();
  readonly selected = output<OrderId>();

  readonly formattedStatus = computed(() =>
    this.order().status.replaceAll('_', ' ')
  );
}
```

---

# 3. Template

```html
@if (loading()) {
  <app-spinner />
} @else if (error(); as error) {
  <app-error [error]="error" (retry)="reload()" />
} @else {
  @for (order of orders(); track order.id) {
    <app-order-card
      [order]="order"
      (selected)="openOrder($event)"
    />
  } @empty {
    <p>No orders found.</p>
  }
}
```

Bindings:

```html
{{ value }}
[property]="expression"
(event)="handler($event)"
[(value)]="model"
[class.active]="active()"
[style.width.px]="width()"
[attr.aria-label]="label()"
```

---

# 4. Signals

```ts
const count = signal(0);
const doubled = computed(() => count() * 2);

count.set(1);
count.update(value => value + 1);

const readonlyCount = count.asReadonly();
```

Rules:

- private writable, public readonly;
- computed for derivation;
- effect for external synchronization;
- avoid effect-based state copying;
- update immutably.

---

# 5. Dependency injection

```ts
const API_URL = new InjectionToken<string>('API_URL');

@Injectable({ providedIn: 'root' })
class UserApi {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = inject(API_URL);
}
```

Provider forms:

```ts
{ provide: TOKEN, useValue: value }
{ provide: PORT, useClass: Adapter }
{ provide: ALIAS, useExisting: EXISTING }
{ provide: TOKEN, useFactory: factory, deps: [DEPENDENCY] }
```

Scopes:

- root/application;
- route/environment;
- component/element.

---

# 6. Router

```ts
export const routes: Routes = [
  {
    path: 'orders',
    providers: [OrdersStore],
    loadChildren: () => import('./features/orders/orders.routes')
      .then(m => m.ORDERS_ROUTES),
  },
  {
    path: 'login',
    loadComponent: () => import('./core/auth/login-page')
      .then(m => m.LoginPage),
  },
  { path: '**', redirectTo: '' },
];
```

Use path parameters for identity and query parameters for filters/sort/pagination.

---

# 7. Reactive forms

```ts
readonly form = this.fb.nonNullable.group({
  name: ['', [Validators.required, Validators.maxLength(100)]],
  email: ['', [Validators.required, Validators.email]],
});

submit(): void {
  if (this.form.invalid) {
    this.form.markAllAsTouched();
    return;
  }

  const command = toCommand(this.form.getRawValue());
  this.save(command);
}
```

Remember:

- form model is not domain entity;
- client validation is not backend validation;
- handle pending, duplicate submit, server errors, and retry;
- custom controls need value, touched, and disabled contracts.

---

# 8. HTTP

```ts
@Injectable()
class HttpOrderRepository extends OrderRepository {
  private readonly http = inject(HttpClient);

  findAll(): Observable<readonly Order[]> {
    return this.http.get<readonly OrderDto[]>('/api/orders').pipe(
      map(dtos => dtos.map(toOrder)),
    );
  }
}
```

Interceptor:

```ts
export const correlationInterceptor: HttpInterceptorFn = (request, next) =>
  next(request.clone({
    setHeaders: { 'X-Correlation-Id': crypto.randomUUID() },
  }));
```

One subscription to a cold HTTP observable normally means one request.

---

# 9. RxJS operator selection

| Need | Operator |
|---|---|
| Latest search wins | `switchMap` |
| Preserve sequential order | `concatMap` |
| Run concurrently | `mergeMap` |
| Ignore duplicate submit while active | `exhaustMap` |
| Ongoing combined values | `combineLatest` |
| One result after finite sources complete | `forkJoin` |
| Primary event plus current context | `withLatestFrom` |
| Recover individual inner request | inner `catchError` |
| Final cleanup | `finalize` |

---

# 10. State placement

```text
URL          filter, sort, page, selected identity
Component    modal, expansion, temporary selection
Form         values, validity, dirty/touched
Route store  feature workflow and feature cache
Root store   user/session/tenant/global config
Backend      source of truth
```

---

# 11. Change detection debugging

Check:

1. Did state change?
2. Was an object mutated in place?
3. Is the correct provider/store instance used?
4. Did the template read the signal/value?
5. Did a supported notification schedule rendering?
6. Is list tracking stable?
7. Is the view detached or reused?
8. Is a computed/effect dependency missing?

---

# 12. Performance checklist

- route lazy loading;
- deferred optional UI;
- stable `track` keys;
- no expensive template functions/getters;
- pure pipes/computed derivations;
- server pagination for large datasets;
- request cancellation/deduplication;
- explicit cache invalidation;
- bundle budgets;
- web-vitals measurement;
- repeated-navigation memory test;
- third-party script review.

---

# 13. Security checklist

- backend authorization for every protected operation;
- no secrets in frontend bundles/config;
- no blind sanitizer bypass;
- safe cookie/token and CSRF strategy;
- validated redirect URLs;
- CSP and security headers;
- no sensitive telemetry/logs;
- runtime validation of untrusted data;
- dependency scanning and lockfile;
- never treat route guards as security enforcement.

---

# 14. Accessibility checklist

- semantic native element first;
- keyboard complete;
- visible focus and logical order;
- labels and accessible names;
- errors associated and announced;
- dialog focus trap/restore;
- contrast, zoom, reduced motion;
- dynamic updates announced only when meaningful;
- RTL/localization tested;
- automated and manual testing.

---

# 15. Test selection

```text
Pure policy/mapper/reducer      unit test
Template interaction           component test
HTTP mapping/error             HTTP integration test
Guard/redirect/params          router harness test
Critical cross-system journey  E2E test
Reusable UI contract           harness + visual + a11y
```

---

# 16. Common anti-patterns

- everything provided in root;
- one global store for every screen;
- backend DTO used everywhere;
- nested subscriptions;
- public subjects/writable signals;
- `shareReplay(1)` as undocumented cache;
- effects copying signals;
- business logic in templates/pipes/interceptors;
- unstable list tracking;
- deep component inheritance;
- giant shared folder/module;
- route guard treated as authorization;
- `any` used to silence design problems;
- micro-frontends used to solve weak modularity.

---

# 17. Official Angular references

- Documentation: https://angular.dev/
- Tutorials: https://angular.dev/tutorials
- Components: https://angular.dev/guide/components
- Templates: https://angular.dev/guide/templates
- Signals: https://angular.dev/guide/signals
- Dependency injection: https://angular.dev/guide/di
- Routing: https://angular.dev/guide/routing
- Forms: https://angular.dev/guide/forms
- HTTP: https://angular.dev/guide/http
- Testing: https://angular.dev/guide/testing
- SSR: https://angular.dev/guide/ssr
- Hydration: https://angular.dev/guide/hydration
- Zoneless: https://angular.dev/guide/zoneless
- Security: https://angular.dev/best-practices/security
- Performance: https://angular.dev/best-practices/runtime-performance
- Accessibility: https://angular.dev/best-practices/a11y
- Releases/support: https://angular.dev/reference/releases
- Version compatibility: https://angular.dev/reference/versions
- CLI reference: https://angular.dev/cli
- Update guide: https://angular.dev/update-guide

# 18. Official language and platform references

- TypeScript handbook: https://www.typescriptlang.org/docs/handbook/
- TypeScript configuration: https://www.typescriptlang.org/tsconfig/
- TypeScript release notes: https://www.typescriptlang.org/docs/handbook/release-notes/overview.html
- MDN JavaScript guide: https://developer.mozilla.org/docs/Web/JavaScript/Guide
- MDN Web APIs: https://developer.mozilla.org/docs/Web/API
- MDN HTTP: https://developer.mozilla.org/docs/Web/HTTP
- Web.dev performance: https://web.dev/learn/performance/
- Web Content Accessibility Guidelines: https://www.w3.org/WAI/standards-guidelines/wcag/
- WAI-ARIA Authoring Practices: https://www.w3.org/WAI/ARIA/apg/
- RxJS documentation: https://rxjs.dev/

# 19. Version review checklist

Before updating these notes or a project:

1. Check actively supported Angular versions.
2. Check Angular/Node/TypeScript/RxJS compatibility.
3. Check API stability labels for signal forms, resources, hydration, and build/test tooling.
4. Read migration schematics and breaking changes.
5. Upgrade one major at a time where required.
6. Run strict build, tests, bundle comparison, SSR/hydration checks, and E2E flows.
7. Record version-specific changes in an ADR or migration log.
