"""
Flock Energy - Urja Meter Ops API

A clean, documented REST API service in front of the legacy Urja Meter Ops
portal. See README.md for setup/run instructions and PROTOCOL.md for how
the legacy portal itself works under the hood.
"""

from functools import lru_cache
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from app.client import UrjaPortalClient, PortalAuthError
from app.models import (
    MeterSummary,
    MeterListResponse,
    MeterDetail,
    MeterHierarchy,
    HierarchyNode,
    MeterLocation,
    ConsumptionReading,
    TransformerSummary,
    TransformerListResponse,
)

app = FastAPI(
    title="Flock Energy - Urja Meter Ops API",
    version="1.0.0",
    description=(
        "Clean REST API proxy layer over the legacy Urja Meter Ops portal. "
        "See /docs for interactive testing."
    ),
)


@lru_cache()
def get_client() -> UrjaPortalClient:
    """
    Single shared portal client for the process.

    A real production service would use per-request auth / a connection
    pool / dependency injection; a single shared session is a deliberate
    simplification for this take-home (see README trade-offs section).
    """
    return UrjaPortalClient()


def _to_float(value) -> Optional[float]:
    """Best-effort conversion of the portal's string numbers to floats."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _hierarchy_node(raw: Optional[dict]) -> Optional[HierarchyNode]:
    if not raw:
        return None
    return HierarchyNode(name=raw.get("name") or None, code=raw.get("code") or None)


@app.get("/api/v1/meters", response_model=MeterListResponse)
def list_meters(
    page: int = Query(1, ge=1),
    q: str = Query("", description="Search by meter number or serial"),
):
    """List meters (paginated), mirroring the portal's meter list/search."""
    raw = get_client().get_meters(page=page, query=q)
    meters = [
        MeterSummary(
            meter_id=m["meterId"],
            serial_no=m["serialNo"],
            make=m["make"],
            phase_type=m["phaseType"],
            install_status=m["installStatus"],
            dt_code=m["dtCode"],
        )
        for m in raw["data"]
    ]
    return MeterListResponse(
        data=meters, total=raw["total"], page=raw["page"], pageSize=raw["pageSize"]
    )


@app.get("/api/v1/meters/{meter_id}", response_model=MeterDetail)
def get_meter(meter_id: str):
    """
    Full detail for a single meter: nameplate + hierarchy + location.

    Hierarchy and location are sourced from the bulk export (see
    PROTOCOL.md) since the portal has no clean single-meter detail
    endpoint with hierarchy included.
    """
    client = get_client()
    try:
        export = client.get_all_meters_export()
    except PortalAuthError as e:
        raise HTTPException(
            status_code=501,
            detail=f"Bulk export endpoint not yet confirmed - see client.py TODO ({e})",
        )

    match = next((m for m in export if m["meterId"] == meter_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Meter {meter_id} not found")

    geo = match.get("geo") or {}
    hierarchy_raw = match.get("hierarchy") or {}

    return MeterDetail(
        meter_id=match["meterId"],
        serial_no=match["serialNo"],
        make=match["make"],
        phase_type=match["phaseType"],
        install_status=match["installStatus"],
        install_type=match.get("installType"),
        dt_code=match["dtCode"],
        hierarchy=MeterHierarchy(
            zone=_hierarchy_node(hierarchy_raw.get("zone")),
            circle=_hierarchy_node(hierarchy_raw.get("circle")),
            division=_hierarchy_node(hierarchy_raw.get("division")),
            subdivision=_hierarchy_node(hierarchy_raw.get("subdivision")),
            substation=_hierarchy_node(hierarchy_raw.get("substation")),
            feeder=_hierarchy_node(hierarchy_raw.get("feeder")),
            dt=_hierarchy_node(hierarchy_raw.get("dt")),
        ),
        location=MeterLocation(
            latitude=_to_float(geo.get("lat")), longitude=_to_float(geo.get("lng"))
        ),
    )


@app.get("/api/v1/meters/{meter_id}/consumption", response_model=list[ConsumptionReading])
def get_meter_consumption(meter_id: str):
    """30-minute interval consumption history for a single meter."""
    readings = get_client().get_meter_energy(meter_id)
    return [
        ConsumptionReading(
            timestamp=r["timestamp"],
            kwh=_to_float(r.get("kwh")),
            kvah=_to_float(r.get("kvah")),
            volt_r=_to_float(r.get("voltR")),
        )
        for r in readings
    ]


@app.get("/api/v1/transformers", response_model=TransformerListResponse)
def list_transformers(page: int = Query(1, ge=1)):
    """List distribution transformers (paginated)."""
    raw = get_client().get_transformers(page=page)
    transformers = [
        TransformerSummary(
            code=t["code"],
            name=t["name"],
            feeder_code=t["feederCode"],
            capacity_kva=t["capacityKva"],
        )
        for t in raw["data"]
    ]
    return TransformerListResponse(
        data=transformers, total=raw["total"], page=raw["page"], page_size=raw["pageSize"]
    )


@app.get("/health")
def health():
    return {"status": "ok"}
