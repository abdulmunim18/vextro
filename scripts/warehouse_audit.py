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
from sqlalchemy import create_engine, text

DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "1234")
DB_NAME = os.getenv("POSTGRES_DB", "vextro_db")

DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

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

        # Last 5 Scrape Runs
        runs = conn.execute(text("""
            SELECT id, platform, status, items_scraped, started_at 
            FROM scrape_runs 
            ORDER BY started_at DESC 
            LIMIT 5
        """)).fetchall()

        print(" [+] RECENT SCRAPE RUN AUDIT LOG:")
        if not runs:
            print("   (No scrape runs recorded yet)")
        else:
            for rid, rplat, rstat, rcnt, rtime in runs:
                print(f"   * Run #{rid:<3} | {rplat:<10} | {rstat:<8} | Scraped: {rcnt:<3} | {rtime}")

        print("==========================================================")
        print(" SUCCESS: WAREHOUSE AUDIT COMPLETED!")
        print("==========================================================")

if __name__ == "__main__":
    run_warehouse_audit()
