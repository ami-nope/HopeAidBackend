"""
app/db/seed.py — Seed script for local development.

Creates:
  - 1 organization (HopeAid Demo Org)
  - 1 super_admin user
  - 1 org_manager user
  - 2 households with persons
  - 3 cases
  - 2 volunteers
  - 3 inventory items

Run with:
  python -m app.db.seed
"""

import uuid

from app.core.security import hash_password
from app.core.constants import (
    AvailabilityStatus,
    CaseCategory,
    CaseStatus,
    DisasterType,
    DutyType,
    InventoryItemType,
    OrgStatus,
    UrgencyLevel,
    UserRole,
)
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.models.case import Case
from app.models.household import Household
from app.models.inventory import InventoryItem
from app.models.organization import Organization
from app.models.person import Person
from app.models.user import User
from app.models.volunteer import Volunteer


def seed():
    # Create all tables if they don't exist yet
    print("[*] Creating tables...")
    Base.metadata.create_all(bind=engine)

    print("[*] Seeding data...")
    db = SessionLocal()
    try:
        # ── Organization ──────────────────────────────────────────────────────
        org = Organization(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            name="HopeAid Demo Organization",
            slug="hopeaid-demo",
            status=OrgStatus.active,
        )
        db.add(org)
        db.flush()   # flush to get the org.id before referencing it below

        # ── Users ─────────────────────────────────────────────────────────────
        super_admin = User(
            organization_id=None,
            name="Platform Admin",
            email="admin@hopeaid.platform",
            hashed_password=hash_password("Admin@1234"),
            role=UserRole.super_admin,
        )
        db.add(super_admin)

        org_manager = User(
            organization_id=org.id,
            name="Demo Manager",
            email="manager@hopeaid-demo.org",
            hashed_password=hash_password("Manager@1234"),
            role=UserRole.org_manager,
        )
        db.add(org_manager)
        db.flush()   # flush to get org_manager.id

        org_admin = User(
            organization_id=org.id,
            name="Demo Org Admin",
            email="admin@hopeaid-demo.org",
            hashed_password=hash_password("OrgAdmin@1234"),
            role=UserRole.admin,
        )
        volunteer_user = User(
            organization_id=org.id,
            name="Demo Volunteer",
            email="volunteer@hopeaid-demo.org",
            hashed_password=hash_password("Volunteer@1234"),
            role=UserRole.volunteer,
        )
        db.add_all([org_admin, volunteer_user])
        db.flush()

        # ── Households ────────────────────────────────────────────────────────
        hh1 = Household(
            organization_id=org.id,
            household_name="Kumar Family",
            location_name="Relief Camp A, Chennai",
            latitude=13.0827,
            longitude=80.2707,
            contact_name="Ravi Kumar",
            contact_phone="+91-9876543210",
            vulnerability_flags={"has_elderly": True, "has_infant": True},
            created_by_user_id=org_manager.id,
        )
        hh2 = Household(
            organization_id=org.id,
            household_name="Patel Family",
            location_name="Flood Zone B, Surat",
            latitude=21.1702,
            longitude=72.8311,
            contact_phone="+91-9876543211",
            vulnerability_flags={"has_pregnant": True},
            created_by_user_id=org_manager.id,
        )
        db.add_all([hh1, hh2])
        db.flush()   # flush to get hh1.id and hh2.id

        # ── Persons ───────────────────────────────────────────────────────────
        db.add_all([
            Person(household_id=hh1.id, organization_id=org.id, name="Ravi Kumar",  age=45, relation_to_head="head"),
            Person(household_id=hh1.id, organization_id=org.id, name="Priya Kumar", age=38, is_pregnant=True,   relation_to_head="spouse"),
            Person(household_id=hh1.id, organization_id=org.id, name="Arjun Kumar", age=8,  has_children=True,  relation_to_head="child"),
            Person(household_id=hh2.id, organization_id=org.id, name="Meena Patel", age=62, has_disability=True, relation_to_head="head"),
        ])

        # ── Cases ─────────────────────────────────────────────────────────────
        db.add_all([
            Case(
                organization_id=org.id,
                household_id=hh1.id,
                reporter_user_id=org_manager.id,
                case_number="HOPEAID-DEMO-2024-00001",
                title="Urgent food and water needed -- Kumar Family",
                description="Family of 4 stranded after flood. 3 days without clean water or food.",
                category=CaseCategory.food,
                urgency_level=UrgencyLevel.critical,
                risk_score=87.5,
                disaster_type=DisasterType.flood,
                location_name="Relief Camp A, Chennai",
                latitude=13.0827,
                longitude=80.2707,
                number_of_people_affected=4,
                status=CaseStatus.verified,
            ),
            Case(
                organization_id=org.id,
                household_id=hh2.id,
                reporter_user_id=org_manager.id,
                case_number="HOPEAID-DEMO-2024-00002",
                title="Medical attention needed -- pregnant mother",
                description="Pregnant woman in 8th month, no access to medical facility.",
                category=CaseCategory.medical,
                urgency_level=UrgencyLevel.critical,
                risk_score=92.0,
                disaster_type=DisasterType.flood,
                location_name="Flood Zone B, Surat",
                number_of_people_affected=1,
                status=CaseStatus.new,
            ),
            Case(
                organization_id=org.id,
                reporter_user_id=org_manager.id,
                case_number="HOPEAID-DEMO-2024-00003",
                title="Shelter needed -- 20 families displaced",
                description="Cyclone destroyed homes in coastal village. 20 families need temporary shelter.",
                category=CaseCategory.shelter,
                urgency_level=UrgencyLevel.high,
                risk_score=72.3,
                disaster_type=DisasterType.cyclone,
                location_name="Coastal Village, Odisha",
                number_of_people_affected=80,
                status=CaseStatus.new,
            ),
        ])

        # ── Volunteers ────────────────────────────────────────────────────────
        db.add_all([
            Volunteer(
                organization_id=org.id,
                name="Dr. Ananya Sharma",
                phone="+91-9876543220",
                email="ananya@volunteer.org",
                current_location_name="Chennai",
                latitude=13.0827,
                longitude=80.2707,
                skills=["first_aid", "medical", "counseling"],
                languages=["en", "hi", "ta"],
                has_transport=True,
                has_medical_training=True,
                duty_type=DutyType.full_time,
                reliability_score=9.2,
                availability_status=AvailabilityStatus.available,
            ),
            Volunteer(
                organization_id=org.id,
                name="Rajesh Menon",
                phone="+91-9876543221",
                current_location_name="Surat",
                latitude=21.1702,
                longitude=72.8311,
                skills=["logistics", "distribution", "shelter"],
                languages=["en", "gu"],
                has_transport=True,
                duty_type=DutyType.part_time,
                reliability_score=7.8,
                availability_status=AvailabilityStatus.available,
            ),
            Volunteer(
                organization_id=org.id,
                user_id=volunteer_user.id,
                name=volunteer_user.name,
                phone="+91-9876543222",
                email=volunteer_user.email,
                current_location_name="Chennai",
                latitude=13.0827,
                longitude=80.2707,
                skills=["community_outreach", "distribution"],
                languages=["en", "ta"],
                has_transport=False,
                duty_type=DutyType.on_call,
                reliability_score=6.5,
                availability_status=AvailabilityStatus.available,
            ),
        ])

        # ── Inventory ─────────────────────────────────────────────────────────
        db.add_all([
            InventoryItem(
                organization_id=org.id,
                item_name="Rice (25kg bag)",
                item_type=InventoryItemType.food,
                quantity=150,
                unit="bags",
                location_name="Warehouse Chennai",
                minimum_threshold=20,
            ),
            InventoryItem(
                organization_id=org.id,
                item_name="Oral Rehydration Salts",
                item_type=InventoryItemType.medicine,
                quantity=500,
                unit="packets",
                location_name="Medical Store Chennai",
                minimum_threshold=50,
            ),
            InventoryItem(
                organization_id=org.id,
                item_name="Emergency Tarpaulin",
                item_type=InventoryItemType.shelter,
                quantity=75,
                unit="units",
                location_name="Logistics Hub Bhubaneswar",
                minimum_threshold=10,
            ),
        ])

        db.commit()
        print("[OK] Seed data created successfully!")
        print()
        print("Demo credentials:")
        print("  Super Admin : admin@hopeaid.platform   / Admin@1234")
        print("  Org Admin   : admin@hopeaid-demo.org   / OrgAdmin@1234")
        print("  Org Manager : manager@hopeaid-demo.org / Manager@1234")
        print("  Volunteer   : volunteer@hopeaid-demo.org / Volunteer@1234")

    except Exception as e:
        db.rollback()
        print(f"[FAILED] Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
