# Enterprise Authentication, SSO, and Backend for Frontend

![Enterprise Angular authentication using SSO and a Backend for Frontend](assets/angular-sso-bff-authentication.svg)

This chapter defines a production architecture for Angular applications that use enterprise Single Sign-On through OpenID Connect and a Backend for Frontend (BFF).

The central security rule is:

> Browser JavaScript should not need direct access to OAuth access or refresh tokens for a sensitive business application.

The Angular application owns user experience and current session presentation. The BFF acts as the confidential OAuth client, manages tokens on the server, maintains a browser session, and calls protected APIs.

## 1. Authentication, authorization, OAuth and OIDC

Do not merge these concepts:

| Concept | Purpose |
|---|---|
| Authentication | establish who the user is |
| Authorization | decide what the user may do on a resource |
| OAuth 2.0 | delegate API access using access tokens |
| OpenID Connect | add an interoperable identity layer on OAuth 2.0 |
| SSO | reuse an identity-provider session across applications |
| Session | maintain authenticated continuity between browser and application |
| MFA | require additional factors during authentication |

An ID token is an assertion for the client about an authentication event. It is not a general-purpose API access token.

## 2. Browser authentication architecture choices

### 2.1 Browser-only OAuth client

```text
Angular → Identity Provider → tokens returned to browser → Angular calls APIs
```

Advantages:

- fewer server components;
- suitable for lower-risk applications where the trade-off is accepted;
- standards-based Authorization Code flow with PKCE.

Risks and complexity:

- access tokens are available to browser code;
- XSS can steal or misuse tokens;
- refresh-token handling is difficult;
- every API requires correct CORS and token policy;
- logout, token rotation and multi-API coordination move into the browser.

### 2.2 Token-mediating backend

The backend performs OAuth but returns an access token to the browser for direct API calls. This removes some OAuth responsibilities from Angular but still exposes the access token to browser code.

### 2.3 Backend for Frontend

```text
Angular ──session cookie──> BFF ──access token──> APIs
                               └──OIDC client──> Identity Provider
```

The BFF:

1. acts as a confidential OIDC/OAuth client;
2. performs Authorization Code flow with PKCE;
3. stores access and refresh tokens outside browser JavaScript;
4. creates a secure browser session;
5. proxies or composes approved API operations;
6. attaches access tokens server-side;
7. applies CSRF, policy, rate and outbound routing controls.

The current IETF browser-based applications guidance presents the BFF as the strongest of the common browser OAuth architecture patterns and recommends it for business, sensitive and personal-data applications.

## 3. Reference deployment

Prefer same-origin routing:

```text
https://portal.example.com/               Angular static assets
https://portal.example.com/bff/session    BFF session API
https://portal.example.com/bff/login      start OIDC login
https://portal.example.com/bff/logout     terminate session
https://portal.example.com/bff/orders/*   approved API mediation
```

A reverse proxy or ingress routes `/` to static Angular assets and `/bff/*` to the BFF.

Benefits:

- session cookies remain first-party;
- Angular avoids cross-origin credential configuration;
- simpler CSRF and CORS policy;
- one product origin for CSP, security headers and observability;
- the BFF can be deployed with the Angular product rather than as a generic enterprise gateway.

A BFF is not merely an API gateway. It is the OAuth client and browser-session owner for one frontend experience.

## 4. Login sequence

```text
1. Browser loads Angular.
2. Angular calls GET /bff/session with credentials.
3. BFF returns authenticated session or 401.
4. Angular navigates browser to /bff/login?returnUrl=/orders.
5. BFF creates state, nonce and PKCE verifier and redirects to IdP.
6. User authenticates at IdP; an existing IdP session may provide SSO.
7. IdP redirects authorization code to BFF callback.
8. BFF validates state, exchanges code using PKCE and client authentication.
9. BFF validates issuer, audience, nonce, signature and required claims.
10. BFF stores tokens in a protected server-side session/token store.
11. BFF rotates the application session ID and sets a secure cookie.
12. BFF redirects to a validated local return URL.
13. Angular loads /bff/session and renders authorized navigation.
14. Angular calls only approved /bff/* endpoints.
15. BFF obtains/refreshes the appropriate token and calls the API.
```

