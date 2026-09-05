# Security and abuse runbook

This runbook defines Trainspotting's initial abuse controls and the response
procedures that accompany them. FastAPI remains authoritative for identity,
roles, validation, and all writes.

## Enforced boundaries

| Surface | Control | Initial policy |
| --- | --- | --- |
| Public archive reads | Versioned shared cache; no application identity throttle | Keep ordinary research and browsing open |
| Mutation request body | ASGI byte limit | 64 KiB for `POST`, `PUT`, and `PATCH` |
| Account synchronization | Clerk user token bucket | 12 requests per minute |
| Submission writes | Clerk user token bucket | 10 requests per minute |
| Moderator decisions | Clerk user token bucket | 30 requests per minute |
| Administrator canonical writes | Clerk user token bucket | 30 requests per minute |
| Administrator rollback | Separate Clerk user token bucket | 30 requests per minute |

The token buckets refill continuously and return `429 Too Many Requests` with a
`Retry-After` header. They are intentionally keyed by Clerk's verified immutable
user ID, not a client-supplied header. State is bounded and process-local. That
is appropriate for the current single API replica; before adding replicas,
replace it with a shared Redis-compatible limiter or an equivalent trusted edge
control. A process restart may reset counters and must not grant authorization
or bypass validation.

## Unsafe input review

- Pydantic models reject undeclared fields, including client-supplied identity
  and role values.
- Public links accept only HTTP(S), must use a valid public host, and reject
  embedded credentials, private/local IP addresses, control characters, and
  invalid ports.
- React renders submitted text through escaped JSX. The Vanilla client creates
  nodes and assigns `textContent`; it does not insert submitted HTML.
- External links opened in a new tab use `noreferrer` or
  `noopener noreferrer`.
- Database values use bound parameters. The few dynamic table/column fragments
  are selected from server-owned literal record types and fixed schema fields,
  never arbitrary client strings.
- Trainspotting does not fetch submitted source URLs server-side, which avoids
  an SSRF path. If link previews or ingestion later fetch remote content, they
  require DNS rebinding protection, redirect revalidation, response-size and
  time limits, and isolated egress.

Do not strip punctuation or HTML-like text from biographies and descriptions.
Escaping at the rendering boundary preserves historically meaningful content
without turning it into executable markup.

## Responding to limits

For isolated `413` responses, ask the member to shorten narrative text or split
supporting evidence across the allowed source entries. Do not raise the global
body ceiling to accommodate one request.

For isolated `429` responses, honor `Retry-After`. For sustained events:

1. Confirm which route category and authenticated identity is affected without
   placing bearer tokens, email addresses, or request bodies in logs.
2. Check API error rate, latency, and database connection pressure.
3. Temporarily suspend the abusive Clerk account when malicious activity is
   confirmed. Do not alter its local role through any public endpoint.
4. Preserve timestamps, route category, response code, and opaque Clerk user ID
   for incident review; never preserve session tokens.
5. If legitimate traffic exceeds a limit, review measurements and change the
   named route policy through a tested pull request.

Public-read traffic incidents should be handled through caching, CDN controls,
and platform-level mitigation. Do not solve them by making the archive require
login.

## Administrator-role recovery

There is no HTTP or browser endpoint that assigns roles. Normal first-admin
bootstrap uses:

```bash
python -m scripts.bootstrap_admin <immutable-clerk-user-id>
```

The script succeeds only when the user has signed in and no different local
administrator exists. For recovery after the sole administrator loses access:

1. Verify account ownership in Clerk and synchronize the replacement account by
   signing in once.
2. Take a current MySQL recovery point and record the relevant internal user IDs
   and existing roles. Never copy tokens or database credentials into a ticket.
3. Obtain a second reviewer for the proposed replacement.
4. In one database transaction, demote the inaccessible administrator to
   `member`, promote the verified replacement to `admin`, and confirm exactly
   one administrator remains. Roll back the transaction if any precondition
   differs.
5. Record the operator, reviewer, timestamp, reason, and affected opaque user IDs
   in the private incident record.
6. Sign in as the replacement and verify the authorization matrix. Revoke old
   Clerk sessions separately.

Never add a general-purpose role-management endpoint merely to recover access.

## Account-data retention

Clerk owns credentials and sessions. Trainspotting stores only the immutable
Clerk user ID, email, display name, local role, and timestamps needed for account
mapping and accountable moderation. It stores no passwords or session tokens.

- Email and display name may be refreshed from Clerk and must not be copied into
  application logs.
- Submission, decision, promotion, and audit records are retained with their
  internal user relationship because provenance is part of archive integrity.
- On a verified account-deletion request, delete the Clerk account/sessions and
  clear the local email and display name. Retain the opaque identity mapping and
  internal foreign-key record only while moderation provenance or legal/security
  obligations require it; display it publicly as a former member.
- A deleted or suspended account must have role `member` and cannot be reused to
  assign a role to a new identity.
- Export/deletion self-service and configurable retention periods belong to
  USER-01. Until then, deletion is a documented administrator operation with a
  recovery point and verification query.

Review these rules before adding profiles, public activity, ingestion workers,
multiple API replicas, remote URL fetching, or additional personal data.
