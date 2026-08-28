"""ORM models — single source of truth for the relational schema.

The schema is designed upfront for ALL phases (Master-prompt §1B RULE):
Phase 0 tables are fully operational; Phase 1/2 tables exist so later
phases never break earlier ones.  Data-integrity rules (§58):
Created/Updated stamps on every meaningful record, soft deletes for
sensitive entities, optimistic-concurrency `version` columns (§35).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, utcnow

# ---------------------------------------------------------------------------
# Identity & RBAC
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(256))
    email: Mapped[Optional[str]] = mapped_column(String(190), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    roles: Mapped[list["Role"]] = relationship(
        secondary="user_roles", back_populates="users", lazy="selectin"
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    title_fa: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    permissions: Mapped[list["Permission"]] = relationship(
        secondary="role_permissions", back_populates="roles", lazy="selectin"
    )
    users: Mapped[list["User"]] = relationship(
        secondary="user_roles", back_populates="roles", lazy="selectin"
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(96), unique=True)  # e.g. "equipment.edit"
    module: Mapped[str] = mapped_column(String(48), index=True)
    title_fa: Mapped[str] = mapped_column(String(128))

    roles: Mapped[list["Role"]] = relationship(
        secondary="role_permissions", back_populates="permissions", lazy="selectin"
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), index=True)
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), index=True
    )


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), index=True)


# ---------------------------------------------------------------------------
# Base data (dropdown lists §37)
# ---------------------------------------------------------------------------


class Factory(Base):
    __tablename__ = "factories"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class EquipmentCategory(Base):
    __tablename__ = "equipment_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("equipment_categories.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class LookupItem(Base):
    """Generic configurable dropdown lists (§37): activity types, intervals…"""

    __tablename__ = "lookup_items"
    __table_args__ = (UniqueConstraint("list_code", "code", name="uq_lookup_list_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    list_code: Mapped[str] = mapped_column(String(48), index=True)  # activity_type, interval…
    code: Mapped[str] = mapped_column(String(48))
    title_fa: Mapped[str] = mapped_column(String(128))
    extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # e.g. {"days": 30}
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ---------------------------------------------------------------------------
# Equipment module (§11) — hierarchy: Company→Factory→Category→Equipment→…
# ---------------------------------------------------------------------------

EQUIPMENT_LEVELS = ("equipment", "subsystem", "component", "subcomponent")


class Equipment(Base):
    __tablename__ = "equipment"
    __table_args__ = (UniqueConstraint("code", name="uq_equipment_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(190))
    level: Mapped[str] = mapped_column(String(16), default="equipment")

    factory_id: Mapped[Optional[int]] = mapped_column(ForeignKey("factories.id"), nullable=True)
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("equipment_categories.id"), nullable=True
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("equipment.id"), nullable=True, index=True
    )

    location: Mapped[Optional[str]] = mapped_column(String(190), nullable=True)
    # Location properties (§11 MODULE EQUIPMENT) — stored as equipment
    # properties only; never part of the hierarchy tree.
    hall: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)      # سالن
    dept: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)      # بخش
    line: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)      # خط
    component_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # نوع قطعه: پمپ/تابلو برق/دینام…
    criticality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # مجموع Safety+Product+Cost+Repair
    position: Mapped[Optional[str]] = mapped_column(String(190), nullable=True)  # موقعیت
    location_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)  # §34: archive, never hard-delete
    manufacturer: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    criticality: Mapped[str] = mapped_column(String(16), default="medium")  # low/medium/high/critical
    status: Mapped[str] = mapped_column(String(32), default="active")

    technical_specs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    dynamic_fields: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    version: Mapped[int] = mapped_column(Integer, default=1)  # optimistic concurrency §35
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    factory = relationship("Factory", lazy="joined")
    category = relationship("EquipmentCategory", lazy="joined")
    parent = relationship(
        "Equipment", remote_side=[id], back_populates="children", lazy="joined"
    )
    children: Mapped[list["Equipment"]] = relationship(
        "Equipment", back_populates="parent", lazy="selectin"
    )
    # Polymorphic attachment list (entity_type/entity_id) — view only.
    files: Mapped[list["FileObject"]] = relationship(
        "FileObject",
        primaryjoin=(
            "and_(Equipment.id == foreign(FileObject.entity_id),"
            " FileObject.entity_type == 'equipment')"
        ),
        lazy="selectin",
        viewonly=True,
    )
    plans: Mapped[list["MaintenancePlan"]] = relationship(
        "MaintenancePlan",
        primaryjoin="MaintenancePlan.equipment_id == Equipment.id",
        lazy="selectin",
        viewonly=True,
    )


class FileObject(Base):
    """Attachments linked to any entity (§45): equipment, work orders, plans…"""

    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)  # equipment | workorder | …
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    original_name: Mapped[str] = mapped_column(String(190))
    stored_name: Mapped[str] = mapped_column(String(128))
    path: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    size: Mapped[int] = mapped_column(Integer, default=0)

    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------------------
# Maintenance Plan (§14) — Phase 0 basic version
# ---------------------------------------------------------------------------


class MaintenancePlan(Base):
    __tablename__ = "maintenance_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)

    work_class: Mapped[Optional[str]] = mapped_column(String(48), nullable=True)   # PM / CM / …
    work_title: Mapped[str] = mapped_column(String(190))
    target_level: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    target_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipment.id"), nullable=True)
    activity_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    activity_type: Mapped[str] = mapped_column(String(48), default="inspection")
    net_activity: Mapped[bool] = mapped_column(Boolean, default=False)
    stop_required: Mapped[bool] = mapped_column(Boolean, default=False)
    interval_code: Mapped[str] = mapped_column(String(32), default="monthly")
    interval_days: Mapped[int] = mapped_column(Integer, default=30)
    performer: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_execution: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_due: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    version: Mapped[int] = mapped_column(Integer, default=1)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    equipment = relationship("Equipment", foreign_keys=[equipment_id], lazy="joined")
    target = relationship("Equipment", foreign_keys=[target_id])


class PMConsumable(Base):
    """Consumable parts required by a PM plan (برنامه نت با قطعات مصرفی)."""

    __tablename__ = "pm_consumables"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("maintenance_plans.id"), index=True)
    equipment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("equipment.id"), index=True, nullable=True)
    part_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parts.id"), nullable=True)
    part_name: Mapped[str] = mapped_column(String(190))
    quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    plan = relationship("MaintenancePlan", lazy="joined")
    equipment = relationship("Equipment", lazy="joined")
    part = relationship("Part", lazy="joined")


# ---------------------------------------------------------------------------
# Bulk import (§11 / MODULE EQUIPMENT — Bulk Data Charge)
# ---------------------------------------------------------------------------


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), default="equipment")
    filename: Mapped[str] = mapped_column(String(190))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|confirmed|rolled_back
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)
    auto_create_lookups: Mapped[bool] = mapped_column(Boolean, default=False)
    summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Bulk Data Charge Center (§6B)
    mapping: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    raw_file_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    rows: Mapped[list["ImportBatchRow"]] = relationship(
        "ImportBatchRow", cascade="all, delete-orphan", lazy="selectin"
    )


class ImportBatchRow(Base):
    __tablename__ = "import_batch_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    raw: Mapped[dict] = mapped_column(JSON)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    errors: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    created_equipment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("equipment.id"), nullable=True
    )
    # §6B staging diff
    staging_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    # new | update | conflict | rejected | resolved
    matched_equipment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("equipment.id"), nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# Audit (§39)
# ---------------------------------------------------------------------------


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(48), index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    old_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    device: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    user = relationship("User", lazy="joined")


# ---------------------------------------------------------------------------
# Phase 1 schema prep (§1B RULE) — Requests / Work Orders / Notifications.
# Implemented UI/workflow lands in Phase 1; the schema is already stable.
# ---------------------------------------------------------------------------


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(48))  # request | workorder | pm | … (§31)
    title: Mapped[str] = mapped_column(String(190))
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    link: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkRequest(Base):
    __tablename__ = "work_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(190))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_type: Mapped[str] = mapped_column(String(32), default="repair")  # §17
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    equipment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipment.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    decision_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    requested_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    equipment = relationship("Equipment", lazy="joined")
    requester = relationship("User", foreign_keys=[requested_by], lazy="joined")


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(190))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_id: Mapped[Optional[int]] = mapped_column(ForeignKey("work_requests.id"), nullable=True)
    equipment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipment.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="created")  # §18 workflow states
    work_class: Mapped[Optional[str]] = mapped_column(String(48), nullable=True)
    execution_mode: Mapped[str] = mapped_column(String(16), default="internal")  # internal/external
    permit_required: Mapped[bool] = mapped_column(Boolean, default=False)
    assigned_to: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)  # §35 concurrency
    offline_sync_status: Mapped[str] = mapped_column(String(16), default="synced")  # §20B
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    equipment = relationship("Equipment", lazy="joined")
    assignee = relationship("User", foreign_keys=[assigned_to], lazy="joined")
    request = relationship("WorkRequest", lazy="joined")
    approvals: Mapped[list["WorkOrderApproval"]] = relationship(
        "WorkOrderApproval", lazy="selectin", cascade="all, delete-orphan",
        order_by="WorkOrderApproval.id",
    )
    time_logs: Mapped[list["WorkOrderTimeLog"]] = relationship(
        "WorkOrderTimeLog", lazy="selectin", cascade="all, delete-orphan",
        order_by="WorkOrderTimeLog.at",
    )


class WorkOrderApproval(Base):
    """Digital Permit / HSE approvals (§19): multiple approvers, signature meta."""

    __tablename__ = "work_order_approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), index=True)
    step: Mapped[str] = mapped_column(String(32), default="permit")  # permit | final
    approver_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/approved/rejected
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signature: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    approver = relationship("User", lazy="joined")


class WorkOrderTimeLog(Base):
    """Technician execution timeline (§20): start/pause/resume/finish."""

    __tablename__ = "work_order_time_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(16))  # start | pause | resume | finish
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    local_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # §20B dedupe
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user = relationship("User", lazy="joined")


class WorkOrderNote(Base):
    """Execution notes (text / voice-transcribed) with offline dedupe (§20/§20B)."""

    __tablename__ = "work_order_notes"
    __table_args__ = (UniqueConstraint("work_order_id", "local_id", name="uq_wo_note_local"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16), default="text")  # text | voice
    local_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    device_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user = relationship("User", lazy="joined")


class WorkOrderCost(Base):
    """Cost entries per work order (§25)."""

    __tablename__ = "work_order_costs"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), index=True)
    cost_type: Mapped[str] = mapped_column(String(48))
    amount: Mapped[float] = mapped_column(default=0)
    currency: Mapped[str] = mapped_column(String(8), default="IRR")
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MaintenanceHistory(Base):
    """Main maintenance records (§16) — created from completed work orders."""

    __tablename__ = "maintenance_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    work_order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("work_orders.id"), nullable=True)
    work_type: Mapped[str] = mapped_column(String(48), default="repair")
    title: Mapped[str] = mapped_column(String(190))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    technician_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    equipment = relationship("Equipment", lazy="joined")
    technician = relationship("User", lazy="joined")


class SyncConflict(Base):
    """Offline version conflicts (§20B/§35): both versions kept, manager resolves."""

    __tablename__ = "sync_conflicts"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    base_version: Mapped[int] = mapped_column(Integer)
    server_version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | resolved
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkOrderStatusLog(Base):
    __tablename__ = "work_order_status_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"), index=True)
    from_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32))
    changed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------------------
# Phase 2 (§1B): Checklists (§15), Risks (§28), Calibration (§29),
# Inventory/Critical parts (§23/§24), Internal consultation (§32).
# ---------------------------------------------------------------------------


class ChecklistTemplate(Base):
    __tablename__ = "checklist_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(190))
    period_code: Mapped[str] = mapped_column(String(16), default="monthly")  # monthly/yearly/custom
    custom_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    equipment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipment.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    equipment = relationship("Equipment", lazy="joined")
    items: Mapped[list["ChecklistItem"]] = relationship(
        "ChecklistItem", lazy="selectin", cascade="all, delete-orphan",
        order_by="ChecklistItem.sort_order")


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("checklist_templates.id"), index=True)
    text: Mapped[str] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ChecklistRun(Base):
    __tablename__ = "checklist_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("checklist_templates.id"), index=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    technician_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    run_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | complete
    result_summary: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # pass | fail
    general_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    template = relationship("ChecklistTemplate", lazy="joined")
    equipment = relationship("Equipment", lazy="joined")
    technician = relationship("User", lazy="joined")
    items: Mapped[list["ChecklistRunItem"]] = relationship(
        "ChecklistRunItem", lazy="selectin", cascade="all, delete-orphan",
        order_by="ChecklistRunItem.id")


class ChecklistRunItem(Base):
    __tablename__ = "checklist_run_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("checklist_runs.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("checklist_items.id"))
    result: Mapped[str] = mapped_column(String(20), default="pending")
    # pending | ok | not_ok | na | requires_action (§15)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    item = relationship("ChecklistItem", lazy="joined")


class RiskItem(Base):
    """Risk & Opportunity register (§28)."""

    __tablename__ = "risk_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(16), default="equipment")  # equipment | process
    kind: Mapped[str] = mapped_column(String(16), default="risk")  # risk | opportunity
    equipment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipment.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(190))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    probability: Mapped[int] = mapped_column(Integer, default=1)  # 1..5
    impact: Mapped[int] = mapped_column(Integer, default=1)       # 1..5
    risk_score: Mapped[int] = mapped_column(Integer, default=1)   # p*i
    mitigation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    equipment = relationship("Equipment", lazy="joined")
    owner = relationship("User", foreign_keys=[owner_id], lazy="joined")


class CalibrationItem(Base):
    """Calibration plans for measuring instruments (§29)."""

    __tablename__ = "calibration_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), index=True)
    standard: Mapped[Optional[str]] = mapped_column(String(190), nullable=True)
    last_calibration: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    interval_days: Mapped[int] = mapped_column(Integer, default=365)
    next_due: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # pass/fail/adjusted
    certificate_file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("files.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    equipment = relationship("Equipment", lazy="joined")


class Supplier(Base):
    """تأمین‌کنندگان قطعات یدکی (جدول 40 رکوردی در اکسس — بخش ۴.۵ سند)."""

    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("name", name="uq_suppliers_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(190))
    contact: Mapped[Optional[str]] = mapped_column(String(190), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Part(Base):
    """Inventory items fed by the external-warehouse Excel gateway (§23)
    and scored for criticality (§24)."""

    __tablename__ = "parts"
    __table_args__ = (UniqueConstraint("code", name="uq_parts_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(190))
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    stock_qty: Mapped[float] = mapped_column(default=0)
    min_qty: Mapped[float] = mapped_column(default=0)
    order_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # SpareOrder در Access
    criticality: Mapped[str] = mapped_column(String(16), default="medium")
    lead_time_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    supplier: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    alternative_part: Mapped[Optional[str]] = mapped_column(String(190), nullable=True)
    equipment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipment.id"), nullable=True)
    import_batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("import_batches.id"), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    equipment = relationship("Equipment", lazy="joined")
    supplier_ref = relationship("Supplier", lazy="joined")


class Conversation(Base):
    """In-app consultation threads (§32 core)."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_a: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user_b: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    subject: Mapped[Optional[str]] = mapped_column(String(190), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    a = relationship("User", foreign_keys=[user_a], lazy="joined")
    b = relationship("User", foreign_keys=[user_b], lazy="joined")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    sender = relationship("User", lazy="joined")
