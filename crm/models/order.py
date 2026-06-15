"""Pydantic models for Order domain."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class OrderCreate(BaseModel):
    customer_id: UUID
    order_date: datetime
    amount: float = Field(..., gt=0, description="Amount in INR")
    category: Optional[str] = None
    product_name: Optional[str] = None
    status: str = Field("completed", pattern=r"^(completed|returned|cancelled)$")


class OrderRead(BaseModel):
    id: UUID
    customer_id: UUID
    order_date: datetime
    amount: float
    category: Optional[str] = None
    product_name: Optional[str] = None
    status: str
    created_at: datetime


class OrderBulkCreate(BaseModel):
    orders: list[OrderCreate]
