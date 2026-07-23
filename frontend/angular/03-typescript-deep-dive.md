# TypeScript Deep Dive

TypeScript is a static type system and tooling layer over JavaScript. Types are erased during compilation; runtime behavior is JavaScript behavior.

## 1. Compiler mental model

The compiler:

1. parses source into syntax trees;
2. binds declarations and scopes;
3. resolves modules and symbols;
4. checks assignability and control-flow narrowing;
5. emits JavaScript and optional declaration/source-map output.

Type correctness does not validate external runtime data. Parse and validate API, storage, URL, and user input at boundaries.

## 2. Strict project baseline

Use strictness as the default:

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "useUnknownInCatchVariables": true
  }
}
```

Adopt additional flags based on ecosystem compatibility. Do not disable strictness globally to solve one local typing problem.

## 3. Inference and annotations

Let TypeScript infer local implementation details. Explicitly type public contracts, domain boundaries, callbacks whose intent is unclear, and exported APIs.

```ts
const retries = 3; // inferred number

export interface UserRepository {
  findById(id: UserId): Promise<User | null>;
}
```

Use `satisfies` to validate a value while preserving its specific inferred type:

```ts
const routes = {
  home: '/',
  users: '/users',
} satisfies Record<string, `/${string}`>;
```

## 4. Union and intersection types

Unions model alternatives. Intersections combine compatible requirements.

```ts
type LoadState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: AppError };
```

This discriminated union prevents impossible combinations such as `loading: true` with both `data` and `error`.

Use exhaustive checks:

```ts
function assertNever(value: never): never {
  throw new Error(`Unhandled value: ${JSON.stringify(value)}`);
}
```

## 5. Narrowing

TypeScript narrows through:

- `typeof`;
- `instanceof`;
- property presence with `in`;
- equality checks;
- truthiness, used carefully;
- discriminant fields;
- user-defined type predicates;
- assertion functions.

```ts
function isUser(value: unknown): value is User {
  return typeof value === 'object' && value !== null &&
    'id' in value && typeof value.id === 'string';
}
```

For untrusted complex data, use a runtime schema validator rather than hand-written shallow guards.

## 6. Interfaces and type aliases

Both can describe object shapes.

Use interfaces when declaration merging or an extendable public object contract is useful. Use type aliases for unions, primitives, tuples, mapped types, and computed compositions.

```ts
interface Auditable {
  createdAt: string;
}

type UserId = string & { readonly __brand: 'UserId' };
```

Structural typing means compatibility is based mainly on shape, not declaration identity. Branding can add nominal-like distinctions for important identifiers.

## 7. Optionality and nullability

These are different:

```ts
interface Example {
  optional?: string;          // property may be absent
  nullable: string | null;    // property exists but may be null
  maybeUndefined: string | undefined;
}
```

Avoid non-null assertions (`!`) unless an invariant is established outside the type system and documented.

## 8. Functions

Model callbacks precisely:

```ts
type Predicate<T> = (value: T, index: number) => boolean;
```

Prefer unions over overloads when behavior and return type do not vary meaningfully. Use overloads when callers receive distinct return types based on distinct inputs.

Understand:

- optional and default parameters;
- rest parameters and tuples;
- call and construct signatures;
- `void`, `never`, `unknown`, and `object`;
- function parameter variance under strict checking.

Avoid the broad `Function` type.

## 9. Generics

Generics preserve relationships between types.

```ts
function indexBy<T, K extends PropertyKey>(
  items: readonly T[],
  keySelector: (item: T) => K,
): Map<K, T> {
  return new Map(items.map(item => [keySelector(item), item]));
}
```

Guidelines:

- use as few type parameters as necessary;
- ensure each parameter relates multiple positions or represents a meaningful choice;
- constrain only what implementation needs;
- do not add generics merely to appear reusable.

## 10. Type operators

### `keyof`

```ts
type UserKey = keyof User;
```

### Indexed access

```ts
type UserName = User['name'];
```

### `typeof`

```ts
const statuses = ['open', 'closed'] as const;
type Status = (typeof statuses)[number];
```

### Mapped types

```ts
type FormControls<T> = {
  [K in keyof T]-?: Control<T[K]>;
};
```

### Conditional types

```ts
type ApiResult<T> = T extends void
  ? { ok: true }
  : { ok: true; data: T };
