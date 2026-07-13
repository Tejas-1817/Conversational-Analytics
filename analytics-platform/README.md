# Conversational Analytics Platform

An enterprise-grade, locally-deployable Conversational Analytics Platform. 

## Features
- **Conversational Analytics**: Ask questions in plain English and get SQL queries, answers, and auto-generated charts.
- **Semantic Layer**: Define Metrics, Dimensions, Joins, and Business Glossary to govern AI query generation.
- **Dynamic Dashboards**: Create, drag, resize, and export fully customizable widgets.
- **AI Evaluation Framework**: Automated benchmarking and reliability testing for the LLM-to-SQL engine.
- **Enterprise Multi-Tenancy**: Built-in tenant isolation, RBAC, and Row-Level Security capabilities.
- **Local First**: Fully functional without requiring cloud infrastructure or distributed systems.

## Prerequisites
- Node.js (v18+)
- Python (3.10+)
- Local PostgreSQL (Optional, defaults to SQLite if not provided)

## One-Command Startup (Local Deployment)

### 1. Backend Setup
Navigate to the `services/schema-ingestion` directory and set up the Python backend:

```bash
cd services/schema-ingestion
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
# source venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run Database Migrations and Seed Demo Data
python scripts/seed_demo.py

# Start Backend Server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend Setup
In a new terminal window, navigate to the `apps/web` directory:

```bash
cd apps/web
npm install

# Start Frontend Development Server
npm run dev
```

The application will be available at `http://localhost:5173`.

## Demo User Guide

The database seeding script (`scripts/seed_demo.py`) creates an initial tenant and two demo users for you to explore the platform.

### Demo Credentials

**Admin Account** (Has access to all Admin and Business features)
- **Email**: `admin@company.com`
- **Password**: `admin123`

**Analyst Account** (Has access only to the Chat and Dashboards)
- **Email**: `analyst@demo.com`
- **Password**: `analyst123`

### Exploring the Platform

1. **Log in**: Use `admin@company.com`.
2. **Semantic Layer**: Navigate to the Semantic Layer from the sidebar. You'll see pre-seeded metrics ("Total Revenue") and dimensions ("Region", "Sale Date"). You can create new metrics and test the formula validation.
3. **Dashboards**: Click on Dashboards. You'll see an "Executive Summary" dashboard with pre-populated widgets. Click "Edit Layout" to drag and resize them. Click the vertical dots on a widget to export data to CSV or JSON.
4. **Chat**: Ask a question like *"Show me revenue by region"* to see the AI generate a response, display a chart, and present the execution trace. You can also rename or search past conversations in the left sidebar.

## Production Security Notes
Although designed to run locally, the backend implements robust security middleware including:
- OWASP-recommended HTTP security headers
- Payload size limiting
- Configurable Rate Limiting
- Tenant-scoped database queries

*Note: Docker and Docker Compose files are provided for convenience but are not required for local execution.*