Never accept an arbitrary external `returnUrl`. Resolve only validated local application paths.

## 5. BFF endpoint contract

A minimal contract:

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/bff/session` | current session and user presentation model |
| GET | `/bff/login` | initiate OIDC authorization redirect |
| GET/POST | `/bff/login/callback` | process authorization response |
| POST | `/bff/logout` | destroy local session and apply federated logout policy |
| GET | `/bff/csrf` | issue/read anti-CSRF metadata when needed |
| * | `/bff/{feature}/...` | explicit feature API operations |

Example session response:

```ts
export interface SessionView {
  readonly status: 'authenticated';
  readonly user: {
    readonly id: string;
    readonly displayName: string;
    readonly email?: string;
  };
  readonly tenant: {
    readonly id: string;
    readonly displayName: string;
  };
  readonly permissions: readonly Permission[];
  readonly expiresAt: string;
  readonly authenticationMethods: readonly string[];
}
```

Do not return raw ID tokens, access tokens, refresh tokens, client secrets, full identity-provider claims or unnecessary personal data.

## 6. Angular folder structure

```text
src/app/core/auth/
  auth.models.ts
  auth-session.store.ts
  auth-session.api.ts
  auth.providers.ts
  authenticated.guard.ts
  permission.guard.ts
  auth-error.interceptor.ts
  login.service.ts
  logout.service.ts
  return-url.ts
  auth-shell/
```

Keep feature-specific authorization policies in the feature when they depend on domain context.

## 7. Session store

```ts
import { Injectable, computed, signal } from '@angular/core';

export type SessionState =
  | { readonly status: 'unknown' }
  | { readonly status: 'anonymous' }
  | { readonly status: 'authenticated'; readonly session: SessionView }
  | { readonly status: 'error'; readonly error: AppError };

@Injectable({ providedIn: 'root' })
export class AuthSessionStore {
  private readonly state = signal<SessionState>({ status: 'unknown' });

  readonly sessionState = this.state.asReadonly();
  readonly isAuthenticated = computed(
    () => this.state().status === 'authenticated',
  );
  readonly session = computed(() => {
    const state = this.state();
    return state.status === 'authenticated' ? state.session : null;
  });
  readonly permissions = computed(
    () => new Set(this.session()?.permissions ?? []),
  );

  setAuthenticated(session: SessionView): void {
    this.state.set({ status: 'authenticated', session });
  }

  setAnonymous(): void {
    this.state.set({ status: 'anonymous' });
  }

  setError(error: AppError): void {
    this.state.set({ status: 'error', error });
  }

  clear(): void {
    this.state.set({ status: 'anonymous' });
  }

  can(permission: Permission): boolean {
    return this.permissions().has(permission);
  }
}
```

Use explicit states. A failed session request is not automatically the same as an anonymous user; it may be a network or backend failure.

## 8. Session API

```ts
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class AuthSessionApi {
  private readonly http = inject(HttpClient);

  load(): Observable<SessionView> {
    return this.http.get<SessionView>('/bff/session', {
      withCredentials: true,
    });
  }

  logout(): Observable<void> {
    return this.http.post<void>('/bff/logout', {}, {
      withCredentials: true,
    });
  }
}
```

With a same-origin BFF, the browser normally sends the session cookie automatically. `withCredentials` becomes important when credentials are required across a permitted origin boundary, but same-origin deployment is simpler.

## 9. Bootstrap the session once

```ts
import { ApplicationConfig, inject, provideAppInitializer } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { catchError, firstValueFrom, of, tap } from 'rxjs';

