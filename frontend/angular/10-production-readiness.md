# Performance, SSR, Security, Accessibility, and Operations

Production readiness is a system property. A fast local component is not enough if the application has oversized bundles, duplicate requests, inaccessible interaction, insecure session handling, or no diagnostics.

## 1. Performance model

Frontend latency is the sum of:

- network connection and transfer;
- server response time;
- JavaScript parse/compile/execute;
- Angular bootstrap and rendering;
- data fetching and serialization;
- style/layout/paint/compositing;
- user-device constraints;
- third-party scripts;
- repeated work after interaction.

Measure before optimizing.

## 2. Bundle strategy

Use:

- route-level lazy loading;
- dynamic import for expensive optional tools;
- deferred template blocks for below-the-fold or interaction-triggered content;
- tree-shakable providers and side-effect-free modules;
- targeted polyfills;
- production source-map policy;
- build budgets.

Investigate:

- duplicated packages;
- importing entire utility or chart libraries;
- locale/data packages bundled unnecessarily;
- dependencies that are not ESM-friendly;
- design-system components importing unrelated features;
- shared chunks that become too large.

## 3. Rendering performance

Common causes of unnecessary work:

- unstable `@for` tracking;
- new object/array creation in template expressions;
- expensive getters/functions called by templates;
- impure pipes;
- broad state/effect fan-out;
- overly large component subtrees;
- repeated synchronous parsing/formatting;
- direct DOM reads and writes causing layout thrashing.

Prefer:

- immutable transitions;
- computed signals/selectors;
- stable references;
- virtual scrolling for very large collections;
- pagination or incremental rendering;
- explicit rendering boundaries;
- off-main-thread processing for genuinely heavy CPU work.

## 4. Change-detection optimization

Optimization sequence:

1. identify actual slow interaction;
2. record browser/Angular performance data;
3. find long tasks or repeated view work;
4. reduce state fan-out and template computation;
5. use `OnPush` and signal-driven notification correctly;
6. verify improvement and no stale UI;
7. add a regression test or budget.

Do not call manual detection APIs throughout the application as a first response. That often hides ownership and scheduling problems.

## 5. Network performance

Improve:

- API response shape and pagination;
- compression;
- cache validators and CDN policy;
- request deduplication;
- cancellation of obsolete requests;
- concurrent independent requests;
- server aggregation where multiple round trips are avoidable;
- preloading only when evidence supports it;
- image sizing and modern formats.

Avoid loading complete datasets and filtering only in the browser for convenience.

## 6. Caching

Define for every cache:

- key;
- scope: user, tenant, feature, query;
- freshness and TTL;
- invalidation triggers;
- stale-while-revalidate behavior;
- error behavior;
- memory limit/eviction;
- authorization isolation;
- observability.

Never share user-specific cached data across sessions or tenants.

## 7. SSR

Server-side rendering can improve initial content delivery, SEO, and perceived loading for suitable pages.

SSR introduces:

- server runtime and scaling;
- request-specific state isolation;
- browser API incompatibility;
- transfer/cache strategy;
- authentication and personalization concerns;
- error handling on server and client;
- deployment complexity.

Do not add SSR to an authenticated internal application without a measured need.

## 8. Hydration

Hydration attaches Angular behavior to server-rendered DOM.

Prevent mismatch by:

- producing valid deterministic HTML;
- avoiding direct DOM manipulation before hydration;
- keeping server/client configuration consistent;
- handling random IDs/time values deterministically;
- isolating browser-only code;
- testing real production SSR output;
- understanding third-party component hydration support.

Use incremental/deferred hydration where current Angular APIs and application behavior justify it.

## 9. Prerendering

Prerender static or mostly static routes at build time when:

- content changes infrequently;
- route list is known;
- personalization is unnecessary;
- CDN delivery is valuable.

Do not prerender user-specific or rapidly changing pages without a correct regeneration strategy.

## 10. Zoneless readiness

For zoneless Angular:

- use signals, Angular event listeners, inputs, and supported async primitives;
- avoid relying on accidental checks after arbitrary callbacks;
- integrate third-party libraries through explicit state updates;
- remove ZoneJS only after tests pass under zoneless configuration;
- inspect async APIs and custom schedulers;
- validate SSR/hydration compatibility for the selected release.

## 11. Security threat model

Treat all frontend code and data delivered to the browser as visible to the user.

Protect against:

- XSS;
- CSRF;
- insecure token storage;
- broken authorization assumptions;
- open redirects;
- clickjacking;
- sensitive logging;
- vulnerable dependencies;
- malicious file/content rendering;
- unsafe postMessage communication;
- supply-chain compromise.

## 12. Angular template security

Angular escapes/interprets template bindings by context. Do not bypass sanitization without a tightly controlled, reviewed source.

Dangerous patterns:

- binding untrusted HTML after bypassing sanitizer;
- constructing script/resource URLs from user data;
- evaluating dynamic template/code strings;
- directly writing `innerHTML` through native DOM APIs;
- trusting markdown/WYSIWYG output without sanitization policy.

