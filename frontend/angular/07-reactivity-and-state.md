# RxJS, Signals, and State Management

The first design decision is not “Which library?” It is “Who owns this state, how long does it live, and how does it change?”

## 1. Classify state

| State | Typical owner | Examples |
|---|---|---|
| Local view state | component | expanded panel, selected row |
| Derived state | computed selector | filtered list, totals |
| Form state | form model | values, validity, dirty state |
| URL state | router | filters, sort, pagination, active entity |
| Feature state | route-scoped store/facade | workflow state shared by feature pages |
| Session state | application scope | current user, tenant, permissions |
| Server state | backend plus frontend cache | users, orders, reference data |
| Ephemeral events | stream/event boundary | notifications, keyboard events |

Duplicating the same state across URL, component, and global store creates synchronization bugs.

## 2. Signals

Signals are ideal for synchronous state with direct dependency tracking.

```ts
@Injectable()
export class OrderListStore {
  private readonly _orders = signal<readonly Order[]>([]);
  private readonly _query = signal('');

  readonly orders = this._orders.asReadonly();
  readonly query = this._query.asReadonly();
  readonly filtered = computed(() => {
    const query = this._query().trim().toLowerCase();
    return this._orders().filter(order =>
      order.customerName.toLowerCase().includes(query)
    );
  });

  setQuery(query: string): void {
    this._query.set(query);
  }
}
```

Rules:

- keep writable signals private;
- expose readonly state;
- use methods for state transitions;
- derive instead of duplicate;
- keep effects at integration boundaries;
- avoid global signal stores for short-lived feature state.

## 3. RxJS observable model

An observable describes a sequence of notifications over time. It can be cold or hot depending on construction and sharing.

Observable contract:

- zero or more `next` values;
- then either `complete` or `error`;
- no notifications after terminal state.

Subscriptions represent resource use. Cancellation occurs through unsubscription when the producer supports it.

## 4. Cold versus hot

A cold observable creates producer behavior per subscriber.

```ts
const users$ = this.http.get<UserDto[]>('/api/users');
```

Two subscriptions usually mean two HTTP requests.

A hot source exists independently of an individual subscription, such as DOM events or a shared subject.

Sharing changes lifetime and caching semantics. Do not add `shareReplay(1)` reflexively.

## 5. Essential operators

### Transform

- `map`: synchronous projection.
- `scan`: accumulated state.
- `groupBy`: partition stream; use carefully due to lifecycle complexity.

### Filter/rate

- `filter`;
- `distinctUntilChanged`;
- `debounceTime`;
- `throttleTime`;
- `auditTime`.

### Combine

- `combineLatest`: emit when any source changes after all emitted;
- `withLatestFrom`: combine when primary source emits;
- `forkJoin`: wait for all finite sources to complete;
- `concat`: subscribe sequentially;
- `merge`: subscribe concurrently.

### Flatten

- `switchMap`: cancel prior inner work; ideal for search/latest request wins.
- `concatMap`: queue and preserve order.
- `mergeMap`: concurrent inner work.
- `exhaustMap`: ignore new triggers while current work runs; useful for submit/login protection.

Operator selection is a concurrency policy.

## 6. Search example

```ts
readonly results$ = this.searchControl.valueChanges.pipe(
  map(value => value.trim()),
  debounceTime(250),
  distinctUntilChanged(),
  switchMap(query =>
    query.length < 2
      ? of([])
      : this.repository.search(query).pipe(
          catchError(error => {
            this.errorReporter.report(error);
            return of([]);
          }),
        )
  ),
);
```

`switchMap` cancels obsolete requests on new search terms.

## 7. Submission example

```ts
readonly saveResult$ = this.saveClicks.pipe(
  exhaustMap(() =>
    this.repository.save(this.form.getRawValue()).pipe(
      materialize(),
    )
  ),
);
```

`exhaustMap` prevents duplicate overlapping submissions. Another valid design disables the UI and uses `concatMap` or imperative orchestration. Choose intentionally.

## 8. Error placement

Placement changes behavior:

```ts
source$.pipe(
  switchMap(value => request(value).pipe(
    catchError(error => of(toFailure(error)))
  ))
)
```

The outer stream survives individual request failure.

```ts
source$.pipe(
  switchMap(value => request(value)),
  catchError(error => of(toFailure(error)))
)
```

The outer pipeline may terminate after recovery emission depending on design. Think about whether future user actions should continue.

## 9. Subjects

Use subjects when you truly need an imperative bridge into a stream.

- `Subject`: no retained current value.
- `BehaviorSubject`: current value for new subscribers.
- `ReplaySubject`: retained history/window.
- `AsyncSubject`: final value upon completion.

Do not expose a writable subject publicly:

```ts
private readonly refreshTrigger = new Subject<void>();
readonly refreshes$ = this.refreshTrigger.asObservable();
```

Signals often replace `BehaviorSubject` for synchronous locally owned state, but not every asynchronous stream.

## 10. Sharing and caching

`shareReplay` combines sharing and replay behavior. Questions before use:

- When is the source subscribed?
- When is it unsubscribed?
- Are errors retained or reset?
- Is the cached value stale?
- Is the cache scoped per user/tenant/filter?
- Can it retain large data indefinitely?
- How is invalidation triggered?

