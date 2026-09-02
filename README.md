# Automatic Index Recommendation using Query Workload Analysis

A system that analyzes SQL query workloads to automatically recommend database indexes, then benchmarks the performance improvement.

## Architecture

```
MySQL Database (Student, Course, Enrollment, Attendance — ~160k rows)
        │
        ▼
Query Workload (workload.csv — 40 SQL queries with frequencies)
        │
        ▼
Workload Analyzer (analyzer/)
   Parses SQL → extracts table, WHERE/JOIN/ORDER BY/GROUP BY columns
   → outputs data/analyzed_workload.json
        │
        ▼
Recommendation Engine (recommendation/)
   Generates candidate indexes → scores via rule-based + ML model
   → outputs data/recommendations.json
        │
        ▼
Benchmarking + Dashboard (benchmark/ + dashboard/)
   Runs queries before/after index creation → measures improvement
   → outputs data/benchmark_results.json → Streamlit dashboard
```

## Prerequisites

- **MySQL 8.0+** installed and running locally
- **Python 3.10+** installed

## Quick Start (Day 1 Setup)

### 1. Clone the repository

```bash
git clone <repo-url>
cd auto-index-recommender
```

### 2. Create the Python virtual environment (on D: drive)

```cmd
python -m venv d:\dbms_cp\venv
d:\dbms_cp\venv\Scripts\activate
set PIP_CACHE_DIR=D:\pip_cache
pip install -r requirements.txt
```

### 3. Create the MySQL user (one-time, as root)

```cmd
mysql -u root -p < database/create_user.sql
```

This creates a dedicated `indexrec_user` with access **only** to the `index_recommender` database. Edit the password in `create_user.sql` before running if you want a different one.

### 4. Set up your credentials

Copy `.env.example` to `.env` and fill in your password:

```cmd
copy .env.example .env
```

Edit `.env`:
```
DB_HOST=localhost
DB_USER=indexrec_user
DB_PASSWORD=<the password you set in create_user.sql>
DB_NAME=index_recommender
```

> ⚠️ **Never commit `.env`** — it's in `.gitignore`.

### 5. Create the database and tables

```cmd
mysql -u root -p < database/schema.sql
```

### 6. Seed the database with synthetic data

```cmd
python database/seed.py
```

This populates:
| Table | Rows |
|-------|------|
| Student | 10,000 |
| Course | 500 |
| Enrollment | 50,000 |
| Attendance | 100,000 |

Uses a fixed random seed (`42`) so every teammate gets equivalent data distributions.

### 7. Generate the query workload

```cmd
python workload/generate_workload.py
```

Produces `workload/workload.csv` — the handoff file for Person 2.

---

## Repository Structure

```
auto-index-recommender/
│
├── database/                # Person 1: schema, user setup, seeder
│   ├── schema.sql
│   ├── create_user.sql
│   └── seed.py
│
├── workload/                # Person 1: query workload
│   ├── queries.sql
│   ├── generate_workload.py
│   └── workload.csv         # ← HANDOFF FILE for Person 2
│
├── analyzer/                # Person 2: SQL parser / analyzer
│   └── analyze.py
│
├── recommendation/          # Person 3: index recommendation engine
│   └── recommend.py
│
├── benchmark/               # Person 4: benchmarking
│   └── benchmark.py
│
├── dashboard/               # Person 4: Streamlit dashboard
│   └── app.py
│
├── data/                    # Shared pipeline output files
│   ├── analyzed_workload.json
│   ├── recommendations.json
│   └── benchmark_results.json
│
├── models/                  # Person 3: trained ML model files
├── tests/                   # Unit tests (each person adds theirs)
├── .env.example             # Credential template
├── .gitignore
├── requirements.txt
└── README.md
```

**Ownership rule:** each person writes only in their own folder and reads from `data/`.

---

## Four-File Protocol

The pipeline is connected through four files with **frozen field names** — changing any field name requires all 4 teammates to agree.

