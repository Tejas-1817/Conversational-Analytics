import sys, os
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from app.db import get_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models import Dashboard, User, SavedInsight, DashboardWidget

engine = get_engine()
Session = sessionmaker(bind=engine)
with Session() as session:
    users = session.scalars(select(User)).all()
    print("Users in DB:")
    for u in users:
        print(f"  User: id={u.id}, email={u.email}, role={u.role}, tenant_id={u.tenant_id}")
    
    dashboards = session.scalars(select(Dashboard)).all()
    print("\nDashboards in DB:")
    for d in dashboards:
        print(f"  Dashboard: id={d.id}, name='{d.name}', user_id={d.user_id}, tenant_id={d.tenant_id}, visibility={d.visibility}, widgets_count={len(d.widgets)}")
        for w in d.widgets:
            print(f"    Widget: id={w.id}, insight_id={w.insight_id}, x={w.x}, y={w.y}, w={w.w}, h={w.h}")
            
    insights = session.scalars(select(SavedInsight)).all()
    print("\nSaved Insights in DB:")
    for i in insights:
        print(f"  Insight: id={i.id}, name='{i.name}', user_id={i.user_id}, tenant_id={i.tenant_id}")
