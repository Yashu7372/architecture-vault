# JavaScript Deep Dive

JavaScript is a dynamically typed, prototype-based language with lexical scoping and an event-loop execution model. Angular does not replace these mechanics.

## 1. Values and types

Primitive values:

- `undefined`, `null`, boolean, number, bigint, string, symbol.

Objects include arrays, functions, dates, maps, sets, promises, and user-defined objects.

JavaScript variables hold values. Object variables hold references to objects, but JavaScript arguments are always passed by value—the copied value may itself be a reference.

```js
const a = { count: 1 };
const b = a;
b.count = 2;
console.log(a.count); // 2
```

## 2. Equality and coercion

Prefer `===` and `!==` unless coercion is intentional and understood.

Important cases:

```js
NaN === NaN;          // false
Object.is(NaN, NaN);  // true
0 === -0;             // true
Object.is(0, -0);     // false
```

Falsy values are `false`, `0`, `-0`, `0n`, `""`, `null`, `undefined`, and `NaN`.

`??` checks only `null` and `undefined`; `||` checks truthiness.

```js
const retries = suppliedRetries ?? 3;
```

## 3. Scope and execution context

JavaScript uses lexical scope: name resolution depends on where code is written.

- `let` and `const` are block scoped.
- `var` is function scoped and hoisted differently.
- declarations are processed before execution, but `let` and `const` remain unavailable in the temporal dead zone until initialization.

```js
function outer() {
  const message = 'hello';
  return function inner() {
    return message;
  };
}
```

The returned function retains access to its lexical environment. This is a closure.

Use closures for encapsulation, factories, memoization, callbacks, and stateful utilities. Watch for accidental retention of large object graphs.

## 4. `this`

`this` is determined by invocation style for normal functions:

- method call: receiver object;
- plain call in strict mode: `undefined`;
- constructor call with `new`: new instance;
- `call`, `apply`, or `bind`: explicitly supplied receiver.

Arrow functions do not bind their own `this`; they capture it lexically.

```js
class Counter {
  count = 0;
  increment = () => this.count++;
}
```

This property arrow function is convenient for callbacks but creates one function per instance.

## 5. Functions

Functions are first-class values. They can be passed, returned, stored, and composed.

Important concepts:

- pure versus impure functions;
- higher-order functions;
- currying and partial application;
- recursion;
- default/rest parameters;
- destructuring;
- function declarations versus expressions.

```js
const pipe = (...functions) => input =>
  functions.reduce((value, fn) => fn(value), input);
```

Prefer pure transformations for testability, but isolate unavoidable effects rather than pretending all application code is pure.

## 6. Objects and property model

Objects map property keys to descriptors. A descriptor controls value/get/set, writability, enumerability, and configurability.

```js
Object.defineProperty(account, 'id', {
  value: 'A-100',
  writable: false,
  enumerable: true,
});
```

Useful APIs:

- `Object.keys`, `values`, `entries`;
- `Object.assign` and object spread;
- `Object.create`;
- `Object.freeze`—shallow, not deep;
- `Object.hasOwn`.

## 7. Prototypes and classes

Objects can delegate property lookup to another object through the prototype chain.

```js
function User(name) {
  this.name = name;
}
User.prototype.greet = function () {
  return `Hello ${this.name}`;
};
```

Class syntax is a clearer layer over prototype-based behavior. Methods live on the prototype; instance fields live on each instance.

Know:

- constructor execution;
- `extends` and `super`;
- static members;
- private fields;
- method overriding;
- composition versus inheritance.

Prefer composition when behavior varies independently or inheritance creates fragile coupling.

## 8. Arrays and collections

Understand mutation characteristics:

- mutating: `push`, `pop`, `splice`, `sort`, `reverse`;
- non-mutating/common transforms: `map`, `filter`, `reduce`, `slice`, `toSorted`, `toReversed`, `with` where supported.

Use `Map` for keyed collections with arbitrary keys and predictable APIs. Use `Set` for uniqueness.

Avoid quadratic operations accidentally:

