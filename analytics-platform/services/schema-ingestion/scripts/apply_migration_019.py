import os
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from app.config import get_settings
from sqlalchemy import create_engine, text

def apply_migration():
    settings = get_settings()
    db_url = settings.metadata_db_url
    print(f"Connecting to metadata database at: {db_url}")

    if db_url.startswith("postgresql://"):
        try:
            import psycopg2
        except ImportError:
            db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

    engine = create_engine(db_url, isolation_level="AUTOCOMMIT")

    migration_file = project_root / "migrations" / "019_dashboards_access_and_scoping.sql"
    print(f"Reading migration file: {migration_file}")
    with open(migration_file, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Split into separate statements or execute block
    print("Executing migration 019...")
    with engine.connect() as conn:
        # Execute line by line / statement by statement to provide clear logs
        statements = [
            # 1. saved_insights columns
            """ALTER TABLE saved_insights
                ADD COLUMN IF NOT EXISTS source_id UUID REFERENCES data_sources(id) ON DELETE CASCADE,
                ADD COLUMN IF NOT EXISTS domain_id UUID REFERENCES domains(id) ON DELETE SET NULL,
                ADD COLUMN IF NOT EXISTS conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
                ADD COLUMN IF NOT EXISTS message_id UUID REFERENCES conversation_messages(id) ON DELETE SET NULL,
                ADD COLUMN IF NOT EXISTS chart_type TEXT,
                ADD COLUMN IF NOT EXISTS last_run_at TIMESTAMP WITH TIME ZONE;""",
            
            # 1b. saved_insights constraints & indexes
            "ALTER TABLE saved_insights DROP CONSTRAINT IF EXISTS saved_insights_tenant_id_name_key;",
            "CREATE INDEX IF NOT EXISTS idx_saved_insights_tenant_user ON saved_insights (tenant_id, user_id);",
            "CREATE INDEX IF NOT EXISTS idx_saved_insights_source ON saved_insights (source_id);",
            
            # 2. dashboards visibility
            """ALTER TABLE dashboards
                ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'published' CHECK (visibility IN ('private', 'published'));""",
            "UPDATE dashboards SET visibility = 'published' WHERE visibility IS NULL;",
            "ALTER TABLE dashboards DROP CONSTRAINT IF EXISTS dashboards_tenant_id_name_key;",
            # Safe constraint add: only add if not already present
            """DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'dashboards_tenant_user_name_key'
                ) THEN
                    ALTER TABLE dashboards ADD CONSTRAINT dashboards_tenant_user_name_key UNIQUE (tenant_id, user_id, name);
                END IF;
            END $$;""",
            "CREATE INDEX IF NOT EXISTS idx_dashboards_tenant_user ON dashboards (tenant_id, user_id);",
            
            # 3. dashboard_widgets overrides & layouts
            """ALTER TABLE dashboard_widgets
                ADD COLUMN IF NOT EXISTS title_override TEXT,
                ADD COLUMN IF NOT EXISTS chart_type_override TEXT,
                ADD COLUMN IF NOT EXISTS settings JSONB NOT NULL DEFAULT '{}'::jsonb,
                ADD COLUMN IF NOT EXISTS layouts JSONB NOT NULL DEFAULT '{}'::jsonb;""",
            """UPDATE dashboard_widgets
                SET layouts = jsonb_build_object('lg', jsonb_build_object('x', x, 'y', y, 'w', w, 'h', h))
                WHERE layouts = '{}'::jsonb OR layouts IS NULL;""",
            "CREATE INDEX IF NOT EXISTS idx_dashboard_widgets_dashboard ON dashboard_widgets (dashboard_id);",
            "CREATE INDEX IF NOT EXISTS idx_dashboard_widgets_insight ON dashboard_widgets (insight_id);",
        ]

        for stmt in statements:
            try:
                conn.execute(text(stmt))
                print(f"  [OK] Executed:\n{stmt[:60].strip()}...")
            except Exception as e:
                print(f"  [ERROR] On statement:\n{stmt}\n  Error: {e}")
                raise

    print("\nVerifying updated schema...")
    with engine.connect() as conn:
        cols = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='saved_insights' ORDER BY ordinal_position;"))
        print("Columns in saved_insights:")
        for col_name, data_type in cols.fetchall():
            print(f"  - {col_name} ({data_type})")

        dash_cols = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='dashboards' ORDER BY ordinal_position;"))
        print("\nColumns in dashboards:")
        for col_name, data_type in dash_cols.fetchall():
            print(f"  - {col_name} ({data_type})")

        widget_cols = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='dashboard_widgets' ORDER BY ordinal_position;"))
        print("\nColumns in dashboard_widgets:")
        for col_name, data_type in widget_cols.fetchall():
            print(f"  - {col_name} ({data_type})")

    print("\nMigration 019 applied and verified successfully!")

if __name__ == "__main__":
    apply_migration()
