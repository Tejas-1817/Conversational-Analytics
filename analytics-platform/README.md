# Conversational Analytics Platform

An enterprise-grade, locally-deployable AI Conversational Analytics Platform that transforms natural language questions into deterministic SQL queries, interactive visualizations, and actionable business insights.

Built with a **Local-First**, privacy-focused architecture powered by an AI Semantic Engine, dynamic web interface, and multi-stage automated schema ingestion pipeline.

---

## 🌟 Key Features

### 🤖 Conversational AI & Natural Language Engine
- **Deterministic 5-Stage Chat Pipeline**: `Parsing Question` ➔ `Entity Resolution` ➔ `Query Planning` ➔ `SQL Compilation & Execution` ➔ `Response Generation`.
- **Intelligent Intent Router**: Seamlessly classifies chat messages to separate analytics queries, greetings, and help requests, preventing rigid NLU validation errors.
- **Robust Entity Resolver**: Name-based candidate resolution that handles time units (`Month`, `Year`, `Day`) gracefully without LLM hallucination crashes.
- **ThoughtSpot & Power BI Copilot Collapsible Chat UI**: Modern assistant message layout featuring an Executive Summary, Primary Visualization, Collapsible `▶ Show Generated SQL Query` accordion, and Collapsible `▶ View Raw Data Grid` accordion.
- **Zero-State Leakage Architecture**: 100% component state isolation per chat message block, eliminating cross-message cache pollution.
- **Full Trace Transparency**: Live step-by-step progress stepper and expandable execution trace detailing latency, schema matches, and generated SQL.

### 📊 Enterprise 5-Phase Visualization Recommendation Pipeline
- **Phase 1 — Result Inspection (`ResultInspector`)**: Automatic dataset profiling and column type classification into `NUMERIC`, `CATEGORICAL`, `TIME_SERIES`, and `PERCENTAGE`, with query intent analysis for aggregate functions and Top-N rankings.
- **Phase 2 — Visualization Recommendation (`ChartRecommender`)**: Deterministic rules engine with 100% confidence scoring (`1.0`) and title inference:
  - 👥 **KPI Card** (`KPICard`): Single aggregate metric display.
  - 🔢 **Multi KPI Cards** (`MultiKPICards`): Grid of individual metric cards for multi-scalar queries.
  - 🏆 **Entity Detail Card** (`DetailCard`): Key-value attribute cards for single entity lookups.
  - 🥇 **Horizontal Leaderboard** (`Leaderboard`): Horizontal ranked bar chart with rank badges (1, 2, 3...) for Top-N queries.
  - 📊 **Bar Chart** (`BarChart`): Vertical bar chart for categorical aggregations.
  - 📈 **Line Chart** (`LineChart`): Area/Line trend chart with date formatting.
  - 🥧 **Pie Chart** (`PieChart`): Donut/Pie chart with custom slice labels.
  - 📑 **Data Grid** (`DataGrid`): Interactive Table with search filter, column sorting, pagination, and CSV Export.
  - ⚠️ **No Records Found** (`NoData`): Clean alert banner when 0 records match.
- **Phase 3 — Unified Analytics Payload**: Appends `visualization`, `title`, `profile`, `statistics`, and `recommended_visualization` to API response DTOs.
- **Phase 4 — Stateless Frontend Renderer**: Pure React renderers for all 8 visual types.
- **Phase 5 — Validation Suite**: End-to-end verification across multi-schema test suites.

### 🧠 Local Vector Embedding & ChromaDB RAG Pipeline
- **On-Device Embedding Engine**: High-performance local sentence-transformers model (`all-MiniLM-L6-v2`) running without external cloud API calls.
- **Tenant-Isolated Vector Storage**: Persistent ChromaDB vector collections (`ChromaStore`) isolated strictly per `tenant_id` for security and multi-tenancy.
- **Automated Schema Snapshot & Vector Sync**: Triggering schema ingestion exports versioned PII-masked DDL snapshots (`v1.json`, `.txt`), generates `embeddings_<timestamp>.json`, and automatically syncs vector records to persistent ChromaDB storage.
- **Feedback Learning Loop**: Embeds approved chat feedback examples into vector memory to continuously improve semantic RAG precision.

