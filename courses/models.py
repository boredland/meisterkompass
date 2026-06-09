"""
courses/models.py
"""

from django.db import models
from django.core.exceptions import ValidationError
from chambers.models import Chamber, Trade


class CourseFormat(models.TextChoices):
    FULL_TIME    = "full_time",    "Vollzeit"
    PART_TIME    = "part_time",    "Teilzeit"
    PART_OR_FULL = "part_or_full", "Teil- oder Vollzeit"


class TeachingMode(models.TextChoices):
    PRESENCE = "presence", "Präsenz"
    ONLINE   = "online",   "Online"
    HYBRID   = "hybrid",   "Hybrid"


class Availability(models.TextChoices):
    AVAILABLE = "available", "Freie Plätze"
    FEW_SPOTS = "few_spots", "Wenige Plätze"
    FULL      = "full",      "Ausgebucht"
    WAITLIST  = "waitlist",  "Warteliste"
    UNKNOWN   = "unknown",   "Unbekannt"


class ExamSourceType(models.TextChoices):
    SCRAPED      = "scraped",      "Scraped automatically"
    PDF_MANUAL   = "pdf_manual",   "Taken from PDF (manually entered)"
    ADMIN_MANUAL = "admin_manual", "Entered via admin interface"


class CourseOffer(models.Model):
    """
    One course offering exactly as listed on the chamber website.
    """

    chamber = models.ForeignKey(
        Chamber, on_delete=models.CASCADE, related_name="course_offers",
    )
    trade = models.ForeignKey(
        Trade, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="course_offers",
        help_text="Leave blank for generic Parts III+IV courses.",
    )
    title        = models.CharField(max_length=300)
    has_part_1   = models.BooleanField(default=False, verbose_name="Part I")
    has_part_2   = models.BooleanField(default=False, verbose_name="Part II")
    has_part_3   = models.BooleanField(default=False, verbose_name="Part III")
    has_part_4   = models.BooleanField(default=False, verbose_name="Part IV")
    format       = models.CharField(max_length=20, choices=CourseFormat.choices)
    teaching_mode = models.CharField(
        max_length=20, choices=TeachingMode.choices,
        default=TeachingMode.PRESENCE, verbose_name="Unterrichtsform",
    )
    start_date     = models.DateField(null=True, blank=True)
    end_date       = models.DateField(null=True, blank=True)
    duration_hours = models.PositiveIntegerField(null=True, blank=True,
                                                  verbose_name="Duration (hours)")

    # Kursgebühr
    course_fee = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                      help_text="Course fee in EUR, excluding exam fees.")

    # Prüfungsgebühr — only populated when stated directly on the course page
    # (e.g. HWK Trier). For the authoritative per-part record see ExamFee.
    exam_fee_scraped = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name="Prüfungsgebühr (scraped)",
        help_text=(
            "Exam fee as stated on this specific course page. "
            "May cover one or multiple parts. "
            "The ExamFee model holds the per-part breakdown for the total-cost calculator."
        ),
    )

    city          = models.CharField(max_length=100, blank=True)
    location_name = models.CharField(max_length=200, blank=True)
    street        = models.CharField(max_length=200, blank=True)
    zip_code      = models.CharField(max_length=10,  blank=True)
    latitude      = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude     = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    availability = models.CharField(max_length=20, choices=Availability.choices,
                                     default=Availability.UNKNOWN)
    is_active     = models.BooleanField(default=True)
    source_url    = models.URLField(blank=True)
    last_scraped_at = models.DateTimeField(null=True, blank=True)
    scraped_raw   = models.JSONField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["chamber__name", "trade__name", "start_date"]
        verbose_name = "Course Offer"
        verbose_name_plural = "Course Offers"

    def __str__(self):
        return f"{self.chamber} · {self.title}"

    def clean(self):
        if not any([self.has_part_1, self.has_part_2, self.has_part_3, self.has_part_4]):
            raise ValidationError("A CourseOffer must include at least one exam part.")

    @property
    def parts_label(self) -> str:
        roman = {1: "I", 2: "II", 3: "III", 4: "IV"}
        included = [roman[p] for p, f in [(1, self.has_part_1), (2, self.has_part_2),
                                           (3, self.has_part_3), (4, self.has_part_4)] if f]
        if not included:
            return "—"
        return " + ".join(included)

    @property
    def included_parts(self) -> list[int]:
        return [p for p, f in [(1, self.has_part_1), (2, self.has_part_2),
                                (3, self.has_part_3), (4, self.has_part_4)] if f]

    @property
    def course_fee_display(self) -> str:
        """Format course fee as German number without decimals, e.g. '6.990 €'."""
        if self.course_fee is None:
            return "—"
        return f"{self.course_fee:,.0f}".replace(",", ".") + " €"

    def resolved_exam_fee_info(self, exam_fee_lookup: dict | None = None) -> dict:
        """
        Returns the best available exam fee info for display.

        Priority:
          1. exam_fee_scraped on this CourseOffer (from Trier/Pfalz scrapers)
          2. ExamFee model records — summed across all parts this offer covers,
             trade-specific first, then all-trades (trade=None) fallback.

        For multi-part offers (e.g. Parts I+II), fees are summed.
        If any part has a qualifier (e.g. "bis zu"), it applies to the total.

        exam_fee_lookup: optional pre-built dict
            {(chamber_id, trade_id_or_None, part): ExamFee}
            Pass from view context to avoid repeated DB queries.

        Returns dict with keys:
            fee        Decimal | None
            qualifier  str ("bis zu" or "")
            display    str  e.g. "bis zu 760,00 €" or "1.130,00 €" or ""
        """
        from decimal import Decimal

        # Priority 1: scraped fee
        if self.exam_fee_scraped is not None:
            fee_str = f"{self.exam_fee_scraped:,.0f}".replace(",", ".") + " €"
            return {"fee": self.exam_fee_scraped, "qualifier": "", "display": fee_str, "fee_max": None}

        # Priority 2: ExamFee model lookup
        total_min = Decimal("0")
        total_max = Decimal("0")
        qualifier = ""
        found     = False
        has_range = False

        for part in self.included_parts:
            ef = None
            if exam_fee_lookup is not None:
                ef = (
                    exam_fee_lookup.get((self.chamber_id, self.trade_id, part))
                    or exam_fee_lookup.get((self.chamber_id, None, part))
                )
            else:
                ef = ExamFee.objects.filter(
                    chamber_id=self.chamber_id, trade_id=self.trade_id, part=part
                ).first()
                if not ef:
                    ef = ExamFee.objects.filter(
                        chamber_id=self.chamber_id, trade__isnull=True, part=part
                    ).first()

            if ef:
                total_min += ef.fee
                total_max += ef.fee_max if ef.fee_max else ef.fee
                if ef.fee_max:
                    has_range = True
                if ef.fee_qualifier and not qualifier:
                    qualifier = ef.fee_qualifier
                found = True

        if not found:
            return {"fee": None, "fee_max": None, "qualifier": "", "display": ""}

        def fmt(v):
            return f"{v:,.0f}".replace(",", ".") + " €"

        if has_range:
            display = f"{fmt(total_min)} bis {fmt(total_max)}"
            return {"fee": total_min, "fee_max": total_max, "qualifier": "", "display": display}

        fee_str = fmt(total_min)
        display = f"{qualifier} {fee_str}".strip() if qualifier else fee_str
        return {"fee": total_min, "fee_max": None, "qualifier": qualifier, "display": display}


