#!/usr/bin/env python
"""
scripts/export_legacy_data.py — ONE-TIME migration helper.

Exports data that lives ONLY in the Django/Neon database (and in no scraper)
into the checked-in JSON files the new static pipeline consumes:

  1. data/manual/exam_fees_manual.json  — admin-curated exam fees
                                           (Koblenz "bis zu", Rheinhessen, …)
  2. data/cache/geocode_cache.json       — existing coordinates, so the first
                                           CI scrape doesn't re-geocode everything
  3. data/courses.json                   — PAST courses, to seed history so the
                                           date filter keeps showing them

Run this ONCE, against the production database, while Django still exists:

    DATABASE_URL=postgresql://USER:PASS@HOST/DB \
    SECRET_KEY=anything \
    DJANGO_SETTINGS_MODULE=config.settings \
        python scripts/export_legacy_data.py

Then commit the generated data/ files and proceed to remove Django.
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

import django

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from courses.models import CourseOffer, ExamFee  # noqa: E402
from scrapers.geocode import build_query           # noqa: E402
from scrapers.pipeline import FORMAT_DISPLAY, _short_name  # noqa: E402


def _f(v):
    return float(v) if v is not None else None


def export_manual_exam_fees() -> int:
    rows = []
    qs = ExamFee.objects.select_related("chamber", "trade").all()
    for ef in qs:
        # Keep anything not purely auto-scraped — these are the curated entries
        # that no scraper can regenerate.
        if ef.source_type == "scraped" and not ef.manually_verified:
            continue
        rows.append({
            "chamber_slug": ef.chamber.slug,
            "trade_slug":   ef.trade.slug if ef.trade else None,
            "part":         ef.part,
            "fee":          _f(ef.fee),
            "fee_max":      _f(ef.fee_max),
            "qualifier":    ef.fee_qualifier or "",
        })
    out = DATA_DIR / "manual" / "exam_fees_manual.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(rows)


def export_geocode_cache() -> int:
    cache: dict[str, list] = {}
    qs = CourseOffer.objects.select_related("chamber").filter(
        latitude__isnull=False, longitude__isnull=False,
    )
    for o in qs:
        query = build_query(o.street or "", o.zip_code or "", o.city or "", getattr(o.chamber, "region", ""))
        cache[query] = [float(o.latitude), float(o.longitude)]
    out = DATA_DIR / "cache" / "geocode_cache.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return len(cache)


def export_past_courses() -> int:
    today = date.today()
    records = []
    qs = CourseOffer.objects.select_related("chamber", "trade").filter(
        is_active=True, start_date__lt=today,
    )
    for o in qs:
        fee = _f(o.course_fee)
        ef = o.resolved_exam_fee_info()
        records.append({
            "chamber_slug":     o.chamber.slug,
            "chamber_name":     _short_name(o.chamber.name),
            "chamber_region":   o.chamber.region,
            "trade_slug":       o.trade.slug if o.trade else None,
            "trade_name":       o.trade.name if o.trade else None,
            "title":            o.title,
            "parts":            o.included_parts,
            "format":           o.format,
            "format_display":   FORMAT_DISPLAY.get(o.format, o.format),
            "teaching_mode":    o.teaching_mode,
            "start_date":       o.start_date.isoformat() if o.start_date else None,
            "end_date":         o.end_date.isoformat() if o.end_date else None,
            "duration_hours":   o.duration_hours,
            "course_fee":       fee,
            "course_fee_display": o.course_fee_display,
            "exam_fee_scraped": _f(o.exam_fee_scraped),
            "exam_fee":         {k: (_f(v) if k in ("fee", "fee_max") else v) for k, v in ef.items()},
            "city":             o.city,
            "street":           o.street,
            "zip_code":         o.zip_code,
            "latitude":         _f(o.latitude),
            "longitude":        _f(o.longitude),
            "availability":     o.availability,
            "source_url":       o.source_url,
        })
    out = DATA_DIR / "courses.json"
    if out.exists():
        print(f"  ! {out} already exists — NOT overwriting. Remove it first to re-seed.")
        return 0
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(records)


if __name__ == "__main__":
    n_fees = export_manual_exam_fees()
    n_geo = export_geocode_cache()
    n_past = export_past_courses()
    print(f"Exported {n_fees} manual exam fee(s) → data/manual/exam_fees_manual.json")
    print(f"Exported {n_geo} geocode cache entr(ies) → data/cache/geocode_cache.json")
    print(f"Exported {n_past} past course(s) → data/courses.json (history seed)")