### 1. `workload/workload.csv` (Person 1 → Person 2)

| Column | Type | Description |
|--------|------|-------------|
| `query_id` | int | Unique query identifier (1-based) |
| `query` | string | The full SQL query text |
| `frequency` | int | How many times this query runs per time window |

```csv
query_id,query,frequency
1,"SELECT * FROM Student WHERE department = 'Computer Science';",85
2,"SELECT * FROM Student WHERE city = 'Pune';",67
```

### 2. `data/analyzed_workload.json` (Person 2 → Person 3)

```json
[
  {
    "query_id": 1,
    "table": "Student",
    "where_columns": ["department"],
    "join_columns": [],
    "order_columns": [],
    "group_columns": [],
    "frequency": 85
  }
]
```

### 3. `data/recommendations.json` (Person 3 → Person 4)

```json
[
  {
    "query_id": 1,
    "table": "Student",
    "columns": ["department"],
    "score": 0.91,
    "reason": "High-frequency filtering column"
  }
]
```

### 4. `data/benchmark_results.json` (Person 4 → Dashboard)

```json
[
  {
    "query_id": 1,
    "index": "idx_student_department",
    "before_ms": 412,
    "after_ms": 91,
    "improvement_percent": 77.91,
    "storage_overhead_mb": 2.4
  }
]
```

---

## Database Sharing — Option A (Local Instances)

Each teammate runs their **own local MySQL server**. This is the recommended approach because:

- No shared server to maintain
- No network latency polluting benchmark measurements
- Works offline
- Each person's `indexrec_user` is fully independent

**Setup per teammate:**
1. Run `schema.sql` as root → creates the database
2. Run `create_user.sql` as root → creates the user (choose your own password)
3. Copy `.env.example` → `.env`, fill in your password
4. Run `seed.py` → seeds your local database

Because the random seed is fixed, everyone's data has the **same distribution** (same row counts, same department/city frequencies) even though exact Faker names differ.

The generated `workload.csv` is committed to the repo, so everyone uses **byte-identical** query text and frequencies.

---

## Git Workflow

```
git pull origin main
        ↓
git checkout -b <name>/<short-description>    (e.g., person2/sql-parser)
        ↓
write code inside YOUR OWN folder only
        ↓
test locally
        ↓
git add → git commit -m "clear message"
        ↓
git push origin <branch-name>
        ↓
open Pull Request into main
        ↓
at least one teammate reviews → merge
```

**Nobody pushes directly to `main`.**

---

## Day 1 Checklist

- [x] Repository created with full folder structure
- [x] `.gitignore` includes `.env`, `__pycache__/`, `venv/`
- [x] `.env.example` committed with placeholder values
- [x] `database/schema.sql` creates 4 tables (no extra indexes)
- [x] `database/create_user.sql` creates least-privilege user
- [x] `database/seed.py` seeds ~160k rows with fixed random seed
- [x] `workload/queries.sql` has 40 categorized queries
- [x] `workload/generate_workload.py` produces `workload.csv`
- [x] `workload/workload.csv` committed (byte-identical for all teammates)
- [x] Four-file protocol documented above with exact field names
- [x] README explains full setup for a teammate with zero context

---

## Running the End-to-End Pipeline

### 1. Generate Query Workload (Person 1)
```bash
python workload/generate_workload.py
```

### 2. Analyze Workload Features (Person 2)
```bash
python analyzer/analyze.py
```

### 3. Generate Index Recommendations & Train ML Model (Person 3)
```bash
python models/train_model.py
python recommendation/candidate_generator.py
python recommendation/ml_recommender.py
```

### 4. Benchmark Recommended Indexes & Launch Dashboard (Person 4)
```bash
# Run benchmarking (live with MySQL or simulated fallback)
python benchmark.py

# Launch the interactive Streamlit analytics dashboard
streamlit run app.py
```

### 5. Run Automated Tests
```bash
python -m unittest discover tests
```
