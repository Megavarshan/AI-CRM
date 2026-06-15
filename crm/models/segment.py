"""Pydantic models for Segment domain."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class FilterCondition(BaseModel):
    field: str
    op: str    # eq | neq | gt | gte | lt | lte | in | not_in | contains
    value: Any


class FilterSpec(BaseModel):
    operator: str = "AND"   # AND | OR
    conditions: list[Any]   # list[FilterCondition] or nested FilterSpec


class SegmentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    filter_spec: FilterSpec
    nl_query: Optional[str] = None


class SegmentRead(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    filter_spec: FilterSpec
    nl_query: Optional[str] = None
    customer_count: int
    created_at: datetime
    updated_at: datetime


class NL2SegmentRequest(BaseModel):
    query: str


class NL2SegmentResponse(BaseModel):
    filter_spec: FilterSpec
    customer_count: int
    preview: list[str]
    nl_query: str