function initializeSession(): Promise<void> {
  const api = inject(AuthSessionApi);
  const store = inject(AuthSessionStore);
  const errors = inject(ErrorTranslator);

  return firstValueFrom(
    api.load().pipe(
      tap(session => store.setAuthenticated(session)),
      catchError(error => {
        if (error.status === 401) {
          store.setAnonymous();
        } else {
          store.setError(errors.fromHttp(error));
        }
        return of(void 0);
      }),
    ),
  ).then(() => undefined);
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideHttpClient(withInterceptors([
      correlationInterceptor,
      authFailureInterceptor,
      transportErrorInterceptor,
    ])),
    provideAppInitializer(initializeSession),
  ],
};
```

Do not allow every component to independently call `/bff/session` on startup. Establish one session bootstrap owner and expose readonly state.

For applications that must render a public shell immediately, bootstrap asynchronously and gate protected routes on the store's resolved state instead of blocking the entire application.

## 10. Login navigation

Login is a browser navigation, not an AJAX call, because the IdP flow uses redirects.

```ts
@Injectable({ providedIn: 'root' })
export class LoginService {
  begin(returnUrl: string): void {
    const safeReturnUrl = normalizeLocalReturnUrl(returnUrl);
    window.location.assign(
      `/bff/login?returnUrl=${encodeURIComponent(safeReturnUrl)}`,
    );
  }
}
```

```ts
export function normalizeLocalReturnUrl(value: string): string {
  if (!value.startsWith('/') || value.startsWith('//')) {
    return '/';
  }

  const url = new URL(value, window.location.origin);
  return url.origin === window.location.origin
    ? `${url.pathname}${url.search}${url.hash}`
    : '/';
}
```

The BFF must repeat its own return-URL validation. Client validation is only user-experience protection.

## 11. Authentication guard

```ts
import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

export const authenticatedGuard: CanActivateFn = (_route, state) => {
  const sessions = inject(AuthSessionStore);
  const router = inject(Router);

  const current = sessions.sessionState();

  if (current.status === 'authenticated') {
    return true;
  }

  if (current.status === 'unknown') {
    return router.createUrlTree(['/session-loading'], {
      queryParams: { returnUrl: state.url },
    });
  }

  return router.createUrlTree(['/sign-in'], {
    queryParams: { returnUrl: state.url },
  });
};
```

Route guards improve navigation and visibility. They do not enforce authorization. The BFF and resource API must apply authorization for every operation.

## 12. Permission guard

Define permissions as stable capability identifiers rather than scattering raw IdP role names through components.

```ts
export const PERMISSION = {
  orderRead: 'orders.read',
  orderUpdate: 'orders.update',
  reportRun: 'reports.run',
  administration: 'administration.access',
} as const;

export type Permission = typeof PERMISSION[keyof typeof PERMISSION];
```

```ts
export function requirePermission(permission: Permission): CanActivateFn {
  return () => {
    const sessions = inject(AuthSessionStore);
    const router = inject(Router);

    return sessions.can(permission)
      ? true
      : router.createUrlTree(['/forbidden']);
  };
}
```

```ts
{
  path: 'reports',
  canActivate: [authenticatedGuard, requirePermission(PERMISSION.reportRun)],
  loadChildren: () => import('./features/reports/reports.routes')
    .then(module => module.REPORTS_ROUTES),
}
```

Prefer server-issued application permissions or a BFF mapping layer that translates IdP groups/roles into stable product permissions.

## 13. Functional HTTP interceptors

With a BFF, Angular normally does not attach bearer tokens.

A correlation interceptor:

```ts
import { HttpInterceptorFn } from '@angular/common/http';

