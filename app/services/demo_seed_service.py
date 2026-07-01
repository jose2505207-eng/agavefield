"""Seed a read-only DEMO organization with the five role profiles.

Idempotent and best-effort (callers must not let a failure crash startup). The
demo accounts are ``is_demo=True``, so every write they attempt is refused by the
demo read-only guard — the profile switcher changes *visibility*, never the
ability to mutate data.

Honest scope: this seeds the demo ORG, the five demo login accounts, and their
memberships (role + permissions + data scope) so ``/api/org/context`` returns a
genuinely different resolved profile per account, and endpoint permission guards
differ for real. It does NOT seed demo work-order rows into the shared DB — the
five dashboards render curated, clearly-labelled demo datasets on the frontend.
Server-side scope enforcement is real and is covered by the pytest suite.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.operations import AppUser
from app.services import auth_service, rbac_service

log = logging.getLogger("agave.demo")

DEMO_ORG_SLUG = "demo-hacienda-verde"
DEMO_ORG_NAME = "Hacienda Verde (Demo)"

# Demo assignee emails used by the worker self-scope + supervisor team-scope.
JUAN_EMAIL = "juan.martinez@demo.agavefield.mx"
PEDRO_EMAIL = "pedro.sanchez@demo.agavefield.mx"

# username -> (full_name, org_role, web_role_label, scope overrides)
_PROFILES = [
    ("DEMO_WORKER", "Juan Martinez", "worker", "agronomist",
     {"scope_assignee_emails": [JUAN_EMAIL]}),
    ("DEMO_SUPERVISOR", "Ana Lopez", "supervisor", "agronomist",
     {"scope_ranch_ids": [1], "scope_lot_ids": [1, 2, 3],
      "scope_assignee_emails": [JUAN_EMAIL, PEDRO_EMAIL]}),
    ("DEMO_ENGINEER", "Ing. Camila Torres", "engineer", "agronomist", {}),
    ("DEMO_ADMIN", "Jose Admin", "admin", "admin", {}),
    ("DEMO_AUDITOR", "Compliance Viewer", "auditor", "reviewer", {}),
]


def _ensure_demo_user(
    db: Session, username: str, full_name: str, web_role: str, organization_id: int
) -> AppUser:
    user = auth_service.get_user(db, username)
    if user is None:
        user = AppUser(
            username=username,
            # Demo creds are public by design (username == password). All writes
            # are blocked server-side regardless.
            password_hash=auth_service.hash_password(username),
            full_name=full_name,
            role=web_role,
            is_demo=True,
            organization_id=organization_id,
        )
        db.add(user)
        db.flush()
        log.info("Seeded demo account '%s' (%s)", username, full_name)
    elif user.organization_id is None:
        user.organization_id = organization_id
        db.flush()
    return user


def seed_demo_org(db: Session) -> None:
    """Create the demo org, five role accounts + memberships. Idempotent."""
    org = rbac_service.get_or_create_organization(
        db, name=DEMO_ORG_NAME, slug=DEMO_ORG_SLUG,
        description="Read-only demo tenant showcasing the five role profiles.",
    )

    for username, full_name, org_role, web_role, scope in _PROFILES:
        user = _ensure_demo_user(db, username, full_name, web_role, org.id)
        existing = rbac_service.get_membership(db, user.id, organization_id=org.id)
        if existing is None:
            rbac_service.create_member(
                db,
                organization_id=org.id,
                app_user_id=user.id,
                role=org_role,
                data_scope=None,  # use the role template default
                scope_ranch_ids=scope.get("scope_ranch_ids"),
                scope_lot_ids=scope.get("scope_lot_ids"),
                scope_assignee_emails=scope.get("scope_assignee_emails"),
                actor="seed",
            )

    # The original DEMO/DEMO account stays valid and maps to the admin profile so
    # signing in with DEMO/DEMO lands on the Organization Control Center.
    demo = auth_service.get_user(db, settings.demo_username)
    if demo is not None:
        if demo.organization_id is None:
            demo.organization_id = org.id
            db.flush()
        if rbac_service.get_membership(db, demo.id, organization_id=org.id) is None:
            rbac_service.create_member(
                db, organization_id=org.id, app_user_id=demo.id,
                role="admin", actor="seed",
            )

    db.commit()
