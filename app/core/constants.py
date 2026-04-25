"""
app/core/constants.py — All shared Enums and constants for HopeAid.

These are used by both SQLAlchemy column types and Pydantic schemas.
Keep them here to avoid circular imports.
"""

from enum import Enum


# ─── Organization ────────────────────────────────────────────────────────────

class OrgStatus(str, Enum):
    active = "active"
    suspended = "suspended"
    pending = "pending"


# ─── User / Auth ─────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    super_admin = "super_admin"
    admin = "admin"
    org_manager = "org_manager"
    field_coordinator = "field_coordinator"
    volunteer = "volunteer"
    reviewer = "reviewer"


# ─── Person ──────────────────────────────────────────────────────────────────

class Gender(str, Enum):
    male = "male"
    female = "female"
    other = "other"
    prefer_not_to_say = "prefer_not_to_say"


# ─── Case ────────────────────────────────────────────────────────────────────

class CaseCategory(str, Enum):
    food = "food"
    shelter = "shelter"
    medical = "medical"
    clothing = "clothing"
    water = "water"
    logistics = "logistics"
    other = "other"


class UrgencyLevel(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class DisasterType(str, Enum):
    flood = "flood"
    earthquake = "earthquake"
    cyclone = "cyclone"
    drought = "drought"
    conflict = "conflict"
    pandemic = "pandemic"
    fire = "fire"
    other = "other"


class CaseStatus(str, Enum):
    new = "new"
    verified = "verified"
    assigned = "assigned"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"
    rejected = "rejected"


class VerificationStatus(str, Enum):
    pending = "pending"
    verified = "verified"
    disputed = "disputed"


class SourceType(str, Enum):
    manual = "manual"
    typed = "typed"
    scanned = "scanned"
    voice = "voice"


# ─── Volunteer ───────────────────────────────────────────────────────────────

class DutyType(str, Enum):
    full_time = "full_time"
    part_time = "part_time"
    on_call = "on_call"


class AvailabilityStatus(str, Enum):
    available = "available"
    busy = "busy"
    unavailable = "unavailable"
    on_leave = "on_leave"


# ─── Assignment ──────────────────────────────────────────────────────────────

class AssignmentStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


# ─── Inventory ───────────────────────────────────────────────────────────────

class InventoryItemType(str, Enum):
    food = "food"
    medicine = "medicine"
    clothing = "clothing"
    shelter = "shelter"
    equipment = "equipment"
    water = "water"
    hygiene = "hygiene"
    other = "other"


class InventoryStatus(str, Enum):
    available = "available"
    low_stock = "low_stock"
    out_of_stock = "out_of_stock"
    expired = "expired"


class MovementType(str, Enum):
    received = "received"
    distributed = "distributed"
    adjusted = "adjusted"
    expired = "expired"
    returned = "returned"


# ─── Upload ──────────────────────────────────────────────────────────────────

class FileType(str, Enum):
    image = "image"
    pdf = "pdf"
    audio = "audio"
    document = "document"


class UploadSource(str, Enum):
    case_form = "case_form"
    id_proof = "id_proof"
    photo = "photo"
    voice_note = "voice_note"
    other = "other"


class ProcessingStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


# ─── AI Extraction ───────────────────────────────────────────────────────────

class AIInputType(str, Enum):
    ocr = "ocr"
    free_text = "free_text"
    voice = "voice"


# ─── Alert ───────────────────────────────────────────────────────────────────

class AlertType(str, Enum):
    urgent_case = "urgent_case"
    inventory_low = "inventory_low"
    unassigned_critical = "unassigned_critical"
    conflict_detected = "conflict_detected"
    volunteer_overloaded = "volunteer_overloaded"
    system = "system"


class AlertStatus(str, Enum):
    active = "active"
    acknowledged = "acknowledged"
    resolved = "resolved"


class RecipientType(str, Enum):
    admin = "admin"
    org_manager = "org_manager"
    field_coordinator = "field_coordinator"
    all = "all"


# ─── Report ──────────────────────────────────────────────────────────────────

class ReportType(str, Enum):
    cases = "cases"
    volunteers = "volunteers"
    inventory = "inventory"
    summary = "summary"


class ReportFormat(str, Enum):
    csv = "csv"
    pdf = "pdf"
    json = "json"


class ReportStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


# ─── RBAC Permissions ────────────────────────────────────────────────────────

# Roles that can manage org-wide settings
ORG_MANAGERS = {UserRole.super_admin, UserRole.admin, UserRole.org_manager}

# Roles that can approve/reject cases
APPROVERS = {UserRole.super_admin, UserRole.admin, UserRole.org_manager, UserRole.reviewer}

# Roles that can do field operations
FIELD_ROLES = {UserRole.field_coordinator, UserRole.volunteer}

# All authenticated roles
ALL_ROLES = set(UserRole)

# ─── File Upload ─────────────────────────────────────────────────────────────

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_DOCUMENT_TYPES = {"application/pdf"}
ALLOWED_AUDIO_TYPES = {"audio/wav", "audio/mpeg", "audio/mp4"}
ALLOWED_UPLOAD_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_DOCUMENT_TYPES | ALLOWED_AUDIO_TYPES

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# ─── Pagination ──────────────────────────────────────────────────────────────

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# ─── Risk Score Weights ──────────────────────────────────────────────────────

RISK_WEIGHTS = {
    "urgency": 0.35,
    "vulnerability": 0.20,
    "disaster": 0.15,
    "scale": 0.10,
    "time": 0.10,
    "essentials": 0.10,
}

# ─── Allocation Score Weights ────────────────────────────────────────────────

ALLOCATION_WEIGHTS = {
    "skill_match": 30,
    "availability": 20,
    "distance": 20,
    "language_match": 10,
    "transport": 10,
    "reliability": 5,
    "workload": 5,
}