### 🛡️ SQL Safety & Offline AST Syntax Validation
- **Offline AST Parsing (`sqlglot`)**: Pre-execution AST validation using `sqlglot` (PostgreSQL dialect) to catch invalid SQL syntax and dialect errors before DB execution.
- **Strict Keyword Blacklisting**: Immediate rejection of destructive mutation statements (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`).
- **Catalog Existence Validation**: Case-insensitive table validation against the ingested data source catalog to prevent hallucinated table execution.

### 🔬 Ollama Integration Telemetry & Audit Infrastructure
- **Microsecond Latency Breakdown**: Measures timing for prompt prep, HTTP POST, JSON parsing, and regex SQL cleaning (`stage_http_ms`, `stage_clean_ms`, `total_latency_s`).
- **Prompt & Token Statistics**: Logs character counts, schema size, question length, and estimated token usage (`len(prompt) // 4`).
- **Failure Classification Taxonomy**: Maps errors to `LLM_TIMEOUT`, `LLM_CONNECTION_FAILED`, `LLM_EMPTY_RESPONSE`, `LLM_INVALID_RESPONSE`, or `LLM_INVALID_SQL`.
- **Raw Response Audit Logging**: Captures full un-cleaned Ollama text outputs (including reasoning `<thought>` blocks) before cleaning.
### 📁 Excel (.xlsx) Data Source Integration
- **Zero-Config Spreadsheet Ingestion**: Upload multi-sheet `.xlsx` files directly via the UI with automatic sheet preview and column type detection.
- **Isolated SQLite Materialization**: Materializes workbook sheets into a dedicated per-source SQLite database with non-negotiable read-only URI enforcement (`?mode=ro`).
- **Heuristic Relationship Discovery**: Automatic cross-sheet join path detection based on column naming conventions and value overlap.
- **Full Text-to-SQL & Visualization Support**: Spreadsheet data is introspected, profiled, PII-masked, and queryable in Chat SQL identically to relational databases.

---

## 🛠️ Architecture & Tech Stack

- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS / Vanilla HSL Design Tokens, Lucide Icons, Recharts, Responsive Modern Glassmorphism Theme.
- **Backend Service**: Python 3.10+ / 3.13, FastAPI, SQLAlchemy 2.0 ORM, Pydantic v2, Structlog, Pandas, OpenPyXL, Sqlglot.
- **Queue & Async Workers**: RQ (Redis Queue) with background worker process for schema ingestion and chat pipeline execution.
- **Storage & Metadata**: PostgreSQL (production) / SQLite (local fallback), Redis, Per-Source SQLite for Materialized Excel Workbooks.

---

## 🚀 Quickstart & Local Deployment Guide

### Prerequisites
- **Node.js**: v18+
- **Python**: 3.10+
- **Redis**: Running on `localhost:6380` (or `localhost:6379`)
- **Ollama** *(Optional for local AI)*: Serving local models on `localhost:11434`

### Configuration Variables
Key environment variables for Excel ingestion (in `services/schema-ingestion/.env` or system environment):
- `EXCEL_UPLOAD_DIR`: Directory for storing original uploaded `.xlsx` files (default: `./storage/excel_uploads`).
- `EXCEL_SQLITE_DIR`: Directory for materialized read-only SQLite database files (default: `./storage/excel_dbs`).
- `EXCEL_MAX_UPLOAD_MB`: Maximum allowable upload size in MB (default: `50`).

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
2. **Data Sources**: Go to **Administration ➔ Data Sources**.
   - **Relational Databases**: Select PostgreSQL/MySQL/Snowflake, configure host/port/credentials, and trigger ingestion.
   - **Excel Files**: Select **Excel (.xlsx)**, upload your workbook, review sheet previews and table names, and click **Connect & Ingest**.
3. **Jobs Progress**: Watch live multi-stage job progress in **Administration ➔ Jobs**.
4. **Semantic Layer**: Explore auto-generated metrics, dimensions, and business glossary terms.
5. **Ask AI Chat**: Ask plain English questions like *"Show me total revenue by month"*. View the generated query, execution trace, and auto-recommended line chart.
6. **Dashboards**: View and customize widget layouts on the Executive Summary dashboard.

---

## 🔐 Production Security & Best Practices

- **Read-Only Database Users**: For target database ingestion, always configure a database user with `SELECT` privileges only (`GRANT SELECT ON ALL TABLES IN SCHEMA public TO <user>`).
- **Read-Only SQLite Files**: Excel data sources are mounted via SQLite URI read-only mode (`?mode=ro`), physically prohibiting `INSERT`/`UPDATE`/`DELETE`/`DROP` mutations.
- **Encrypted Credentials**: Stored secrets are encrypted at rest using Fernet symmetric encryption.
- **Tenant Scope Enforcement**: All API routes and database queries enforce `tenant_id` boundaries.