For server state, a repository cache with explicit keys, TTL/freshness, invalidation, and observability is often clearer than scattered sharing operators.

## 11. Signal and observable interoperability

Use observables for:

- HTTP and asynchronous event streams;
- cancellation and concurrency composition;
- websocket/SSE streams;
- time-based operators;
- multi-event pipelines.

Use signals for:

- current synchronous state;
- local and feature state;
- derived template state;
- fine-grained dependency tracking.

Convert at a stable boundary rather than repeatedly converting back and forth.

```ts
readonly routeId = toSignal(
  this.route.paramMap.pipe(map(params => params.get('id'))),
  { initialValue: null }
);
```

When converting, decide:

- initial value;
- error behavior;
- subscription lifetime;
- equality;
- whether the source emits synchronously.

## 12. Resource-style async state

Modern Angular provides resource-oriented APIs for linking reactive requests with asynchronous loading. Before adopting them broadly, verify current stability and API status.

Regardless of API, model:

- request identity;
- loading/reloading;
- data;
- empty state;
- error;
- cancellation;
- stale data behavior;
- optimistic updates.

## 13. Store design

A small signal-based feature store:

```ts
@Injectable()
export class OrdersStore {
  private readonly repository = inject(OrderRepository);

  private readonly state = signal<OrdersState>({
    status: 'idle',
    orders: [],
    error: null,
  });

  readonly status = computed(() => this.state().status);
  readonly orders = computed(() => this.state().orders);
  readonly error = computed(() => this.state().error);

  load(): void {
    this.state.update(state => ({ ...state, status: 'loading', error: null }));

    this.repository.findAll()
      .pipe(takeUntilDestroyed())
      .subscribe({
        next: orders => this.state.set({ status: 'success', orders, error: null }),
        error: error => this.state.set({ status: 'error', orders: [], error: toAppError(error) }),
      });
  }
}
```

For more complex workflows, centralize actions/reducers/effects or use a mature state library when it genuinely reduces ambiguity.

## 14. When a state library helps

Consider a formal library when:

- many screens coordinate the same complex state;
- state transitions need strict event/reducer discipline;
- effects, entity normalization, devtools, and replay are valuable;
- many developers require one predictable convention;
- optimistic updates and conflict recovery are extensive.

Do not use a global store simply because the application is “enterprise.” Complexity, ownership, and team needs should justify it.

## 15. Reducer pattern

```ts
type Action =
  | { type: 'load' }
  | { type: 'loadSuccess'; orders: readonly Order[] }
  | { type: 'loadFailure'; error: AppError };

function reduce(state: State, action: Action): State {
  switch (action.type) {
    case 'load':
      return { ...state, status: 'loading', error: null };
    case 'loadSuccess':
      return { status: 'success', orders: action.orders, error: null };
    case 'loadFailure':
      return { ...state, status: 'error', error: action.error };
    default:
      return assertNever(action);
  }
}
```

Reducers make transitions explicit and testable.

## 16. Entity normalization

Normalize when many operations access entities by ID or update subsets frequently:

```ts
type EntityState<T, Id extends PropertyKey> = Readonly<{
  ids: readonly Id[];
  entities: Readonly<Partial<Record<Id, T>>>;
}>;
```

Do not normalize tiny read-only lists without benefit.

## 17. Optimistic updates

An optimistic flow needs:

1. client-generated operation identity;
2. immediate local state update;
3. backend request;
4. success reconciliation;
5. failure rollback or conflict state;
6. duplicate and out-of-order response handling;
7. user feedback.

Optimism without rollback/conflict policy is not complete.

## 18. Real-time streams

For websocket/SSE:

- reconnect with bounded backoff and jitter;
- resume using cursor/event ID if supported;
- de-duplicate events;
- order by domain sequence when required;
- detect stale/gap conditions;
- merge snapshots with deltas;
- scope subscriptions by active route/user context;
- prevent unbounded in-memory history;
- expose connection state to UI.

Do not assume transport arrival order equals domain truth across partitions or reconnects.

## 19. URL as state

Search filters, pagination, sorting, selected tabs, and entity identity often belong in the URL.

Benefits:

- deep links;
- refresh survival;
- browser navigation;
- sharing;
- observability and reproducibility.

Serialize only stable public state; do not put secrets or huge objects in query parameters.

## 20. Common anti-patterns

- nested subscriptions;
- subscription inside subscription instead of flattening;
- manual unsubscribe subjects everywhere when destruction utilities exist;
- `shareReplay(1)` used as accidental global cache;
- effects that propagate state;
- duplicate source-of-truth state;
- public subjects or writable signals;
- one root store for every temporary screen state;
- treating server data as permanently fresh;
- retrying writes without idempotency semantics;
- converting observable to signal and back repeatedly.

## 21. Interview explanations

Be ready to explain:

- cold versus hot observables;
- subject variants;
- `switchMap`, `concatMap`, `mergeMap`, `exhaustMap` through concurrency use cases;
- error placement;
- signals versus observables;
- computed versus effect;
- `shareReplay` risks;
- state scope and ownership;
- optimistic update design;
- real-time snapshot plus delta reconciliation;
- why URL state is often better than global state.
