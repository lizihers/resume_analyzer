"""Seed the database with all companies and positions from ai_service.py.

Run once: python seed_db.py
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env first
load_dotenv(Path(__file__).parent / ".env")

# Ensure the project root is importable
sys.path.insert(0, str(Path(__file__).parent))

from backend.database import init_db, add_company, add_position, get_all_companies, get_all_positions
from backend.ai_service import COMPANY_CAREERS, POSITIONS

# Ensure DB is initialized
init_db()

# ── Seed companies ──────────────────────────────────────────────────
existing = get_all_companies(active_only=False)
existing_names = {c["name"] for c in existing}
added = 0
skipped = 0

for c in COMPANY_CAREERS:
    name = c["name"]
    if name in existing_names:
        skipped += 1
        continue
    tags = ", ".join(c.get("tags", []))
    uid = add_company(name, c.get("url", ""), tags)
    if uid:
        added += 1
    else:
        skipped += 1

print(f"Companies: {added} added, {skipped} skipped (already exist)")

# ── Seed positions ──────────────────────────────────────────────────
existing = get_all_positions(active_only=False)
existing_roles = {p["role"] for p in existing}
added = 0
skipped = 0

for p in POSITIONS:
    role = p["role"]
    if role in existing_roles:
        skipped += 1
        continue
    skills = ", ".join(p.get("skills", []))
    tags = ", ".join(p.get("tags", []))
    urls = json.dumps(p.get("recruitment_urls", []), ensure_ascii=False)
    uid = add_position(
        role=role,
        skills=skills,
        description=p.get("description", ""),
        salary_range=p.get("salary_range", ""),
        tags=tags,
        recruitment_urls=urls,
    )
    if uid:
        added += 1
    else:
        skipped += 1

print(f"Positions: {added} added, {skipped} skipped (already exist)")

# ── Summary ─────────────────────────────────────────────────────────
companies = get_all_companies()
positions = get_all_positions()
print(f"\nDatabase ready: {len(companies)} companies, {len(positions)} positions")
