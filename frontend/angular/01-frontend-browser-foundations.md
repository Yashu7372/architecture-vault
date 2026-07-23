# Frontend and Browser Foundations

Angular runs inside the browser platform. Framework knowledge without browser knowledge creates fragile debugging and poor architecture decisions.

## 1. Navigation to rendering

When a user enters a URL:

1. The browser parses the URL.
2. It resolves the host through DNS.
3. It creates a transport connection and negotiates TLS for HTTPS.
4. It sends an HTTP request with headers, cookies, and cache validators.
5. The server or CDN returns HTML and response metadata.
6. The browser parses HTML into the DOM.
7. CSS is parsed into the CSSOM.
8. JavaScript can block parsing unless deferred or loaded as a module.
9. DOM and CSSOM produce a render tree.
10. The browser calculates layout, paints pixels, and composites layers.

Important metrics:

- **TTFB:** server/network responsiveness.
- **FCP:** first content appears.
- **LCP:** main content appears.
- **INP:** responsiveness to interaction.
- **CLS:** visual stability.

## 2. HTML semantics

Prefer native semantic elements before ARIA or generic containers:

- `header`, `nav`, `main`, `section`, `article`, `aside`, `footer`;
- `button` for actions and `a` for navigation;
- `label`, `fieldset`, `legend`, correct input types;
- heading hierarchy that represents document structure;
- tables only for tabular data.

Semantic HTML improves accessibility, keyboard behavior, SEO, testing, and maintainability.

## 3. DOM and events

The DOM is a mutable object graph representing the document.

Event flow:

1. Capturing phase: root toward target.
2. Target phase.
3. Bubbling phase: target toward root.

Key APIs:

- `event.target`: original event source.
- `event.currentTarget`: listener owner.
- `preventDefault()`: cancel browser default when cancelable.
- `stopPropagation()`: stop propagation; use sparingly.

Event delegation places one listener on a stable ancestor and inspects the event target. It is useful for dynamic collections and reduces listeners.

## 4. CSS mental model

### Cascade order

A winning declaration depends on:

- origin and importance;
- cascade layer;
- selector specificity;
- scope/proximity where applicable;
- source order.

### Layout

Understand:

- normal flow;
- block and inline formatting;
- flexbox for one-dimensional layout;
- grid for two-dimensional layout;
- intrinsic sizing, min/max content;
- containing blocks and positioned elements;
- overflow and scroll containers;
- stacking contexts and `z-index`.

### Responsive design

Prefer:

- fluid dimensions;
- responsive typography;
- container or media queries;
- mobile-first constraints;
- content-driven breakpoints;
- logical properties for internationalization.

## 5. Browser execution model

The main thread commonly performs:

- JavaScript execution;
- style calculation;
- layout;
- paint preparation;
- event dispatch.

Long tasks block interaction. Avoid repeatedly mixing layout reads and writes because it can force synchronous layout.

Bad pattern:

```ts
for (const element of elements) {
  const width = element.offsetWidth;
  element.style.width = `${width + 10}px`;
}
```

Better: batch reads, compute, then batch writes.

## 6. Networking and HTTP

Know these concepts:

- methods and idempotency;
- status code classes;
- request/response headers;
- content negotiation and compression;
- HTTP caching with `Cache-Control`, `ETag`, and conditional requests;
- cookies and attributes: `Secure`, `HttpOnly`, `SameSite`;
- CORS as a browser-enforced cross-origin policy;
- preflight requests;
- connection reuse and multiplexing;
- CDN and edge caching.

Frontend caching must not silently violate data freshness or authorization boundaries.

## 7. Browser storage

| Storage | Best for | Risks |
|---|---|---|
| In-memory | transient UI state | lost on refresh |
| `sessionStorage` | per-tab non-sensitive state | synchronous API, script-readable |
| `localStorage` | small durable preferences | synchronous, script-readable, no built-in expiry |
| IndexedDB | larger structured offline data | complexity and migration handling |
| Cookies | server-bound session metadata | sent with requests, size limits |
| Cache Storage | request/response caching | invalidation and stale data |

Do not store secrets in browser storage. A frontend application cannot protect a secret from its own user or from injected script.

## 8. Accessibility

Core requirements:

- full keyboard operability;
- visible focus;
- sensible focus order;
- labels and accessible names;
- appropriate roles, states, and properties;
- adequate contrast;
- error identification and recovery;
- announcements for important dynamic updates;
- reduced-motion support;
- no interaction that depends only on color, hover, or pointer precision.

Use ARIA to fill semantic gaps, not to replace correct HTML.

## 9. Security foundations

Understand:

- XSS and unsafe HTML/script injection;
- CSRF and cookie-based authentication;
- clickjacking and frame protections;
- CSP and trusted resource policies;
- open redirects;
- dependency and supply-chain risk;
- authorization being a server responsibility.

Client-side route guards improve UX; they do not enforce authorization.

## 10. Frontend architecture concerns

A frontend application manages several state classes:

- **server state:** data owned by backend systems;
- **URL state:** shareable navigation/filter state;
- **form state:** values, validation, dirty/touched/submission state;
- **view state:** selected tab, expanded panel, modal visibility;
- **session state:** authenticated user and contextual permissions;
- **cached state:** derived or retained data with freshness rules.

Classify state before selecting a library.

## 11. DevTools workflow

### Network

Check waterfall, initiator, cache status, response size, compression, duplicated requests, preflight, and server timing.

### Performance

Record interaction, inspect long tasks, scripting, style, layout, paint, and layout shifts.

### Memory

Use heap snapshots and allocation timelines. Look for retained components, listeners, timers, subscriptions, and large caches.

### Rendering

Inspect paint flashing, layer borders, and layout shifts when needed.

## Practical exercises

1. Build a responsive accessible form without Angular.
2. Implement event delegation for a dynamic list.
3. Demonstrate microtask versus task ordering.
4. Compare cached and uncached network requests.
5. Cause and fix layout thrashing.
6. Audit a page using keyboard only and an accessibility tree inspector.
7. Explain why a CORS failure cannot be fixed only by changing Angular code.
