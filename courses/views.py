"""
courses/views.py
"""

import json
from datetime import date as date_cls
from django.views.generic import ListView, TemplateView
from django.db.models import Q, Case, When, IntegerField, Value
from .models import CourseOffer, CourseFormat
from chambers.models import Chamber, Trade

PER_PAGE_OPTIONS = [10, 20, 30, 40, 60]
PER_PAGE_DEFAULT = 20


class CourseListView(ListView):
    model = CourseOffer
    template_name = "courses/list.html"
    context_object_name = "offers"

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get("per_page", "")
        if per_page == "all":
            return None
        try:
            val = int(per_page)
            if val in PER_PAGE_OPTIONS:
                return val
        except (ValueError, TypeError):
            pass
        return PER_PAGE_DEFAULT

    def _apply_filters(self, qs):
        p = self.request.GET
        if v := p.get("chamber"):   qs = qs.filter(chamber__slug=v)
        if v := p.get("trade"):     qs = qs.filter(trade__slug=v)
        if v := p.get("format"):    qs = qs.filter(format=v)
        if p.get("available"):      qs = qs.filter(availability="available")

        date_from = p.get("date_from")
        date_to   = p.get("date_to")

        if date_from:
            qs = qs.filter(start_date__gte=date_from)
        elif date_to:
            # date_to set but no date_from → include past up to that date
            qs = qs.filter(start_date__lte=date_to)
        else:
            # Default: only current/future courses + "Termine nicht verfügbar"
            today = date_cls.today()
            qs = qs.filter(Q(start_date__gte=today) | Q(start_date__isnull=True))

        if date_to and date_from:
            qs = qs.filter(start_date__lte=date_to)

        selected_parts = [int(x) for x in p.getlist("part") if x.isdigit()]
        include_combos = p.get("include_combos") == "1"

        if selected_parts:
            q = Q()
            for part in selected_parts:
                field = f"has_part_{part}"
                if include_combos:
                    q |= Q(**{field: True})
                else:
                    exact = {f"has_part_{pp}": (pp == part) for pp in [1, 2, 3, 4]}
                    q |= Q(**exact)
            qs = qs.filter(q)

        return qs

    def get_queryset(self):
        return self._apply_filters(
            CourseOffer.objects.filter(is_active=True)
            .select_related("chamber", "trade")
            .order_by("trade__name", "start_date")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["chambers"]         = Chamber.objects.all().order_by("name")
        ctx["formats"]          = CourseFormat.choices
        ctx["per_page_options"] = PER_PAGE_OPTIONS

        p = self.request.GET
        sel_chamber = p.get("chamber", "")

        if sel_chamber:
            trades_qs = Trade.objects.filter(
                course_offers__chamber__slug=sel_chamber,
                course_offers__is_active=True,
            ).distinct().order_by("name")
        else:
            trades_qs = Trade.objects.filter(
                course_offers__is_active=True
            ).distinct().order_by("name")
        ctx["trades"] = trades_qs

        # Count distinct chambers in the current filtered results
        ctx["filtered_chamber_count"] = (
            self.get_queryset().values("chamber").distinct().count()
        )
        ctx["sel_chamber"]        = sel_chamber
        ctx["sel_trade"]          = p.get("trade",         "")
        ctx["sel_format"]         = p.get("format",        "")
        ctx["sel_available"]      = p.get("available",     "")
        ctx["sel_parts"]          = p.getlist("part")
        ctx["sel_include_combos"] = p.get("include_combos", "") == "1"
        ctx["sel_date_from"]      = p.get("date_from",     "")
        ctx["sel_date_to"]        = p.get("date_to",       "")
        ctx["sel_per_page"]       = p.get("per_page",      "")
        ctx["view_mode"]          = p.get("view",          "list")

        from .models import ExamFee as EF
        chamber_ids = set(o.chamber_id for o in ctx["offers"])
        ef_qs = EF.objects.filter(chamber_id__in=chamber_ids).select_related("trade")
        exam_fee_lookup: dict = {}
        for ef in ef_qs:
            exam_fee_lookup[(ef.chamber_id, ef.trade_id, ef.part)] = ef

        for offer in ctx["offers"]:
            offer.exam_fee_info = offer.resolved_exam_fee_info(exam_fee_lookup)

        ctx["exam_fee_lookup"] = exam_fee_lookup

        map_qs = self._apply_filters(
            CourseOffer.objects
            .filter(is_active=True, latitude__isnull=False, longitude__isnull=False)
            .select_related("chamber", "trade")
            .order_by("start_date")
        )
        from .models import ExamFee as EF2
        map_chamber_ids = set(o.chamber_id for o in map_qs)
        map_ef_lookup: dict = {}
        for ef in EF2.objects.filter(chamber_id__in=map_chamber_ids).select_related("trade"):
            map_ef_lookup[(ef.chamber_id, ef.trade_id, ef.part)] = ef

        ctx["map_data_json"] = json.dumps([
            {
                "title":            o.title,
                "trade":            o.trade.name if o.trade else "Allgemein",
                "chamber":          o.chamber.short_name,
                "city":             o.city,
                "lat":              float(o.latitude),
                "lng":              float(o.longitude),
                "fee":              float(o.course_fee) if o.course_fee else None,
                "exam_fee":         float(ef_info["fee"]) if ef_info["fee"] else None,
                "exam_fee_display": ef_info["display"],
                "format":           o.get_format_display(),
                "parts":            o.parts_label,
                "start":            o.start_date.strftime("%d.%m.%Y") if o.start_date else "",
                "url":              o.source_url,
            }
            for o in map_qs
            for ef_info in [o.resolved_exam_fee_info(map_ef_lookup)]
        ])

        filter_params = "&".join(
            f"{k}={v}" for k, v in p.items()
            if k not in ("view", "page") and v
        )
        ctx["list_url_params"] = filter_params
        return ctx


class AfbgView(TemplateView):
    """AFBG (Aufstiegs-BAföG) calculator page."""
    template_name = "pages/afbg.html"

    def get_context_data(self, **kwargs):
        from .models import ExamFee

        ctx = super().get_context_data(**kwargs)

        # ── Exam fees ────────────────────────────────────────────────
        ef_lookup: dict = {}
        try:
            for ef in ExamFee.objects.select_related("chamber", "trade").all():
                cid = str(ef.chamber_id)
                tid = str(ef.trade_id) if ef.trade_id else "null"
                ef_lookup.setdefault(cid, {}).setdefault(tid, {})[ef.part] = {
                    "fee":       float(ef.fee),
                    "fee_max":   float(ef.fee_max) if ef.fee_max else None,
                    "qualifier": ef.fee_qualifier or "",
                }
        except Exception:
            pass

        # ── Course fees: next available course per chamber+trade+parts ──
        # Priority: future courses with available spots first, then any course.
        # "Next" means nearest start_date >= today; fallback to any date.
        fee_list: list = []
        try:
            today = date_cls.today()

            AVAIL_RANK = {"available": 0, "few_spots": 1, "full": 2, "unknown": 3}

            all_offers = list(
                CourseOffer.objects
                .filter(is_active=True, course_fee__isnull=False)
                .select_related("chamber", "trade")
                .order_by("start_date")
            )

            def sort_key(o):
                is_future = o.start_date is None or o.start_date >= today
                avail     = AVAIL_RANK.get(o.availability, 3)
                if o.start_date:
                    d = o.start_date.toordinal()
                    date_score = d if is_future else (10_000_000 - d)
                else:
                    date_score = 5_000_000
                return (0 if is_future else 1, avail, date_score)

            all_offers.sort(key=sort_key)

            seen: dict = {}
            for o in all_offers:
                key = (o.chamber_id, o.trade_id, tuple(o.included_parts))
                if key not in seen:
                    seen[key] = {
                        "chamber_id":       o.chamber_id,
                        "trade_id":         o.trade_id,
                        "parts":            o.included_parts,
                        "fee":              float(o.course_fee),
                        # Include scraped exam fee for AFBG calculator auto-fill
                        "exam_fee_scraped": float(o.exam_fee_scraped) if o.exam_fee_scraped else None,
                    }
            fee_list = list(seen.values())
        except Exception:
            pass

        # ── Chambers & trades ────────────────────────────────────────
        try:
            chambers = [
                {"id": c.id, "name": c.short_name, "slug": c.slug}
                for c in Chamber.objects.order_by("name")
            ]
        except Exception:
            chambers = []

        try:
            # Only show trades that have I or II course offers (not generic III/IV trades)
            trade_ids_with_12 = {
                o["trade_id"] for o in fee_list
                if o["trade_id"] and any(p in [1, 2] for p in o["parts"])
            }
            trades = [
                {"id": t.id, "name": t.name, "slug": t.slug}
                for t in Trade.objects.filter(id__in=trade_ids_with_12).order_by("name")
            ]
        except Exception:
            trades = []

        # Mark generic (III/IV only) entries so JS can identify them
        for entry in fee_list:
            entry["is_generic"] = all(p in [3, 4] for p in entry["parts"])

        ctx["chambers_json"]    = json.dumps(chambers)
        ctx["trades_json"]      = json.dumps(trades)
        ctx["course_fees_json"] = json.dumps(fee_list)
        ctx["exam_fees_json"]   = json.dumps(ef_lookup)
        return ctx