```

### Template literal types

```ts
type EventName<T extends string> = `${T}Changed`;
```

## 11. Utility types

Know when to use:

- `Partial`, `Required`, `Readonly`;
- `Pick`, `Omit`, `Record`;
- `Exclude`, `Extract`, `NonNullable`;
- `Parameters`, `ReturnType`, `Awaited`;
- constructor-related utility types.

Do not use `Partial<DomainEntity>` as a universal update DTO. It can allow invalid or immutable fields. Define explicit command types.

## 12. Classes and access modifiers

TypeScript modifiers influence type checking. Most are not security boundaries.

```ts
abstract class Repository<T, Id> {
  abstract findById(id: Id): Promise<T | null>;
}
```

Understand:

- public/protected/private;
- ECMAScript `#private` fields;
- abstract classes;
- `implements` versus `extends`;
- parameter properties;
- static members;
- `override`.

Angular dependency injection often favors composition through injected collaborators over deep inheritance.

## 13. Enums and alternatives

String unions and `as const` objects often tree-shake and interoperate more transparently:

```ts
export const Role = {
  Admin: 'admin',
  User: 'user',
} as const;

export type Role = (typeof Role)[keyof typeof Role];
```

Use enums intentionally when their runtime object semantics are desired.

## 14. Modules and resolution

Understand:

- ES module syntax;
- type-only imports/exports;
- package `exports`;
- module resolution strategy;
- path aliases versus real package boundaries;
- declaration files (`.d.ts`);
- ESM/CommonJS interop;
- side effects and tree shaking.

```ts
import type { User } from './user.model';
```

A path alias improves import readability but does not create architectural isolation.

## 15. Decorators

Angular uses decorators as framework metadata on classes and members. Distinguish Angular's supported decorator model and compiler behavior from general ECMAScript decorator proposals.

Do not create custom decorators when a plain function, provider, directive, or composition pattern is clearer.

## 16. Boundary validation

Static types cannot make this safe:

```ts
const user = await response.json() as User;
```

The assertion only silences checking. Instead:

1. receive `unknown`;
2. validate or parse;
3. map transport DTO to domain/view model;
4. handle invalid data explicitly.

## 17. Domain modeling

Prefer meaningful types:

```ts
type OrderId = string & { readonly __brand: 'OrderId' };
type Money = Readonly<{ amountMinor: number; currency: Currency }>;

type PlaceOrderCommand = Readonly<{
  customerId: CustomerId;
  lines: readonly OrderLineInput[];
}>;
```

Separate:

- transport DTOs;
- domain models;
- form models;
- view models;
- commands and events.

They may initially look similar but evolve for different reasons.

## 18. Angular-specific typing practices

- use strict template checking;
- type inputs, outputs, route data, resolvers, forms, and API boundaries;
- use injection tokens for interfaces because interfaces do not exist at runtime;
- avoid `any` in custom controls and event handlers;
- prefer readonly inputs and immutable state transitions;
- represent asynchronous UI states as discriminated unions;
- avoid broad shared models that couple every feature to one backend DTO.

## 19. Common mistakes

- replacing errors with `any`;
- asserting instead of validating;
- using `Object`, `{}`, or `Function` as broad types;
- confusing optional and nullable fields;
- creating generic abstractions before repeated use cases exist;
- exposing mutable arrays and objects through public APIs;
- using type-level complexity that teammates cannot maintain;
- assuming private fields or route guards provide security.

## Interview exercises

1. Model loading, success, empty, and failure states without booleans.
2. Write a generic `groupBy` with correct key constraints.
3. Explain structural typing and excess-property checks.
4. Compare `unknown`, `any`, `never`, and `void`.
5. Implement an exhaustive reducer over a discriminated union.
6. Explain why TypeScript cannot validate an HTTP response.
7. Design types for a dynamic Angular form without abandoning strictness.
