# Conversational Analytics Platform

An enterprise-grade, locally-deployable AI Conversational Analytics Platform that transforms natural language questions into deterministic SQL queries, interactive visualizations, and actionable business insights.

Built with a **Local-First**, privacy-focused architecture powered by an AI Semantic Engine, dynamic web interface, and multi-stage automated schema ingestion pipeline.

---

## 🌟 Key Features

### 🤖 Conversational AI & Natural Language Engine
- **Deterministic 5-Stage Chat Pipeline**: `Parsing Question` ➔ `Entity Resolution` ➔ `Query Planning` ➔ `SQL Compilation & Execution` ➔ `Response Generation`.
- **Intelligent Intent Router**: Seamlessly classifies chat messages to separate analytics queries, greetings, and help requests, preventing rigid NLU validation errors.
- **Robust Entity Resolver**: Name-based candidate resolution that handles time units (`Month`, `Year`, `Day`) gracefully without LLM hallucination crashes.
- **Chart Recommendation Engine**: Automatically selects the optimal visualization (Line Chart, Bar Chart, Pie Chart, Stat Card) based on query semantics.
- **Full Trace Transparency**: Live step-by-step progress stepper and expandable execution trace detailing latency, schema matches, and generated SQL.

### 🏗️ Automated Schema Ingestion & AI Semantic Layer
- **Multi-Stage Ingestion Pipeline**:
  1. **Introspection**: Reflects database tables, columns, data types, and primary/foreign keys.
  2. **Data Profiling**: Computes column stats, null rates, and sample value distributions.
  3. **Relationship Detection**: Discovers hidden foreign key relationships via value-overlap testing and AI heuristics.
  4. **Role Classification**: Automatically labels columns as dimensions, measures, keys, or attributes.
  5. **Semantic Generation**: Generates business metrics, dimensions, synonyms, and documentation with graph validation and atomic version promotion.
- **Semantic Layer Management**: Full CRUD interface for Metrics, Dimensions, Joins, and Business Glossary with automated formula parsing and validation.

### 📊 Dynamic Dashboards & Visualization
- **Drag & Drop Layout**: Customizable, resizable widget grid.
- **Data Exporting**: One-click data export to CSV and JSON formats.
- **Global Filters**: Date ranges and dimension slicers that filter dashboard widgets dynamically.

### 🔒 Enterprise Governance & Security
- **Strict Multi-Tenancy**: Built-in tenant isolation with tenant-scoped sessions and Row-Level Security (RLS) enforcement.
- **Role-Based Access Control (RBAC)**: Fine-grained permissions for `ADMIN`, `ANALYST`, and `VIEWER` roles.
- **Encrypted Credentials**: Target database credentials encrypted at rest using Fernet symmetric cryptography.
- **OWASP Security Middleware**: HTTP security headers, payload size limits, and rate limiting.

### 🔌 Pluggable LLM Provider Registry
- **Local-First AI**: Native support for local LLM inference via **Ollama** (`mistral`, `llama3`, `qwen`).
- **Cloud Provider Extensibility**: Easily switch or fallback to Google Gemini, HuggingFace Hub, or mock providers.

---

## 🛠️ Architecture & Tech Stack

- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS / Vanilla HSL Design Tokens, Lucide Icons, Recharts, Responsive Modern Glassmorphism Theme.
- **Backend Service**: Python 3.10+ / 3.13, FastAPI, SQLAlchemy 2.0 ORM, Pydantic v2, Structlog.
- **Queue & Async Workers**: RQ (Redis Queue) with background worker process for schema ingestion and chat pipeline execution.
- **Storage & Metadata**: PostgreSQL (production) / SQLite (local fallback), Redis.

---

## 🚀 Quickstart & Local Deployment Guide

### Prerequisites
- **Node.js**: v18+
- **Python**: 3.10+
- **Redis**: Running on `localhost:6380` (or `localhost:6379`)
- **Ollama** *(Optional for local AI)*: Serving local models on `localhost:11434`

---

### Step 1: Start Infrastructure (Redis & Demo DB)

If using Docker, spin up Redis and the Demo Postgres database using Docker Compose:

```bash
docker compose up -d redis demo-source-db
```

---

### Step 2: Backend Setup & Seed Data

Navigate to the `services/schema-ingestion` directory:

```bash
cd services/schema-ingestion

# Create and activate virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac/Linux:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run migrations & seed demo tenant/user data
python scripts/seed_demo.py
```

Now start **two** background services:

#### Terminal A (API Server):
```bash
# Ensure venv is activated
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### Terminal B (Background Ingestion & Chat Worker):
```bash
# Ensure venv is activated
python -m app.worker
```

---

### Step 3: Frontend Setup

In a new terminal window, navigate to `apps/web`:

```bash
cd apps/web
npm install

# Start Vite Development Server
npm run dev
```

Open your browser and navigate to **`http://localhost:5173`**.

---

## 👤 Demo User Accounts

The seeding script generates pre-configured credentials for quick testing:

| Role | Email | Password | Access Rights |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@company.com` | `admin123` | Full Access (Data Sources, Ingestion, Semantic Layer, Users, Chat, Dashboards) |
| **Analyst** | `analyst@demo.com` | `analyst123` | Analytical Access (Semantic Layer, Chat, Dashboards) |

---

## 📖 Usage Walkthrough

1. **Log In**: Log in as `admin@company.com` / `admin123`.
2. **Data Sources**: Go to **Administration ➔ Data Sources**. Set up or test database connections (`127.0.0.1:5432` for local pgAdmin DB or `127.0.0.1:5443` for demo container). Click **Trigger Ingestion** to run the 5-stage pipeline.
3. **Jobs Progress**: Watch live multi-stage job progress in **Administration ➔ Jobs**.
4. **Semantic Layer**: Explore auto-generated metrics (e.g., *Revenue*), dimensions (e.g., *Region*, *Date*), and business glossary terms.
5. **Ask AI Chat**: Ask plain English questions like *"Show me total revenue by month"*. View the generated query, execution trace, and auto-recommended line chart.
6. **Dashboards**: View and customize widget layouts on the Executive Summary dashboard.

---

## 🔐 Production Security & Best Practices

- **Read-Only Database Users**: For target database ingestion, always configure a database user with `SELECT` privileges only (`GRANT SELECT ON ALL TABLES IN SCHEMA public TO <user>`).
- **Encrypted Credentials**: Stored secrets are encrypted at rest using Fernet symmetric encryption.
- **Tenant Scope Enforcement**: All API routes and database queries enforce `tenant_id` boundaries.
