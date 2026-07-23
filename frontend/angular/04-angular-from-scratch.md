# Angular From Scratch

This chapter builds the framework mental model from workspace creation to a small production-style feature.

## 1. What Angular provides

Angular is an application framework with integrated solutions for:

- component rendering and template compilation;
- dependency injection;
- routing;
- forms;
- HTTP integration;
- reactive primitives and RxJS interoperability;
- SSR, hydration, build optimization, testing, and developer tooling.

Angular is opinionated enough to support large teams, but architecture quality still depends on boundaries and state ownership.

## 2. Prerequisites

Use a supported Node.js version for the selected Angular release. Verify versions from the Angular compatibility documentation before creating or upgrading a workspace.

```bash
node --version
npm --version
npx ng version
```

Create a strict standalone application:

```bash
npx @angular/cli@latest new customer-portal \
  --standalone \
  --routing \
  --style=scss \
  --strict

cd customer-portal
npm start
```

Do not install the CLI globally merely because a tutorial does. `npx` or project-local tooling gives more reproducible versioning.

## 3. Workspace anatomy

Common files:

```text
src/
  app/
    app.config.ts
    app.routes.ts
    app.ts
    app.html
    app.scss
  main.ts
  index.html
  styles.scss
angular.json
tsconfig.json
tsconfig.app.json
package.json
```

Responsibilities:

- `main.ts`: browser bootstrap.
- `app.config.ts`: application-wide providers.
- `app.routes.ts`: root route configuration.
- `angular.json`: build, serve, test, assets, styles, and budgets.
- TypeScript configs: compilation and template-checking settings.

## 4. Bootstrap

A standalone application starts with `bootstrapApplication`:

```ts
import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { App } from './app/app';

bootstrapApplication(App, appConfig)
  .catch(error => console.error(error));
```

```ts
import { ApplicationConfig } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { routes } from './app.routes';
import { correlationInterceptor } from './core/http/correlation.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(withInterceptors([correlationInterceptor])),
  ],
};
```

Application providers are long-lived. Do not place feature state there by default.

## 5. Components

A component combines a TypeScript class, template, styles, host element, and dependency context.

```ts
import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

@Component({
  selector: 'app-user-card',
  standalone: true,
  template: `
    <article>
      <h2>{{ user().name }}</h2>
      <button type="button" (click)="selected.emit(user().id)">
        Select
      </button>
    </article>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UserCard {
  readonly user = input.required<UserSummary>();
  readonly selected = output<UserId>();
}
```

Component design rules:

- keep inputs explicit and readonly;
- emit domain-relevant events, not raw DOM events;
- avoid hidden mutation of input objects;
- keep templates declarative;
- move complex orchestration to a feature service/facade when it improves clarity;
- do not split components solely by line count.

## 6. Template syntax

### Interpolation

```html
<p>{{ displayName() }}</p>
```

### Property binding

```html
<button [disabled]="isSaving()">Save</button>
```

### Event binding

```html
<input (input)="onSearch($event)" />
```

### Two-way binding

Use where the bidirectional contract is truly intended, especially for form controls. Avoid using two-way binding to hide unclear ownership.

### Class and style binding

```html
<div [class.is-critical]="severity() === 'critical'"></div>
```

### Modern control flow

```html
@if (state().status === 'loading') {
  <app-spinner />
} @else if (state().status === 'success') {
  @for (user of state().data; track user.id) {
    <app-user-card [user]="user" />
  } @empty {
    <p>No users found.</p>
  }
} @else if (state().status === 'error') {
  <app-error [error]="state().error" />
}
```

Always choose a stable tracking key for lists. Tracking by object identity can cause unnecessary DOM replacement when data is recreated.

## 7. Signals

Signals hold synchronous reactive values.

```ts
readonly query = signal('');
readonly users = signal<readonly UserSummary[]>([]);
readonly filteredUsers = computed(() => {
  const normalized = this.query().trim().toLowerCase();
  return this.users().filter(user =>
    user.name.toLowerCase().includes(normalized)
  );
});
```

Use:

- `signal` for owned mutable state;
- `computed` for derived state;
- `effect` only for effects that synchronize with external systems.

Do not use effects to copy one signal into another when a computed value is sufficient.

## 8. Dependency injection

Angular DI resolves runtime tokens to values.

```ts
@Injectable({ providedIn: 'root' })
export class UserApi {
  private readonly http = inject(HttpClient);