A “safe” wrapper should encode provenance and policy, not merely rename a bypass call.

## 13. Authentication and session security

Prefer a deployment design that minimizes JavaScript access to durable credentials.

Consider:

- HTTP-only, Secure, SameSite cookies;
- CSRF protection for cookie-authenticated state-changing requests;
- short-lived tokens;
- refresh coordination;
- logout and revocation;
- session fixation prevention;
- reauthentication for sensitive actions;
- multi-tab behavior;
- secure redirect validation.

Do not store privileged long-lived tokens in `localStorage` by default.

## 14. Authorization

Frontend authorization controls presentation and navigation. Backend authorization controls access.

The backend must verify:

- authenticated identity;
- tenant/resource ownership;
- role/permission/policy;
- operation and field-level restrictions;
- state-transition validity.

Do not send all sensitive data and merely hide unauthorized fields in Angular.

## 15. Content Security Policy

A strong CSP can reduce XSS impact. Design it with:

- script/style source restrictions;
- nonces/hashes where required;
- frame ancestors;
- object/base URI restrictions;
- reporting;
- Trusted Types where applicable;
- third-party script minimization.

Avoid weakening CSP with broad unsafe allowances just to support one dependency.

## 16. Dependency security

Use:

- lockfiles;
- automated vulnerability and license scanning;
- controlled package registries where required;
- update policies;
- provenance/signature features when available;
- minimal dependency count;
- review of install scripts and maintainership;
- reproducible CI installation.

A package with a tiny helper can cost more in supply-chain risk than writing a local utility.

## 17. Accessibility architecture

Accessibility is not a final audit step.

Every reusable component needs contracts for:

- semantic role;
- accessible name;
- keyboard interactions;
- focus entry, movement, trapping, and restoration;
- disabled and readonly behavior;
- errors/help text;
- live announcements;
- high contrast and zoom;
- reduced motion;
- RTL and localization.

Use established interaction patterns for dialogs, menus, tabs, comboboxes, grids, and trees.

## 18. Focus management

Manage focus when:

- opening/closing dialogs;
- navigating to a new view;
- adding/removing form sections;
- showing validation summary;
- performing destructive confirmation;
- updating content that changes task context.

Do not move focus for every minor update. It can disorient assistive-technology users.

## 19. Error accessibility

For forms:

- associate messages with controls;
- indicate invalid state programmatically;
- provide a summary for large forms;
- move or guide focus after failed submission;
- preserve entered data;
- use clear recovery language;
- announce asynchronous/server errors appropriately.

## 20. Observability

Capture:

- route/navigation timing;
- API timing and status;
- correlation/trace identifiers;
- JavaScript errors and unhandled rejections;
- selected business journey events;
- web vitals and device context;
- feature flag/config version;
- build/release identifier;
- real-time connection state;
- cache hit/miss where useful.

Redact tokens, personal data, request bodies, and sensitive query parameters.

## 21. Error boundaries and recovery

Define recovery by layer:

- component: local retry/empty state;
- feature: route-level failure and navigation recovery;
- application: unexpected error reporting and safe fallback;
- session: reauthentication or forbidden state;
- deployment: rollback and feature-flag disablement.

Do not replace the entire app with a generic error page for every recoverable request failure.

## 22. Configuration and feature flags

Runtime configuration should be:

- schema-validated;
- versioned;
- observable in diagnostics;
- free of secrets;
- loaded before dependent features;
- resilient to missing optional values.

Feature flags need:

- owner and expiry;
- default behavior;
- server-side enforcement when security-sensitive;
- analytics/observability;
- cleanup after rollout;
- test coverage for both states.

## 23. Deployment

Production pipeline should produce one immutable artifact where possible.

Include:

- strict build and tests;
- dependency/SBOM information;
- bundle budgets;
- environment-independent artifact plus runtime config if required;
- cache-busting hashed assets;
- correct HTML caching policy;
- CDN compression;
- source-map upload with restricted access;
- health/smoke checks;
- canary or progressive rollout;
- rollback procedure.

## 24. Browser caching deployment rule

A common safe policy:

- hashed JS/CSS/assets: long-lived immutable cache;
- `index.html`: short/no cache so deployments are discovered;
- runtime configuration: short cache or versioned fetch;
- API responses: domain-specific policy.

Incorrect HTML caching can serve references to removed asset chunks after deployment.

## 25. Production checklist

- production build has no warnings ignored blindly;
- bundle budgets pass;
- lazy routes are verified;
- no duplicate critical requests;
- loading/empty/error/offline/retry states work;
- keyboard and screen-reader flows are tested;
- authorization is enforced by backend;
- no secrets or sensitive logs are present;
- CSP/security headers are reviewed;
- SSR/hydration has no mismatch warnings if enabled;
- errors and web vitals reach monitoring;
- release ID and correlation IDs are traceable;
- rollback and feature disablement are documented;
- repeated navigation does not leak memory;
- critical E2E smoke tests run against production-like deployment.
