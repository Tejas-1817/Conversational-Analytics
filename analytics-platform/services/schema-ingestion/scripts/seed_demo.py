import os
import sys
import uuid
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db import session_scope, get_engine
from app.models import (
    Tenant, User, DataSource, TableMeta, ColumnMeta,
    SemanticMetric, SemanticDimension, BusinessGlossary,
    SavedInsight, Dashboard, DashboardWidget,
    BenchmarkCollection, EvaluationDataset, SemanticSynonym
)
from app.security.auth import get_password_hash
from app.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migrations():
    logger.info("Running alembic migrations...")
    os.system("alembic upgrade head")

def clear_database(db: Session):
    logger.info("Clearing existing data (for demo purposes)...")
    # Truncate tables to avoid constraint violations while keeping structure
    tables = [
        "dashboard_widgets", "dashboards", "saved_insights",
        "evaluation_results", "evaluation_datasets", "evaluation_runs", "benchmark_collections",
        "semantic_synonyms", "business_glossary", "semantic_dimensions", "semantic_metrics",
        "columns_meta", "tables_meta", "data_sources",
        "users", "tenants"
    ]
    for table in tables:
        db.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
    db.commit()

def seed():
    settings = get_settings()
    
    with session_scope() as db:
        clear_database(db)

        # 1. Tenant
        logger.info("Seeding Tenant...")
        demo_tenant_id = settings.default_tenant_id
        tenant = Tenant(
            id=demo_tenant_id,
            name="Demo Corporation",
            slug="demo-corp",
            display_name="Demo Corporation",
            plan="enterprise",
            is_active=True
        )
        db.add(tenant)
        db.commit()

        # 2. Users
        logger.info("Seeding Users...")
        admin_email = settings.admin_bootstrap_email or "admin@company.com"
        admin_password = settings.admin_bootstrap_password or "admin123"
        
        admin_user = User(
            tenant_id=demo_tenant_id,
            email=admin_email,
            password_hash=get_password_hash(admin_password),
            role="ADMIN"
        )
        db.add(admin_user)
        
        analyst_user = User(
            tenant_id=demo_tenant_id,
            email="analyst@demo.com",
            password_hash=get_password_hash("analyst123"),
            role="ANALYST"
        )
        db.add(analyst_user)
        db.commit()

        # 3. Data Source & Schema
        logger.info("Seeding Data Source & Schema...")
        ds = DataSource(
            tenant_id=demo_tenant_id,
            name="Production Postgres",
            type="postgres",
            database_name="prod_db",
            username="user",
            credentials_encrypted=b"dummy",
            created_by=admin_user.email,
            updated_by=admin_user.email
        )
        db.add(ds)
        db.commit()

        table = TableMeta(
            source_id=ds.id,
            schema_name="public",
            table_name="sales",
            business_name="Retail Sales",
            description="Fact table for all retail sales",
            updated_by=admin_user.email,
            status="approved",  # Phase 2: seed approved so embedding backfill has data
        )
        db.add(table)
        db.commit()

        col_rev = ColumnMeta(table_id=table.id, column_name="revenue", data_type="numeric", description="Total revenue", updated_by=admin_user.email, status="approved")
        col_reg = ColumnMeta(table_id=table.id, column_name="region", data_type="varchar", description="Sales region", updated_by=admin_user.email, status="approved")
        col_date = ColumnMeta(table_id=table.id, column_name="sale_date", data_type="timestamp", description="Date of sale", updated_by=admin_user.email, status="approved")
        db.add_all([col_rev, col_reg, col_date])
        db.commit()

        # 4. Semantic Layer
        logger.info("Seeding Semantic Layer...")
        metric = SemanticMetric(
            tenant_id=demo_tenant_id,
            name="Total Revenue",
            business_name="Total Revenue",
            description="Sum of revenue from all sales",
            source_table_id=table.id,
            source_column_id=col_rev.id,
            expression="SUM(revenue)",
            created_by=admin_user.email,
            updated_by=admin_user.email,
            status="approved",  # Phase 2: pre-approved for embedding
        )
        db.add(metric)
        
        dim_region = SemanticDimension(
            tenant_id=demo_tenant_id,
            business_name="Region",
            description="Geographic region",
            source_table_id=table.id,
            source_column_id=col_reg.id,
            data_type="varchar",
            created_by=admin_user.email,
            updated_by=admin_user.email,
            status="approved",  # Phase 2: pre-approved for embedding
        )
        db.add(dim_region)
        
        dim_date = SemanticDimension(
            tenant_id=demo_tenant_id,
            business_name="Sale Date",
            description="Date when the sale occurred",
            source_table_id=table.id,
            source_column_id=col_date.id,
            data_type="timestamp",
            is_time_dimension=True,
            time_granularity="DAY",
            created_by=admin_user.email,
            updated_by=admin_user.email,
            status="approved",  # Phase 2: pre-approved for embedding
        )
        db.add(dim_date)
        db.commit()

        glossary = BusinessGlossary(
            tenant_id=demo_tenant_id,
            term="Revenue",
            business_definition="The total amount of income generated by the sale of goods or services.",
            created_by=admin_user.email,
            updated_by=admin_user.email,
            status="approved",  # Phase 2: pre-approved for embedding
        )
        db.add(glossary)
        db.commit()

        syn1 = SemanticSynonym(tenant_id=demo_tenant_id, entity_type="GLOSSARY", entity_id=glossary.id, synonym="sales")
        syn2 = SemanticSynonym(tenant_id=demo_tenant_id, entity_type="GLOSSARY", entity_id=glossary.id, synonym="income")
        syn3 = SemanticSynonym(tenant_id=demo_tenant_id, entity_type="GLOSSARY", entity_id=glossary.id, synonym="earnings")
        syn4 = SemanticSynonym(tenant_id=demo_tenant_id, entity_type="GLOSSARY", entity_id=glossary.id, synonym="total earnings")
        syn5 = SemanticSynonym(tenant_id=demo_tenant_id, entity_type="GLOSSARY", entity_id=glossary.id, synonym="earn")
        syn6 = SemanticSynonym(tenant_id=demo_tenant_id, entity_type="GLOSSARY", entity_id=glossary.id, synonym="total income")
        db.add_all([syn1, syn2, syn3, syn4, syn5, syn6])
        db.commit()

        # 5. Saved Insights & Dashboards
        logger.info("Seeding Insights & Dashboards...")
        insight1 = SavedInsight(
            tenant_id=demo_tenant_id,
            user_id=admin_user.id,
            name="Revenue by Region",
            description="Total revenue split by geographic region",
            query="Show me total revenue by region",
            chart_config={
                "chartType": "bar",
                "data": [
                    {"region": "North America", "revenue": 150000},
                    {"region": "EMEA", "revenue": 120000},
                    {"region": "APAC", "revenue": 95000}
                ]
            }
        )
        insight2 = SavedInsight(
            tenant_id=demo_tenant_id,
            user_id=admin_user.id,
            name="Monthly Revenue Trend",
            description="Total revenue trend over the last 6 months",
            query="What is the revenue trend over time?",
            chart_config={
                "chartType": "line",
                "data": [
                    {"month": "Jan", "revenue": 45000},
                    {"month": "Feb", "revenue": 52000},
                    {"month": "Mar", "revenue": 48000},
                    {"month": "Apr", "revenue": 61000},
                    {"month": "May", "revenue": 59000},
                    {"month": "Jun", "revenue": 68000}
                ]
            }
        )
        db.add_all([insight1, insight2])
        db.commit()

        dashboard = Dashboard(
            tenant_id=demo_tenant_id,
            user_id=admin_user.id,
            name="Executive Summary",
            description="High level overview of business performance"
        )
        db.add(dashboard)
        db.commit()

        widget1 = DashboardWidget(
            dashboard_id=dashboard.id,
            insight_id=insight1.id,
            x=0, y=0, w=6, h=4
        )
        widget2 = DashboardWidget(
            dashboard_id=dashboard.id,
            insight_id=insight2.id,
            x=6, y=0, w=6, h=4
        )
        db.add_all([widget1, widget2])
        db.commit()

        # 6. Benchmarks
        logger.info("Seeding Evaluation Benchmarks...")
        collection = BenchmarkCollection(
            tenant_id=demo_tenant_id,
            name="Core KPI Suite",
            description="Tests basic conversational flows",
            domain="Sales",
            created_by=admin_user.email
        )
        db.add(collection)
        db.commit()

        ds1 = EvaluationDataset(
            collection_id=collection.id,
            question="What is the total revenue?",
            expected_intent={"intent": "aggregate", "metric": "Total Revenue", "dimensions": []},
            expected_plan={"metric_id": str(metric.id), "dimension_ids": []},
            expected_sql="SELECT SUM(revenue) FROM sales",
            expected_chart="kpi_card",
            expected_result={"columns": ["revenue"], "rows": [{"revenue": 500000}]}
        )
        db.add(ds1)
        db.commit()

        logger.info("Demo data seeding completed successfully!")

if __name__ == "__main__":
    run_migrations()
    seed()
