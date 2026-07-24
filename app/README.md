# Flock Energy - Urja Meter Ops API

A clean, documented REST API service built in front of the legacy "Urja
Meter Ops" portal used by field/ops staff to look up smart meter data.

* **What this is**: a Python/FastAPI service that logs into the legacy
portal on your behalf, fetches meter/transformer/consumption data, and
exposes it as clean, typed JSON over REST - so another engineer or
program never has to touch the original portal.
* **How the legacy portal actually works**: see [`PROTOCOL.md`](./PROTOCOL.md).
* **API shape**: see [`openapi.json`](./openapi.json), or run the app and
visit `/docs` for an interactive Swagger UI.
* **Reflection**: see the bottom of this file.

## Architecture

```
app/
  config.py   - environment-driven settings (base URL, credentials)
  client.py   - the ONLY module that knows the legacy portal exists.
                Handles login, session/cookie persistence, auto
                re-authentication, and returns raw-but-parsed JSON.
  models.py   - Pydantic models for this service's OWN clean API shape
                (separate from whatever the portal happens to return).
  main.py     - FastAPI routes. Talks only to client.py + models.py.
```

The guiding principle: **`client.py` is the adapter boundary.** Everything
above it should be able to keep working even if the portal's internals
change, as long as `client.py`'s public methods keep their contract.

## Setup

Requires Python 3.10+.

```bash
cd flock-energy-api
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env               # then edit .env if needed
```

## Running

```bash
export $(cat .env | xargs)         # or use a tool like python-dotenv
uvicorn app.main:app --reload
```

Then visit:

* `http://127.0.0.1:8000/docs` - interactive Swagger UI
* `http://127.0.0.1:8000/health` - health check

## Sample requests

```bash
# List meters, page 1
curl "http://127.0.0.1:8000/api/v1/meters?page=1"

# Search meters by number/serial
curl "http://127.0.0.1:8000/api/v1/meters?q=J100005"

# Full detail for one meter (nameplate + hierarchy + location)
curl "http://127.0.0.1:8000/api/v1/meters/J100000"

# Consumption history for one meter
curl "http://127.0.0.1:8000/api/v1/meters/J100000/consumption"

# List transformers, page 1
curl "http://127.0.0.1:8000/api/v1/transformers?page=1"
```

## Assumptions

* The portal's `/login` response shape (`{"type":"redirect",...}`) is a
SvelteKit form-action convention and is stable across sessions - the
adapter checks for it explicitly rather than relying on HTTP status
codes, since the portal returns `200` even for what is logically a
redirect.
* A single shared, long-lived `httpx.Client` session (one login) is
sufficient for this service's scale. A production system serving many
concurrent users would need per-user or pooled sessions instead.
* Hierarchy data is sourced from the bulk export rather than the
per-meter `\_\_data.json` hydration payload, since the latter is an
internal SvelteKit format not intended as a public API (see
PROTOCOL.md for details).
* Consumption data has no date-range parameters as far as was observed;
the service exposes whatever fixed window the portal itself returns.

## Design decisions \& trade-offs

* **FastAPI + httpx** chosen for speed of development and FastAPI's
built-in OpenAPI generation, which satisfies the `openapi.json`
deliverable almost for free.
* **One shared client instance** (`functools.lru\_cache`) rather than
per-request sessions - simpler, appropriate for a take-home, called out
explicitly as a thing that wouldn't scale to production multi-tenant use.
* **Defensive type coercion** (`\_to\_float`) rather than letting Pydantic
validation hard-fail on the portal's string-typed numbers or blank
hierarchy fields - the legacy data has real quality issues (see
PROTOCOL.md) and the service degrades gracefully (returns `null`)
rather than 500ing on a single bad meter.

## What was intentionally skipped (given the time budget)

* **The exact bulk-export endpoint URL was not confirmed** before time
ran out during reconnaissance - it's stubbed with a `TODO` in
`client.py`. This is the single most important thing to fix before
this service is fully usable; `GET /api/v1/meters/{id}` currently
depends on it.
* No caching layer - every request hits the portal live.
* No automated tests.
* No handling of the "network hierarchy as its own browsable structure"
optional extension, or a web client on top of the API.
* No pagination pass-through on `/api/v1/meters/{id}/consumption` (the
portal itself doesn't appear to paginate it, so neither does this).

## What I'd improve with more time

* Confirm and wire up the real export endpoint, and add a fallback path
that reconstructs hierarchy from the `\_\_data.json` format if the export
endpoint is ever unavailable.
* Add a thin caching layer for the bulk export (it's the same \~403-meter
payload every time within a session) with a simple TTL.
* Add integration tests against a mocked portal (recorded fixtures of the
real responses captured during reconnaissance).
* Investigate whether `/portal/search` supports filtering by
status/make/phase server-side, to avoid over-fetching.

## Reflection

**What assumptions did I make?**
See "Assumptions" above - mainly around session handling, the stability
of the SvelteKit redirect-response shape, and treating the bulk export
(rather than the per-meter hydration payload) as the source of truth for
hierarchy.

**Which part was most difficult, and how did I get unstuck?**
Finding the actual data endpoints. The portal's URLs all look like normal
page routes at first glance; the real JSON APIs only became visible by
watching the Network tab while clicking around, and even then some data
(hierarchy) only exists in a non-obvious internal format. Getting unstuck
meant systematically checking every page for background `fetch` requests
rather than assuming the visible URL structure told the whole story.

**If I had another day, what would I improve?**
Confirm the export endpoint URL (the one concrete gap), add tests against
recorded fixtures, add caching, and build out the network-hierarchy
optional extension properly (reconstruct it as a real tree rather than
just embedding hierarchy per meter).

**What mistake did I make while solving this?**
Spent the reconnaissance phase very thoroughly (which paid off - the
protocol map is solid) but ran out of time before confirming the single
most operationally important request: the export button's actual URL. In
hindsight I should have prioritized locking down every endpoint URL
before going deep on data shapes.

**If reviewing my own submission, what would I criticise?**
The `EXPORT\_ENDPOINT\_PATH` TODO is a real gap - `GET /api/v1/meters/{id}`
won't work correctly until it's confirmed. I'd also flag the lack of any
tests, and the single shared session as something that's fine for a
take-home but explicitly not production-ready.



\## Known Limitations



\- \*\*`GET /api/v1/meters/{meter\_id}` (meter detail) is not currently functional.\*\*

&#x20; This endpoint depends on the portal's bulk export (`GET /portal/export`),

&#x20; which requires a signed request (`X-Signature` / `X-Timestamp` headers,

&#x20; HMAC-based, using a secret fetched from `/portal/keys`). The exact signing

&#x20; algorithm could not be confirmed from the minified client-side JavaScript

&#x20; within the time available. This matches PROTOCOL.md's own note that the

&#x20; export endpoint's exact contract was an unconfirmed TODO. The endpoint

&#x20; currently raises a clear `PortalAuthError` rather than crashing silently.

&#x20; Next step: extract and reverse the signing function from the portal's

&#x20; bundled JS (see PROTOCOL.md "Bulk export" section for context).

