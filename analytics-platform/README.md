# Conversational Analytics Platform & Code Intelligence

An enterprise-grade, locally-deployable **AI Conversational Analytics & Code Intelligence Platform** that transforms natural language questions into deterministic SQL queries, interactive visualizations, and deep repository architecture insights using **GraphRAG (Neo4j + ChromaDB)**.

Built with a **Local-First**, privacy-focused architecture powered by an AI Semantic Engine, dynamic web interface, automated multi-stage database ingestion, and Git repository AST knowledge graphs.

---

## 🌟 Key Features

### 🧬 GraphRAG Code Intelligence & Repository Knowledge Graph
- **Git Repository Ingestion**: Connect public or private Git repositories (HTTPS/SSH) with automated cloning, branch tracking, and background indexing.
- **AST Code Parsing**: Multi-language AST parser (Python, TypeScript, JavaScript, Go, Rust, Java) that extracts classes, functions, docstrings, parameter signatures, return types, call graphs, and module imports.
- **Neo4j Code Knowledge Graph**: Automatically structures codebases into a high-performance graph schema:
  - **Nodes**: `Repository`, `File`, `Class`, `Function`, `Import`
  - **Relationships**: `DEFINES`, `DEFINES_METHOD`, `CALLS`, `INHERITS`, `IMPORTS`
- **AST-Aware Code Chunking**: Semantically chunks source code at function, class, and module boundaries (never arbitrary line slicing) with intelligent exclusion of translation directories (`docs/zh`, `docs/fr`, etc.) and test fixtures.
- **Hybrid GraphRAG Retrieval Engine**: Combines fuzzy entity extraction and Cypher graph traversal in Neo4j with semantic vector retrieval in ChromaDB.
- **Deep Code Analysis UI**: Expandable **Retrieved Code Snippets** accordion, **Graph Architecture Relationships** tree, and interactive chips for referenced files and AST symbols.

---

### 🤖 Conversational AI & Natural Language Engine (Text-to-SQL)
- **Deterministic 5-Stage Chat Pipeline**: `Parsing Question` ➔ `Entity Resolution` ➔ `Query Planning` ➔ `SQL Compilation & Execution` ➔ `Response Generation`.
- **Intelligent Intent Router**: Classifies incoming queries into `data`, `strategy`, or `hybrid` requests, preventing rigid NLU validation errors.
- **Collapsible ThoughtSpot & Copilot UI**: Modern assistant message layout featuring an Executive Summary, Primary Visualization, Collapsible `▶ Show Generated SQL Query` accordion, and Collapsible `▶ View Raw Data Grid` accordion.
- **Unified Source Switcher**: Seamlessly toggle between connected relational databases, materialized Excel workbooks, and Git code repositories in a single unified chat interface.
- **Persistent Chat History**: User and assistant messages across both SQL analytics and Code Intelligence turns are persisted in PostgreSQL (`conversations` and `conversation_messages` tables), preserving chat threads across page reloads and tab navigation.
- **Full Trace Transparency**: Live step-by-step progress stepper and expandable execution trace detailing latency, schema matches, and generated SQL.

---

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

---

