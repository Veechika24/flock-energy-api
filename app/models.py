"""
Pydantic models describing the *clean* API this service exposes.

These are intentionally separate from whatever shape the legacy portal
happens to return - the adapter layer (client.py) is responsible for
translating portal quirks (string numbers, empty-string codes, etc.) into
these well-typed models.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class HierarchyNode(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None


class MeterHierarchy(BaseModel):
    zone: Optional[HierarchyNode] = None
    circle: Optional[HierarchyNode] = None
    division: Optional[HierarchyNode] = None
    subdivision: Optional[HierarchyNode] = None
    substation: Optional[HierarchyNode] = None
    feeder: Optional[HierarchyNode] = None
    dt: Optional[HierarchyNode] = None


class MeterSummary(BaseModel):
    """A single row as returned by the meters list/search endpoint."""

    meter_id: str
    serial_no: str
    make: str
    phase_type: str
    install_status: str
    dt_code: str


class MeterListResponse(BaseModel):
    data: List[MeterSummary]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")

    class Config:
        populate_by_name = True


class MeterLocation(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class MeterDetail(BaseModel):
    meter_id: str
    serial_no: str
    make: str
    phase_type: str
    install_status: str
    install_type: Optional[str] = None
    dt_code: str
    hierarchy: Optional[MeterHierarchy] = None
    location: Optional[MeterLocation] = None


class ConsumptionReading(BaseModel):
    timestamp: str
    kwh: Optional[float] = None
    kvah: Optional[float] = None
    volt_r: Optional[float] = None


class TransformerSummary(BaseModel):
    code: str
    name: str
    feeder_code: str
    capacity_kva: float


class TransformerListResponse(BaseModel):
    data: List[TransformerSummary]
    total: int
    page: int
    page_size: int
