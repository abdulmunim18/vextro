#!/usr/bin/env python3
"""
VEXTRO Data Warehouse - Audit & Health Inspection Tool
Prints detailed health summary for FYP documentation.
Usage:
    python scripts/warehouse_audit.py
"""

import os
import sys
from datetime import datetime
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text

# Accept either the backend .env naming (DB_*) or the legacy POSTGRES_*
# names, whichever is set. No baked-in password: force the caller to
# supply one via the environment so we cannot leak a stale default.
DB_HOST = os.getenv("DB_HOST") or os.getenv("POSTGRES_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT") or os.getenv("POSTGRES_PORT", "5432")
DB_USER = os.getenv("DB_USER") or os.getenv("POSTGRES_USER", "vextro_app")
DB_PASSWORD = os.getenv("DB_PASSWORD") or os.getenv("POSTGRES_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME") or os.getenv("POSTGRES_DB", "vextro_db")

if not DB_PASSWORD:
    raise SystemExit(
        "Set DB_PASSWORD (or POSTGRES_PASSWORD) before running the audit."
    )

# Explicit psycopg (v3) driver so this script uses the same DBAPI the
# backend requirements pin, instead of pulling psycopg2 as a hidden dep.
# URL-encode user/password so special chars like ``@`` in the password do
# not corrupt the connection URL's parsed host.
DB_URL = (
    f"postgresql+psycopg://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

def run_warehouse_audit():
    print("==========================================================")
    print("    VEXTRO CENTRALIZED DATA WAREHOUSE & HEALTH AUDIT     ")
    print("==========================================================")
    print(f" Timestamp : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" Database  : {DB_NAME} on {DB_HOST}:{DB_PORT}")
    print("----------------------------------------------------------")

    engine = create_engine(DB_URL)

    with engine.connect() as conn:
        def q(query):
            return conn.execute(text(query)).scalar() or 0

        canonicals = q("SELECT COUNT(*) FROM canonical_products")
        variants = q("SELECT COUNT(*) FROM product_variants")
        listings = q("SELECT COUNT(*) FROM product_listings")
        observations = q("SELECT COUNT(*) FROM price_history")
        scrape_runs = q("SELECT COUNT(*) FROM scrape_runs")

        print(" [+] WAREHOUSE CORE METRICS:")
        print(f"   * Canonical Products (Shared Identity) : {canonicals}")
        print(f"   * Product Variants (RAM / Storage)    : {variants}")
        print(f"   * Active Product Listings             : {listings}")
        print(f"   * Historical Price Observations       : {observations}")
        print(f"   * Registered Scraper Execution Runs   : {scrape_runs}")
        print("----------------------------------------------------------")

        # Marketplace breakdown
        platforms = conn.execute(text("""
            SELECT p.name, COUNT(l.id) as listing_cnt 
            FROM platforms p 
            LEFT JOIN product_listings l ON l.platform_id = p.id 
            GROUP BY p.name
        """)).fetchall()

        print(" [+] MARKETPLACE COVERAGE:")
        for p_name, p_cnt in platforms:
            print(f"   * {p_name:<15} : {p_cnt} listings")
        print("----------------------------------------------------------")

        # Last 5 Scrape Runs. Uses the acquisition-chain column names
        # (items_ingested / items_rejected / items_failed) that the
        # scraper's monitoring extension and the ORM model actually write.
        runs = conn.execute(text("""
            SELECT id, platform, status, items_discovered, items_ingested,
                   items_rejected, items_failed, started_at
            FROM scrape_runs
            ORDER BY started_at DESC
            LIMIT 5
        """)).fetchall()

        print(" [+] RECENT SCRAPE RUN AUDIT LOG:")
        if not runs:
            print("   (No scrape runs recorded yet)")
        else:
            for rid, rplat, rstat, rdisc, ring, rrej, rfail, rtime in runs:
                print(
                    f"   * Run #{rid:<3} | {rplat:<10} | {rstat:<8} | "
                    f"discovered {rdisc:<4} ingested {ring:<4} "
                    f"rejected {rrej:<4} failed {rfail:<4} | {rtime}"
                )

        print("==========================================================")
        print(" SUCCESS: WAREHOUSE AUDIT COMPLETED!")
        print("==========================================================")

if __name__ == "__main__":
    run_warehouse_audit()