export const correlationInterceptor: HttpInterceptorFn = (request, next) => {
  const correlationId = crypto.randomUUID();

  return next(request.clone({
    setHeaders: { 'X-Correlation-ID': correlationId },
  }));
};
```

Only attach headers to approved first-party URLs. Do not leak internal identifiers to arbitrary third-party endpoints.

## 14. Coordinate 401 responses

A naive interceptor that redirects on every 401 can create:

- multiple concurrent session checks;
- duplicate login redirects;
- retry storms;
- lost form state;
- loops when the login or session endpoint itself returns 401.

The BFF should normally refresh tokens server-side before returning a final 401. Angular should treat a final 401 as session expiry.

```ts
@Injectable({ providedIn: 'root' })
export class SessionExpiryCoordinator {
  private handling = false;

  handleExpired(returnUrl: string): void {
    if (this.handling) return;
    this.handling = true;

    inject(AuthSessionStore).clear();
    inject(LoginService).begin(returnUrl);
  }
}
```

```ts
export const authFailureInterceptor: HttpInterceptorFn = (request, next) => {
  const coordinator = inject(SessionExpiryCoordinator);
  const router = inject(Router);

  return next(request).pipe(
    catchError(error => {
      const isAuthEndpoint = request.url.startsWith('/bff/session') ||
        request.url.startsWith('/bff/login') ||
        request.url.startsWith('/bff/logout');

      if (error.status === 401 && !isAuthEndpoint) {
        coordinator.handleExpired(router.url);
      }

      return throwError(() => error);
    }),
  );
};
```

For complex applications, preserve an unsaved-work recovery strategy rather than blindly redirecting.

## 15. CSRF/XSRF

Cookie-based authentication requires CSRF protection for state-changing operations.

Angular `HttpClient` supports the client half of a common double-submit-style integration by reading a JavaScript-readable XSRF cookie and sending its value in a request header for eligible same-origin mutations.

```ts
provideHttpClient(
  withXsrfConfiguration({
    cookieName: 'PORTAL-XSRF-TOKEN',
    headerName: 'X-PORTAL-XSRF-TOKEN',
  }),
  withInterceptors([
    correlationInterceptor,
    authFailureInterceptor,
  ]),
)
```

The BFF must:

- issue the anti-CSRF token;
- bind/verify it against the user session;
- validate it on eligible mutations;
- reject missing or mismatched values;
- use appropriate SameSite and origin checks as defence in depth.

The authentication session cookie should remain `HttpOnly`; the separate anti-CSRF cookie can be readable by Angular when using this pattern.

Do not disable CSRF protection merely because the endpoint accepts JSON.

## 16. Cookie policy

Recommended session-cookie attributes:

```text
Secure
HttpOnly
SameSite=Lax or Strict when compatible with the login topology
Path=/
short idle timeout
absolute maximum lifetime
server-side revocation
session ID rotation after authentication and privilege change
```

Consider a `__Host-` prefixed cookie when deployment constraints permit:

```text
Set-Cookie: __Host-portal-session=...; Secure; HttpOnly; Path=/; SameSite=Lax
```

Do not put access tokens or user profile JSON inside a readable cookie.

If using encrypted client-side session cookies, ensure size, key rotation, replay, revocation and leakage implications are understood. High-value applications often prefer an opaque cookie referencing server-side session state.

## 17. BFF token storage

Store per-session token material in a protected server-side store:

```text
sessionId
subject/user identity
issuer and tenant
access token encrypted at rest where appropriate
refresh token encrypted at rest
access-token expiry
granted scopes/audience
session created/last activity/absolute expiry
refresh version or rotation metadata
logout/revocation state
```

Controls:

- no token logging;
- encryption and key rotation;
- strict administrative access;
- short data retention;
- deletion on logout and expiry;
- bounded cache size;
- resilient but fail-closed behavior;
- single-flight refresh per session and audience.

## 18. Token refresh

The browser should not implement refresh-token rotation in a BFF design.

Server-side algorithm:

```text
1. Resolve session.
2. Select token by resource/audience.
3. If token has safe remaining lifetime, use it.
4. Otherwise acquire a per-session/token lock.
5. Re-check after lock acquisition.
6. Refresh token with IdP.
7. Validate response and rotation rules.
8. Atomically replace encrypted token state.
9. Release lock.
10. Call API or terminate session on definitive failure.
```

This avoids many simultaneous API requests causing a refresh storm.

Do not retry a non-idempotent API mutation automatically unless the operation has an idempotency design.

## 19. BFF outbound API mediation

Never create an unrestricted endpoint such as:

```text
/bff/proxy?url=https://anything.example/path
```

Use explicit mappings:

```text
GET  /bff/orders/{id}  → GET  https://orders-api.internal/orders/{id}
POST /bff/orders       → POST https://orders-api.internal/orders
GET  /bff/reports/...  → GET  https://reports-api.internal/...
```

Validate:

- destination host and scheme;
- path template and identifiers;
- allowed method;
- request and response size;
- headers that may be forwarded;
- timeout and retry policy;
- user and resource authorization;
- rate and concurrency limits.

Strip hop-by-hop headers and never let user input select an arbitrary token audience or destination.

## 20. API authorization

Each protected API must validate:

- token issuer and signature;
- audience;
- expiry and not-before time;
- required scope/permission;
- tenant and resource relationship;
- operation-specific policy.

A user with `orders.read` must not automatically read every tenant's orders. Use resource-aware authorization.

The BFF may enforce coarse product policy, but the resource API remains authoritative for its data.

## 21. SSO behavior

SSO comes from the identity-provider session, not from copying tokens between Angular applications.

For two applications:

```text
Portal A → /bff/login → IdP sees existing session → returns quickly
Portal B → /bff/login → same IdP session → returns quickly
```

Each application should generally maintain its own local BFF session and OAuth client registration.

Do not share one application's session cookie across unrelated products merely to simulate SSO.

## 22. Multi-tenant identity

Resolve tenant from trusted application context, not solely from a mutable query parameter.

Possible models:

- one IdP tenant/realm per customer;
- one shared issuer with tenant claim;
- home-realm discovery before login;
- organization selection after authentication;
- delegated administration.

Validate issuer, tenant and client registration together. Prevent login confusion where an authorization response from one issuer is accepted for another tenant.

The BFF should translate raw identity claims into a stable application session model.

## 23. Logout

Local logout:

```text
1. require POST + CSRF validation;
2. invalidate BFF session;
3. delete token material;
4. clear session and anti-CSRF cookies;
5. clear Angular user-specific stores/caches;
6. redirect to a safe local logged-out page.
```

Federated logout may additionally:

- revoke refresh/access tokens where supported;
- call the provider's end-session endpoint;
- include a validated post-logout redirect;
- coordinate front-channel or back-channel logout requirements.

SSO logout semantics vary by identity provider. Document whether logout means:

- this application only;
- this browser's IdP session;
- all sessions/devices;
- global enterprise sign-out.

## 24. Frontend cache clearing

On logout or tenant switch, clear:

- root/feature stores containing user data;
- repository caches;
- IndexedDB or Cache Storage entries owned by the application;
- real-time subscriptions;
- pending background work;
- analytics identity state;
- user-specific service-worker data.

Avoid persisting sensitive server data in `localStorage`.

## 25. Browser security controls

Authentication does not remove XSS risk. An injected script may still perform actions through the user's session even when it cannot read an `HttpOnly` cookie.

Use:

- Angular templates and sanitization;
- AOT production compilation;
- Content Security Policy;
- Trusted Types where supported;
- dependency and supply-chain scanning;
- no unsafe dynamic template generation;
- narrow use of `DomSanitizer` bypass APIs;
- no tokens or PII in logs;
- SRI or controlled hosting for external scripts where applicable;
- clickjacking protection;
- secure headers at the BFF/edge.

The BFF reduces token theft exposure; it does not make XSS harmless.

## 26. Session expiry UX

Differentiate:

- idle timeout warning;
- absolute session expiry;
- authentication step-up requirement;
- temporary BFF/API outage;
- revoked account;
- changed tenant/permission;
- failed refresh.

For sensitive forms:

1. warn before idle expiry;
2. preserve only non-sensitive draft data according to policy;
3. reauthenticate or step up;
4. reload authoritative data;
5. detect conflicts before resubmission.

Never silently retry a financial or operational command after reauthentication without idempotency and user confirmation rules.

## 27. Step-up authentication

Certain operations may require stronger authentication than ordinary navigation:

```text
view dashboard        normal SSO session
edit configuration    recent MFA required
approve payment       phishing-resistant factor / transaction policy
access restricted PII additional entitlement and audit
```

The API or BFF returns a structured challenge rather than a generic 403. Angular presents the reason and navigates through a controlled step-up flow. After completion, the original operation must be revalidated server-side.

## 28. Micro-frontend considerations

Prefer one product shell and one BFF session boundary.

Avoid:

- each micro-frontend running its own OIDC client;
- multiple token stores in the same page;
- conflicting interceptors;
- broad cross-domain cookies;
- each feature interpreting raw IdP claims differently.

The shell can expose a narrow session/permission contract, while each API independently authorizes operations.

## 29. Spring Boot BFF implementation shape

Typical components:

```text
Spring Security OAuth2 Client
OIDC authorization-code login
secure server session or distributed session store
WebClient/RestClient token relay performed server-side
CSRF repository and validation
explicit BFF controllers/routes
resource authorization adapters
logout and token revocation coordinator
```

Pseudo-configuration:

```java
@Bean
SecurityFilterChain security(HttpSecurity http) throws Exception {
    http
        .authorizeHttpRequests(auth -> auth
            .requestMatchers("/", "/assets/**", "/bff/login/**").permitAll()
            .requestMatchers(HttpMethod.GET, "/bff/session").permitAll()
            .requestMatchers("/bff/**").authenticated()
            .anyRequest().permitAll())
        .oauth2Login(Customizer.withDefaults())
        .oauth2Client(Customizer.withDefaults())
        .csrf(csrf -> csrf.csrfTokenRepository(
            CookieCsrfTokenRepository.withHttpOnlyFalse()))
        .logout(logout -> logout.logoutUrl("/bff/logout"));

    return http.build();
}
```

Production code must additionally handle session fixation, proxy headers, secure cookies, token-at-rest protection, logout semantics, error translation, outbound allowlists and resource-level authorization.

Do not expose Spring's authorized-client tokens through the session endpoint.

## 30. ASP.NET Core BFF implementation shape

Typical components:

```text
cookie authentication
OpenID Connect handler
Authorization Code + PKCE
server-side token/session store
antiforgery validation
YARP or explicit HttpClient API mediation
authorization policies
Data Protection key management
logout/revocation coordinator
```

Pseudo-configuration:

```csharp
builder.Services
    .AddAuthentication(options =>
    {
        options.DefaultScheme = CookieAuthenticationDefaults.AuthenticationScheme;
        options.DefaultChallengeScheme = OpenIdConnectDefaults.AuthenticationScheme;
    })
    .AddCookie(options =>
    {
        options.Cookie.HttpOnly = true;
        options.Cookie.SecurePolicy = CookieSecurePolicy.Always;
        options.Cookie.SameSite = SameSiteMode.Lax;
    })
    .AddOpenIdConnect(options =>
    {
        options.ResponseType = "code";
        options.UsePkce = true;
        options.SaveTokens = false; // use a protected server-side token store
    });
