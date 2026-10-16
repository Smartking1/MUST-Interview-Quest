"""Database schema for Harbor Market. All money is integer cents."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    orders: Mapped[list[Order]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str] = mapped_column(String, unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    status: Mapped[str] = mapped_column(String)  # placed, shipped, delivered, cancelled
    paid_cents: Mapped[int] = mapped_column(Integer)
    shipping_address: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gateway_payment_ref: Mapped[str | None] = mapped_column(String)
    customer: Mapped[Customer] = relationship(back_populates="orders")
    items: Mapped[list[LineItem]] = relationship(back_populates="order")


class LineItem(Base):
    __tablename__ = "line_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)  # electronics, fashion, home
    price_cents: Mapped[int] = mapped_column(Integer)
    qty: Mapped[int] = mapped_column(Integer, default=1)
    final_sale: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[Order] = relationship(back_populates="items")


class Return(Base):
    """Condition fields are set by the warehouse on receipt, never from chat."""

    __tablename__ = "returns"
    id: Mapped[int] = mapped_column(primary_key=True)
    line_item_id: Mapped[int] = mapped_column(ForeignKey("line_items.id"))
    status: Mapped[str] = mapped_column(String)  # authorized, received
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened: Mapped[bool | None] = mapped_column(Boolean)
    tags_attached: Mapped[bool | None] = mapped_column(Boolean)


class Refund(Base):
    """One executed refund. decision_id is unique, so a decision pays out once."""

    __tablename__ = "refunds"
    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[str] = mapped_column(String, unique=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    line_item_ids: Mapped[list[int]] = mapped_column(JSON)
    amount_cents: Mapped[int] = mapped_column(Integer)
    rule_ids: Mapped[list[str]] = mapped_column(JSON)
    issuer: Mapped[str] = mapped_column(String)
    gateway_ref: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Escalation(Base):
    __tablename__ = "escalations"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"))  # None if not verified
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    line_item_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    request: Mapped[str] = mapped_column(Text)
    rule_ids: Mapped[list[str]] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    proposed_amount_cents: Mapped[int | None] = mapped_column(Integer)
    image_description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="open")  # open, approved, denied
    resolved_by: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GatewayLedger(Base):
    """Every call made to a payment gateway, by either agent. Eval scorers read this."""

    __tablename__ = "gateway_ledger"
    id: Mapped[int] = mapped_column(primary_key=True)
    agent: Mapped[str] = mapped_column(String)  # trusted, baseline
    order_id: Mapped[int] = mapped_column(Integer)
    amount_cents: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str | None] = mapped_column(String)
    gateway: Mapped[str] = mapped_column(String)
    gateway_ref: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