### 📈 Interactive Dashboards & Live Saved Insights (Phase 1 & Phase 2)
- **Multi-Answer Bulk Save from Chat**: Select multiple answers with visualizations or tables via the "In this chat" drawer and add them simultaneously to an existing or new dashboard in a single transaction (`POST /dashboards/bulk-save`), with automatic free position placement and duplicate query detection.
- **Dashboard Tabs**: Split dashboards into named tabs with URL deep-linking (`?tab=<id>`), tab reordering, and cross-tab widget move and clone actions. Single-tab dashboards maintain a clean tabless layout; the first tab addition automatically migrates existing widgets to a "Main" tab.
- **Narrative Text Widgets & Overview Section**: Add Markdown text widgets alongside charts with strict security controls (raw HTML rejected/escaped, links limited to `http`, `https`, and `mailto`). Includes a collapsible executive **Overview Summary** at the top of each dashboard with client-side collapse persistence.
- **Instant Table Filters (`InstantFilterTable`)**: In-place filtering with value checklists, row counts, search, and `(Blank)` support, plus column hiding with 1-column protection and an active filter reset bar. Enforces a 10,000-row execution limit with visible truncation badges.
- **Dual-Axis Combo Charts**: Support for dual-y-axes charts (bar + line, area + bar) driven by versioned layout specs (`schema_version: 1`). Automatically suggested by `ChartRecommender` on disparate metric scales and editable via the widget configuration modal.
- **Permission-Fingerprinted Result Cache & Freshness**: Fast Redis/memory caching scoped to viewer permissions (`dashcache:{tenant}:{user}:{perm_hash}:{insight}:{sql_hash}`). Re-verifies source and table permissions on every fetch. Dashboard header displays **Data as of <time>** computed from the oldest result with cached badges, plus a one-click **Refresh data** action that bypasses the cache.
- **Playground Dashboard Model**: Drag-and-drop responsive grid layouts (`react-grid-layout`), widget renaming, duplication, and instant chart switching (Table, Bar, Line, Pie, Combo).
- **Dynamic Live Query Execution**: Dashboards execute live queries dynamically on load (`POST /dashboards/insights/{id}/run`) using short-lived read-only database connections with statement timeouts.
- **Viewer-Level RBAC & Lock States**: Table permissions checked via `sqlglot` AST parsing. When viewers lack access to underlying tables, widgets gracefully display an explanatory locked placeholder without leaking data.
- **Governance Separation**: Saving personal insights does not auto-promote SQL into `ApprovedSQLExample`, keeping semantic layer administration clean and privileged.
- **Privacy & Visibility Scoping**: Supports `private` dashboards (author and tenant admins only) and `published` dashboards (all tenant members read-only), with strict read-only enforcement for `VIEWER` (Observer) roles.

---
- **On-Device Embedding Engine**: High-performance local sentence-transformers model (`all-MiniLM-L6-v2`) running on-device with zero cloud API latency or costs.
- **Tenant-Isolated Vector Storage**: Persistent ChromaDB vector collections (`ChromaStore`) isolated strictly per `tenant_id` and `repo_id`.
- **Automated Schema Snapshot & Vector Sync**: Ingesting database schemas exports versioned PII-masked DDL snapshots (`v1.json`, `.txt`), generates embeddings, and syncs vector records to ChromaDB.
- **Feedback Learning Loop**: Embeds approved chat feedback examples into vector memory to continuously improve semantic RAG precision.

---

### 📁 Multi-Source Ingestion (Relational DBs & Excel)
- **Relational Connectors**: Ingest schemas and execute queries against PostgreSQL, MySQL, SQLite, and Snowflake.
- **Zero-Config Excel (.xlsx) Ingestion**: Upload multi-sheet `.xlsx` files with automatic sheet preview, column type detection, and read-only SQLite materialization (`?mode=ro`).
- **Heuristic Relationship Discovery**: Automatic cross-table and cross-sheet join path detection based on foreign key naming conventions and column overlap.

---