```

Avoid treating `SaveTokens = true` in a large authentication cookie as a complete enterprise token-storage design.

## 31. Testing strategy

### Angular tests

- anonymous, authenticated and error session bootstrap;
- guard redirects and return URL preservation;
- permission presentation;
- single 401 coordination;
- logout clears all user state;
- no bearer token attached by Angular;
- CSRF header behavior for eligible mutations;
- login loop protection.

### BFF integration tests

- state, nonce and PKCE validation;
- session fixation prevention;
- cookie attributes;
- CSRF rejection;
- token refresh single-flight behavior;
- issuer/audience mismatch;
- outbound host/path/method allowlist;
- logout and revocation;
- expired/revoked session;
- cross-tenant isolation.

### E2E scenarios

- first login with MFA;
- SSO with existing IdP session;
- permission denied;
- session expiry during navigation and during an edit;
- refresh-token rotation failure;
- logout from one app versus IdP-global logout;
- multiple tabs;
- identity-provider outage;
- BFF failover without session confusion.

## 32. Observability

Capture without secrets:

- login start/success/failure reason category;
- issuer/client/application ID, not token contents;
- session created, rotated, expired and revoked;
- refresh latency and failure category;
- API operation template, status, duration and trace ID;
- 401/403 rate by route and release;
- redirect-loop detection;
- CSRF rejection count;
- unusual cross-tenant/resource denials;
- BFF outbound destination policy rejection.

Never log authorization codes, access tokens, refresh tokens, session cookies, raw ID tokens or password/MFA data.

## 33. Failure policy

| Failure | Angular behavior | BFF behavior |
|---|---|---|
| no local session | show sign-in or begin login | return 401/session anonymous |
| IdP temporarily unavailable | show controlled outage | preserve safe local state; no insecure fallback |
| access token expired | normally invisible | refresh server-side |
| refresh rejected | require login | revoke local session |
| API 403 | show forbidden/business message | retain session; do not convert to login |
| CSRF failure | show safe retry guidance | reject and log security event |
| BFF unavailable | show service unavailable | never expose tokens as fallback |

Do not treat every 403 as authentication expiry.

## 34. Security review checklist

- [ ] Authorization Code flow with PKCE is used.
- [ ] BFF is registered as a confidential client.
- [ ] Access and refresh tokens are never returned to Angular.
- [ ] Session cookie is Secure and HttpOnly.
- [ ] Session ID rotates after authentication.
- [ ] CSRF is enforced server-side for mutations.
- [ ] Return and post-logout URLs are allowlisted.
- [ ] API destinations, paths and methods are explicit.
- [ ] APIs enforce resource authorization independently.
- [ ] Token storage, encryption, refresh and revocation are defined.
- [ ] 401 handling cannot create redirect storms.
- [ ] Logout clears server and browser user state.
- [ ] CSP and Trusted Types policy are evaluated.
- [ ] Logs and telemetry redact identity secrets.
- [ ] Multi-tenant issuer and resource isolation are tested.
- [ ] Failure and disaster-recovery behavior fails closed.

## 35. Interview explanations

Be prepared to explain:

1. authentication versus OAuth authorization;
2. why an ID token should not be used as an API token;
3. Authorization Code flow and PKCE;
4. how SSO works through the identity-provider session;
5. browser-only OAuth versus token-mediating backend versus BFF;
6. why `HttpOnly` reduces token theft but does not eliminate XSS impact;
7. why cookie sessions require CSRF protection;
8. why route guards do not enforce authorization;
9. refresh single-flight handling;
10. local logout versus federated logout;
11. BFF versus API gateway;
12. multi-tenant issuer and resource isolation.

## Official references

- OpenID Connect Core: <https://openid.net/specs/openid-connect-core-1_0.html>
- OAuth 2.0 for Browser-Based Applications: <https://datatracker.ietf.org/doc/draft-ietf-oauth-browser-based-apps/>
- Angular route guards: <https://angular.dev/guide/routing/route-guards>
- Angular HTTP interceptors: <https://angular.dev/guide/http/interceptors>
- Angular security and XSRF: <https://angular.dev/best-practices/security>
- Angular application initializer: <https://angular.dev/api/core/provideAppInitializer>
