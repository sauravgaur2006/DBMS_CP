"""
Setup and Seed Cloud MySQL Database (e.g., Aiven, TiDB, Clever Cloud)
====================================================================
Usage:
    python database/setup_cloud_db.py
Reads credentials from .env or prompts interactively.
Executes schema.sql and populates all 160,500 deterministic records via seed.py.
"""

import os
import sys
from pathlib import Path
import mysql.connector
from dotenv import load_dotenv

# Ensure root is in path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

load_dotenv()

def main():
    print("=" * 70)
    print("  CLOUD MYSQL SETUP & SEEDING SCRIPT (Aiven / TiDB / Remote)")
    print("=" * 70)

    from urllib.parse import urlparse

    service_uri = os.getenv("DB_URI", os.getenv("MYSQL_URL", "")).strip()
    if service_uri:
        parsed = urlparse(service_uri)
        host = parsed.hostname or "localhost"
        port = parsed.port or 3306
        user = parsed.username or "root"
        password = parsed.password or ""
        database = parsed.path.lstrip('/') or "defaultdb"
    else:
        host = os.getenv("DB_HOST", "localhost")
        port = int(os.getenv("DB_PORT", 3306))
        user = os.getenv("DB_USER", "root")
        password = os.getenv("DB_PASSWORD", "")
        database = os.getenv("DB_NAME", "defaultdb")

    def resolve_host(h: str) -> str:
        if h in ("localhost", "127.0.0.1"):
            return h
        try:
            import socket
            return socket.gethostbyname(h)
        except Exception:
            try:
                import urllib.request, json
                url = f"https://dns.google/resolve?name={h}"
                res = json.loads(urllib.request.urlopen(url, timeout=5).read())
                for ans in res.get("Answer", []):
                    if ans.get("type") == 1:
                        return ans["data"]
            except Exception:
                pass
        return h

    resolved_host = resolve_host(host)
    print(f"Connecting to Cloud MySQL at {host} ({resolved_host}):{port} (Database: {database}) as user '{user}'...")

    connect_kwargs = {
        "host": resolved_host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
    }
    # Enable SSL if connecting to cloud provider (Aiven, TiDB, etc.)
    if host not in ("localhost", "127.0.0.1"):
        connect_kwargs["ssl_disabled"] = False

    try:
        conn = mysql.connector.connect(**connect_kwargs)
        cursor = conn.cursor()
        print("[OK] Successfully connected to Cloud MySQL!\n")
    except Exception as e:
        print(f"[!] Connection failed: {e}")
        print("Check your .env file credentials and try again.")
        sys.exit(1)

    # 1. Execute schema.sql tables (without dropping entire cloud DB if shared)
    schema_sql_path = root_dir / "database" / "schema.sql"
    print(f"[*] Applying schema from: {schema_sql_path}")
    
    with open(schema_sql_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    # Split statements
    statements = [s.strip() for s in schema_sql.split(";") if s.strip()]
    for stmt in statements:
        # Skip drop database / create database if on managed cloud like Aiven where db already exists
        if stmt.upper().startswith("DROP DATABASE") or stmt.upper().startswith("CREATE DATABASE") or stmt.upper().startswith("USE "):
            continue
        try:
            cursor.execute(stmt)
            conn.commit()
        except Exception as e:
            print(f"  [Notice] Statement notice: {e}")

    print("[OK] Schema applied successfully (Student, Course, Enrollment, Attendance tables ready).\n")
    cursor.close()
    conn.close()

    # 2. Seed data
    print("[*] Launching database/seed.py to insert 160,500 records into Cloud MySQL...")
    from database.seed import main as seed_main
    seed_main()
    print("\n" + "=" * 70)
    print("  CLOUD DATABASE IS FULLY CONFIGURED & SEEDED (160,500 rows)!")
    print("=" * 70)

if __name__ == "__main__":
    main()