```js
// O(n²) when used repeatedly on a growing array
items.filter((item, index) => items.indexOf(item) === index);

// Typically O(n)
[...new Set(items)];
```

## 9. Modules

ES modules have static imports/exports, module scope, live bindings, and asynchronous loading semantics.

```js
export function calculateTotal() {}
import { calculateTotal } from './pricing.js';
```

Dynamic import creates a lazy boundary:

```js
const feature = await import('./feature.js');
```

Tree shaking depends on static analyzability, package metadata, and side-effect discipline—not merely on using named imports.

## 10. Event loop

JavaScript execution is run-to-completion per task. Browser APIs schedule future work.

Simplified ordering:

1. Execute current call stack.
2. Drain microtask queue.
3. Browser may render.
4. Run next task.

Promises schedule microtasks. Timers schedule tasks.

```js
console.log('A');
setTimeout(() => console.log('B'));
Promise.resolve().then(() => console.log('C'));
console.log('D');
// A, D, C, B
```

Excessive microtasks can delay rendering and other tasks.

## 11. Promises and async/await

A promise represents eventual settlement. `async` functions always return promises.

```js
async function loadUser(id, signal) {
  const response = await fetch(`/api/users/${id}`, { signal });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}
```

Important:

- use `Promise.all` for fail-fast parallel work;
- use `Promise.allSettled` when every result matters;
- avoid sequential `await` when operations are independent;
- cancellation is not automatic—use `AbortController` or library semantics;
- always decide where errors are handled.

## 12. Iterators and generators

An iterable supplies an iterator through `Symbol.iterator`. Generators create iterators with suspended execution.

```js
function* range(start, end) {
  for (let value = start; value <= end; value++) yield value;
}
```

This model helps explain lazy sequences and stream-like APIs.

## 13. Error handling

Throw `Error` objects with context. Preserve causes when wrapping errors.

```js
try {
  await saveOrder(order);
} catch (error) {
  throw new Error('Order save failed', { cause: error });
}
```

Do not catch errors merely to log and rethrow at every layer. Define ownership for recovery, translation, observability, and user messaging.

## 14. Memory and garbage collection

Garbage collectors reclaim unreachable objects. A leak is usually unwanted reachability.

Common frontend leak sources:

- listeners not removed;
- timers not cleared;
- long-lived subscriptions;
- closures retaining large state;
- global caches without eviction;
- detached DOM nodes;
- singleton services retaining feature state forever.

## 15. Immutability

Immutability makes change explicit and works well with reactive rendering.

```js
const updated = users.map(user =>
  user.id === id ? { ...user, active: true } : user
);
```

Object spread is shallow. For complex updates, normalize state or use focused update helpers rather than deep cloning everything.

## 16. Core utilities to implement

### Debounce

```js
function debounce(fn, delay) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}
```

### Memoization

```js
function memoizeOne(fn) {
  let initialized = false;
  let lastArgs;
  let lastValue;

  return (...args) => {
    if (initialized && args.length === lastArgs.length &&
        args.every((value, index) => Object.is(value, lastArgs[index]))) {
      return lastValue;
    }
    initialized = true;
    lastArgs = args;
    lastValue = fn(...args);
    return lastValue;
  };
}
```

## 17. Common interview traps

- `typeof null` is `"object"` for historical reasons.
- arrow functions do not have their own `this`, `arguments`, or constructor behavior.
- `forEach` does not await asynchronous callbacks.
- spreading an object does not deep clone it.
- promises are eager once created; observables may be lazy depending on construction.
- `const` prevents rebinding, not object mutation.
- closures capture bindings, not frozen snapshots of values.
- deleting or setting a property can affect engine optimization, but correctness comes first.

## Practice questions

1. Explain lexical scope and closure using a production example.
2. Predict output involving tasks and microtasks.
3. Implement concurrency-limited async mapping.
4. Explain prototype lookup and class method storage.
5. Find a memory leak caused by a listener or closure.
6. Compare debounce and throttle.
7. Explain why immutable updates help Angular rendering.
