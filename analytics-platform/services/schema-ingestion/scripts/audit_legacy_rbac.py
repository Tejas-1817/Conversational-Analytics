"""Pre-migration audit script for Enterprise RBAC and Table Permissions.

Audits legacy records to identify:
1. Existing enterprises (tenants)
2. User role distribution and unassigned/orphaned users
3. Data sources and enterprise assignments
4. Domains and creator ownership matching
5. Existing access grants
"""

from __future__ import annotations

import sys
from pathlib import Path
from sqlalchemy import text

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.db import get_engine  # noqa: E402


def run_audit() -> dict:
    engine = get_engine()
    results = {}

    with engine.connect() as conn:
        # 1. Tenants / Enterprises
        try:
            tenants = conn.execute(text("SELECT id, name, slug, is_active FROM tenants")).fetchall()
            results["enterprises"] = [
                {"id": str(t[0]), "name": t[1], "slug": t[2], "is_active": t[3]}
                for t in tenants
            ]
        except Exception as e:
            results["enterprises"] = f"Error querying tenants: {e}"

        # 2. Users & Role distribution
        try:
            users_count = conn.execute(text("SELECT count(*) FROM users")).scalar()
            roles_dist = conn.execute(text("SELECT role::text, count(*) FROM users GROUP BY role")).fetchall()
            orphaned_users = conn.execute(text("""
                SELECT count(*) FROM users 
                WHERE tenant_id IS NULL OR tenant_id NOT IN (SELECT id FROM tenants)
            """)).scalar()

            results["users"] = {
                "total": users_count,
                "roles_distribution": {r[0]: r[1] for r in roles_dist},
                "orphaned_users_count": orphaned_users,
            }
        except Exception as e:
            results["users"] = f"Error querying users: {e}"

        # 3. Data Sources
        try:
            sources_count = conn.execute(text("SELECT count(*) FROM data_sources")).scalar()
            orphaned_sources = conn.execute(text("""
                SELECT count(*) FROM data_sources 
                WHERE tenant_id IS NULL OR tenant_id NOT IN (SELECT id FROM tenants)
            """)).scalar()

            results["data_sources"] = {
                "total": sources_count,
                "orphaned_sources_count": orphaned_sources,
            }
        except Exception as e:
            results["data_sources"] = f"Error querying data_sources: {e}"

        # 4. Domains & Ownership matching
        try:
            domains_count = conn.execute(text("SELECT count(*) FROM domains")).scalar()
            matched_domains = conn.execute(text("""
                SELECT count(*) FROM domains d
                JOIN users u ON d.created_by = u.email AND d.tenant_id = u.tenant_id
            """)).scalar()

            results["domains"] = {
                "total": domains_count,
                "matched_to_existing_user": matched_domains,
                "ambiguous_or_system_created": (domains_count or 0) - (matched_domains or 0),
            }
        except Exception as e:
            results["domains"] = f"Error querying domains: {e}"

        # 5. Access control tables
        try:
            dsa_count = conn.execute(text("SELECT count(*) FROM user_data_source_access")).scalar()
            results["user_data_source_access"] = {"total_grants": dsa_count}
        except Exception:
            results["user_data_source_access"] = {"exists": False}

        try:
            uta_count = conn.execute(text("SELECT count(*) FROM user_table_access")).scalar()
            results["user_table_access"] = {"total_grants": uta_count}
        except Exception:
            results["user_table_access"] = {"exists": False}

    return results


if __name__ == "__main__":
    import json
    report = run_audit()
    print("\n=== PRE-MIGRATION ENTERPRISE RBAC AUDIT REPORT ===")
    print(json.dumps(report, indent=2))
