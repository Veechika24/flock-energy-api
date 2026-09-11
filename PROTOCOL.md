# PROTOCOL.md - Urja Meter Ops, as discovered

Reverse-engineered by logging into the portal, clicking through the UI, and
inspecting Network requests in Chrome DevTools (Fetch/XHR filter).

## Stack

The portal is built with **SvelteKit** (confirmed via
`<body data-sveltekit-preload-data="hover">` in the page source, and the
`__data.json` page-hydration requests it fires on navigation).

## Authentication

```
POST /login
Content-Type: application/x-www-form-urlencoded
Body: email=<email>&password=<password>
```

- On success, responds `200 OK` with body `{"type":"redirect","status":303,"location":"/meters"}`
  and sets a session cookie: `__Secure-better-auth.session_token`.
  This is a SvelteKit form-action response shape, not a real HTTP redirect -
  clients must check the response body's `type` field rather than the
  status code alone.
- The cookie name indicates the portal uses the **better-auth** library for
  session management.
- Subsequent requests are authenticated purely via that cookie - no bearer
  token or CSRF header was observed.
- Session expiry behaviour (exact TTL, and what a request looks like once
  expired) was not fully characterised in the time available - the adapter
  assumes a `401` or a redirect back to `/login` means "re-authenticate and
  retry once."

## Clean JSON endpoints

All of these return `Content-Type: application/json` and were confirmed via
DevTools, not guessed:

| Purpose | Method | Path | Notes |
|---|---|---|---|
| List meters | GET | `/portal/meters/search?q=&page=N` | `q` also matches by serial number; 20 per page |
| Meter location | GET | `/portal/meters/{meterId}/geo` | lat/lng returned as **strings** |
| Meter consumption | GET | `/portal/meters/{meterId}/energy` | fixed ~1 week window, no pagination or date params observed; all values (kwh/kvah/voltR) returned as **strings** |
| List transformers | GET | `/portal/dts?page=N` | 20 per page |

List responses share one pagination envelope:

```json
{ "data": [ ... ], "total": 403, "page": 1, "pageSize": 20 }
```

## Bulk export ("Export all meters" button, on the Transformers page)

Downloads `meter-export.json` - a **flat JSON array of all 403 meters**,
each with nameplate fields *and* the full hierarchy *and* geo embedded
in one object:

```json
{
  "meterId": "J100000",
  "serialNo": "SE33962",
  "make": "HPL",
  "phaseType": "single",
  "installStatus": "Decommissioned",
  "installType": "Whole Current",
  "build": "legacy",
  "dtCode": "DT-001",
  "hierarchy": {
    "zone": {"name": "Jaipur Zone 1", "code": "Z-01"},
    "circle": {"name": "Circle 1", "code": "C-01"},
    "division": {"...": "..."},
    "subdivision": {"...": "..."},
    "substation": {"...": "..."},
    "feeder": {"...": "..."},
    "dt": {"name": "Malviya Nagar DT 1", "code": "DT-001"}
  },
  "geo": {"lat": 26.938961002479868, "lng": 75.83095696146852}
}
```

This is the **only** clean source of hierarchy data found - see below.

**Important gap**: the exact request (URL/method) that this button fires
was not captured before time ran out. It is very likely a `GET` to
something like `/portal/meters/export`, but this needs to be confirmed
in DevTools before `client.py`'s `EXPORT_ENDPOINT_PATH` can be trusted.
This is flagged as a `TODO` in the code.

## Hierarchy data on the single-meter detail page (messy path)

The meter detail page (`/meters/{meterId}`) shows the full breadcrumb
hierarchy (Zone > Circle > Division > Subdivision > Substation > Feeder >
DT), but it is **not** served by a clean JSON endpoint. Instead it comes
through SvelteKit's internal page-hydration request:

```
GET /meters/{meterId}/__data.json?x-sveltekit-invalidated=...
```

This returns a compact, deduplicated array format where fields reference
other array indices (SvelteKit's internal serialization, not a stable
public API). Example: `"detail": 2` means "the value is at index 2 of the
`data` array." This is tightly coupled to the frontend's internals and
could change on any SvelteKit/portal upgrade, so the adapter deliberately
does **not** parse it - it uses the bulk export instead, which is both
cleaner and (for this use case) sufficient.

## Data quality issues observed

These are real, and any client needs to handle them rather than assume
clean input:

- **Empty-string hierarchy fields**: some records have
  `"circle": {"name": "", "code": "C-01"}` or similar - name/code can be
  blank even when the sibling field is populated.
- **Duplicate DT code, inconsistent name**: meters `J100400`-`J100402` all
  have `dtCode: "DT-007"`, but their `dt.name` is `"Old Malviya Nagar Xfmr"`,
  while every other meter tagged `DT-007` calls it `"Sanganer DT 7"`. Same
  code, two different names in the source data - a real-world data quality
  issue rather than a bug in this service.
- **String-typed numbers throughout**: `geo.lat`/`geo.lng` and all of
  `energy`'s `kwh`/`kvah`/`voltR` fields are returned as JSON strings, not
  numbers. The adapter converts these to floats defensively (returning
  `null` rather than raising if a value is unparseable).

## Not yet investigated

- Exact session expiry / re-authentication behaviour under a long-running
  client (see Robustness in the optional extensions).
- Whether `/portal/search` supports any other query parameters (sorting,
  filtering by status/make/phase, etc.) beyond `q` and `page`.
- The exact export endpoint URL (see above).