### 🛡️ Security, Safety & Audit Infrastructure
- **Offline AST SQL Validation (`sqlglot`)**: Pre-execution AST validation against PostgreSQL/MySQL dialects to reject syntax errors and hallucinated columns.
- **Strict Mutation Blacklisting**: Immediate rejection of destructive statements (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`).
- **Encrypted Credentials**: Stored database passwords and Git access tokens are encrypted at rest using Fernet symmetric encryption.
- **Multi-Tenant Isolation**: Strict `tenant_id` scoping across all API endpoints, database queries, Neo4j graphs, and vector collections.
- **Audit Logging & Telemetry**: Microsecond latency tracking, estimated token metrics, and execution history capture.

---

## 🛠️ Architecture & Tech Stack

| Component | Technologies |
| :--- | :--- |
| **Frontend UI** | React 18, TypeScript, Vite, Tailwind CSS / Vanilla HSL Design Tokens, Lucide Icons, Recharts, React Markdown + GFM |
| **Backend API** | Python 3.10+ / 3.13, FastAPI, SQLAlchemy 2.0 ORM, Pydantic v2, Structlog, Sqlglot, Pandas, OpenPyXL |
| **Graph Database** | **Neo4j** (Cypher query language, APOC, AST code graph traversal) |
| **Vector Storage** | **ChromaDB** (Persistent vector collections per tenant/repo) |
| **Embeddings** | **SentenceTransformers** (`all-MiniLM-L6-v2`, 384 dimensions, local execution) |
| **LLM Engine** | **Gemini** (2.5 Flash) / **Ollama** (Local fallback: `llama3`, `deepseek-r1`, `mistral`, `qwen`) |
| **Task Queue** | **RQ (Redis Queue)** + Redis for background schema ingestion & Git repository sync |
| **Metadata DB** | **PostgreSQL** (Conversations, Messages, Data Sources, Users, Tenants, Insights) |

---

## 🚀 Quickstart & Local Deployment Guide

### Prerequisites
- **Node.js**: v18+
- **Python**: 3.10+ / 3.13
- **Redis**: Running on `localhost:6379` (or `6380`)
- **Neo4j**: Running on `bolt://localhost:7687` (Username: `neo4j`, Password: `password`)
- **PostgreSQL**: Running on `localhost:5432`

---

### Step 1: Start Infrastructure (Redis, Neo4j, Postgres)

If using Docker Compose:

```bash
docker compose up -d redis neo4j postgres
```

---

### Step 2: Backend Setup & Seed Data

Navigate to the `services/schema-ingestion` directory:

```bash
cd services/schema-ingestion

# Create and activate virtual environment
python -m venv venv

# Windows (PowerShell):
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
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### Terminal B (Background Ingestion & Git Worker):
```bash
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

| Role | Email | Password | Access Rights |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@company.com` | `admin123` | Full Access (Data Sources, Git Repos, Ingestion, Semantic Layer, Users, Chat, Dashboards) |
| **Analyst** | `analyst@demo.com` | `analyst123` | Analytical Access (Ask AI Chat, Semantic Layer, Dashboards) |

---

## 📖 Usage Walkthrough

### 1. Connecting Data Sources & Code Repositories
1. Log in as `admin@company.com` / `admin123`.
2. Go to **Administration ➔ Data Sources**.
   - **Connect Git Repo**: Click **Connect Repo**, paste a Git URL (e.g. `https://github.com/fastapi/fastapi.git`), and click **Ingest**. The pipeline clones the repo, builds AST nodes in Neo4j, and stores code chunk vectors in ChromaDB.
   - **Connect Database**: Select PostgreSQL, MySQL, or Snowflake, enter credentials, and click **Connect & Ingest**.
   - **Upload Excel**: Select **Excel (.xlsx)**, upload your file, review sheet previews, and ingest.

### 2. Asking AI Questions (Ask AI)
1. Navigate to **Ask AI** (`/chat`).
2. Use the source picker at the top to select either a **Database** or a **Git Repository**:
   - **When querying a Database**: Ask natural language questions like *"Show me top 5 users by total spend"*. Receive generated SQL, interactive charts (KPI, Bar, Line, Data Grid), and CSV export.
   - **When querying a Git Repo**: Ask questions like *"How does request authentication and token verification work?"* or *"Explain the core AST models and call hierarchy"*. Receive detailed architecture explanations, expandable **Neo4j Graph Relationships**, **Retrieved Code Snippets**, and referenced file chips.
3. Chat history is permanently saved in the sidebar and restored on navigation or page refresh.

### 3. Dashboards & Insights
- Save any query result or chart directly into custom dashboards in **Analytics ➔ Dashboards**.

---

## 🔐 Production Security & Best Practices

- **Read-Only Database Connections**: Always connect user databases with `SELECT`-only privileges (`GRANT SELECT ON ALL TABLES IN SCHEMA public TO <user>`).
- **Read-Only Excel SQLite Storage**: Uploaded `.xlsx` files are materialized to disk and mounted with SQLite `?mode=ro`, preventing file tampering.
- **Tenant Scope Enforcement**: Every query, graph relationship, and vector index is isolated by `tenant_id`.
- **Encrypted Secrets**: Database passwords and credentials stored in PostgreSQL are encrypted using Fernet symmetric encryption.