class ExamFee(models.Model):
    PART_CHOICES = [
        (1, "Part I   – Practical/technical"),
        (2, "Part II  – Theory/technical"),
        (3, "Part III – Business administration"),
        (4, "Part IV  – Vocational training"),
    ]
    chamber = models.ForeignKey(Chamber, on_delete=models.CASCADE, related_name="exam_fees")
    trade   = models.ForeignKey(
        Trade,
        on_delete=models.CASCADE,
        related_name="exam_fees",
        null=True, blank=True,
        help_text=(
            "Leave blank to apply this fee to ALL trades at this chamber for the selected part. "
            "A trade-specific entry always takes precedence over an all-trades entry."
        ),
    )
    part              = models.IntegerField(choices=PART_CHOICES)
    fee     = models.DecimalField(
        max_digits=8, decimal_places=2,
        help_text="Fee amount (or lower bound of a range).",
    )
    fee_max = models.DecimalField(
        max_digits=8, decimal_places=2,
        null=True, blank=True,
        help_text=(
            "Optional upper bound for a range, e.g. enter 600 here and 2000 in fee_max "
            "to display '600,00 bis 2.000,00 €'. Leave blank for a single value."
        ),
    )
    fee_qualifier     = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text=(
            "Optional qualifier displayed before the fee, e.g. 'bis zu' for maximum fees "
            "(as in HWK Koblenz Gebührenverzeichnis). Leave blank for exact amounts. "
            "Not used when fee_max is set (the range itself communicates variability)."
        ),
    )
    scraper_may_overwrite = models.BooleanField(default=True)
    manually_verified = models.BooleanField(default=False)
    source_type       = models.CharField(max_length=20, choices=ExamSourceType.choices,
                                          default=ExamSourceType.SCRAPED)
    source_url        = models.URLField(blank=True)
    valid_from        = models.DateField(null=True, blank=True)
    valid_until       = models.DateField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["chamber__name", "trade__name", "part"]
        verbose_name = "Exam Fee"
        verbose_name_plural = "Exam Fees"
        # Note: unique_together cannot enforce NULL uniqueness in all DBs.
        # Uniqueness for trade-specific entries is enforced here;
        # all-trades entries (trade=NULL) are validated in clean().

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.trade is None:
            # Only one all-trades entry per chamber+part
            qs = ExamFee.objects.filter(
                chamber=self.chamber, trade__isnull=True, part=self.part
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    f"An all-trades exam fee for this chamber and part already exists."
                )
        else:
            # Only one trade-specific entry per chamber+trade+part
            qs = ExamFee.objects.filter(
                chamber=self.chamber, trade=self.trade, part=self.part
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    f"An exam fee for this chamber, trade, and part already exists."
                )

    def __str__(self):
        roman     = {1: "I", 2: "II", 3: "III", 4: "IV"}
        trade_str = self.trade.name if self.trade else "Alle Gewerke"
        return f"{self.chamber} · {trade_str} · Part {roman[self.part]} · {self.fee_display}"

    @staticmethod
    def _fmt(amount) -> str:
        """Format a Decimal as German number string without decimals, e.g. '1.130 €'."""
        return f"{amount:,.0f}".replace(",", ".") + " €"

    @property
    def fee_display(self) -> str:
        """
        Human-readable fee string. Examples:
          Single exact:   "1.130,00 €"
          With qualifier: "bis zu 380,00 €"
          Range:          "600,00 bis 2.000,00 €"
        """
        if self.fee_max:
            return f"{self._fmt(self.fee)} bis {self._fmt(self.fee_max)}"
        fee_str = self._fmt(self.fee)
        return f"{self.fee_qualifier} {fee_str}".strip()