  getUsers(): Observable<readonly UserDto[]> {
    return this.http.get<readonly UserDto[]>('/api/users');
  }
}
```

Provider choices:

- `providedIn: 'root'`: one application-wide service, tree-shakable when unused.
- route providers: one service scope for a route subtree.
- component providers: new instance per component provider boundary.
- injection token: configuration, interface-like contract, or non-class value.

```ts
export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL');
```

A TypeScript interface cannot be an injection token because it is erased at runtime.

## 9. Services

A service is not automatically a domain layer. It is simply an injectable collaborator.

Good service responsibilities:

- API adapter;
- feature orchestration;
- reusable policy;
- state ownership;
- cross-cutting infrastructure.

Bad service design:

- one global service containing unrelated application state;
- services created only to move code out of components;
- direct backend DTO leakage into every view;
- circular service dependencies.

## 10. A small feature structure

```text
features/users/
  data-access/
    user-api.ts
    user-dto.ts
    user.mapper.ts
  domain/
    user.ts
    user-id.ts
  feature-list/
    user-list-page.ts
  ui/
    user-card.ts
    user-filter.ts
  users.routes.ts
  public-api.ts
```

The exact folders are less important than enforceable dependency direction.

## 11. HTTP client

```ts
@Injectable({ providedIn: 'root' })
export class UserRepository {
  private readonly http = inject(HttpClient);

  findAll(): Observable<readonly User[]> {
    return this.http
      .get<readonly UserDto[]>('/api/users')
      .pipe(map(dtos => dtos.map(toUser)));
  }
}
```

HTTP observables are normally cold: each subscription can produce a new request. Share or cache only with explicit freshness and error semantics.

## 12. Functional interceptor

```ts
export const correlationInterceptor: HttpInterceptorFn = (request, next) => {
  const correlationId = crypto.randomUUID();
  return next(request.clone({
    setHeaders: { 'X-Correlation-Id': correlationId },
  }));
};
```

Interceptors are appropriate for transport-level concerns such as correlation, authentication header attachment, tracing, and standardized error translation. Do not hide arbitrary business workflows in them.

## 13. Routing

```ts
export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./home/home').then(m => m.Home),
  },
  {
    path: 'users',
    loadChildren: () => import('./features/users/users.routes')
      .then(m => m.USERS_ROUTES),
  },
  { path: '**', redirectTo: '' },
];
```

Lazy routes create code-splitting boundaries. Validate with bundle output rather than assuming every dynamic import produces an ideal chunk.

## 14. Forms

Prefer reactive forms for complex, dynamic, or heavily validated workflows.

```ts
readonly form = this.formBuilder.nonNullable.group({
  name: ['', [Validators.required, Validators.maxLength(100)]],
  email: ['', [Validators.required, Validators.email]],
});
```

A form submission flow must handle:

- client validation;
- disabled/submitting state;
- duplicate submission prevention;
- server validation errors;
- failure and retry;
- success navigation or state update;
- unsaved-change behavior.

## 15. Lifecycle

Common lifecycle points:

- construction/injection;
- input initialization and changes;
- view/content initialization;
- render completion hooks where needed;
- destruction cleanup.

Do not put all initialization in a lifecycle hook by habit. Field initialization, constructor injection, route resolvers, and reactive derivation may be more appropriate.

Use Angular destruction utilities for subscriptions or imperative resources tied to the injection context.

## 16. Error model

Separate:

- transport errors;
- authentication/authorization failures;
- validation errors;
- domain conflicts;
- unexpected defects.

Convert raw errors to stable application errors at boundaries. User messages should be actionable and must not expose sensitive internals.

## 17. Development workflow

```bash
npm start
npm test
npm run build
npx ng generate component features/users/ui/user-card
npx ng generate service features/users/data-access/user-api
```

Before committing:

- compile with strict checks;
- run tests and linting;
- inspect changed bundle behavior for major features;
- test keyboard navigation;
- verify loading, empty, error, and retry states;
- remove debug logging and accidental subscriptions.

## 18. First application checklist

Build a user-management application containing:

- standalone bootstrap;
- lazy user feature;
- typed API adapter and mapping layer;
- list, detail, create, and edit routes;
- reactive form with server error display;
- signal-based local view state;
- RxJS search with cancellation;
- loading, empty, error, and retry states;
- route guard for unsaved changes;
- component and HTTP tests;
- accessible form and navigation;
- production build with budgets.
