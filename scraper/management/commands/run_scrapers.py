"""
scraper/management/commands/run_scrapers.py
"""
import logging
from django.core.management.base import BaseCommand
from scraper.hwk_koblenz     import HwkKoblenzScraper
from scraper.hwk_trier        import HwkTrierScraper
from scraper.hwk_pfalz        import HwkPfalzScraper
from scraper.hwk_rheinhessen  import HwkRheinhessenScraper
from scraper.hwk_saarland     import HwkSaarlandScraper

SCRAPERS = {
    "hwk-koblenz":    HwkKoblenzScraper,
    "hwk-trier":      HwkTrierScraper,
    "hwk-pfalz":      HwkPfalzScraper,
    "hwk-rheinhessen": HwkRheinhessenScraper,
    "hwk-saarland":   HwkSaarlandScraper,
}

class Command(BaseCommand):
    help = "Run course scrapers for one or all chambers"

    def add_arguments(self, parser):
        parser.add_argument(
            "--chamber", choices=list(SCRAPERS.keys()),
            help="Run only a specific chamber's scraper",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Scrape but do not save to database",
        )

    def _fix_saarland_coordinates(self) -> int:
        """Force-set coordinates for HWK Saarland (single location)."""
        from courses.models import CourseOffer
        from chambers.models import Chamber
        try:
            chamber = Chamber.objects.get(slug="hwk-saarland")
        except Chamber.DoesNotExist:
            return 0
        return CourseOffer.objects.filter(
            chamber=chamber,
            is_active=True,
        ).update(latitude=49.2297, longitude=6.9967)

    def _fix_rheinhessen_coordinates(self) -> int:
        """
        Fix coordinates for HWK Rheinhessen courses that Nominatim geocodes
        inconsistently:
        - Empty street → set to Robert-Bosch-Straße 8 (default location)
        - Robert-Bosch-Straße → force-set to known coords (Nominatim unreliable)
        - Dekan-Laist-Str. → leave untouched (already correctly geocoded)
        """
        from courses.models import CourseOffer
        from chambers.models import Chamber
        try:
            chamber = Chamber.objects.get(slug="hwk-rheinhessen")
        except Chamber.DoesNotExist:
            return 0

        LAT, LNG = 49.959692, 8.260685  # Robert-Bosch-Straße 8

        # Only fix courses without a street or with Robert-Bosch address
        updated = CourseOffer.objects.filter(
            chamber=chamber,
            is_active=True,
        ).exclude(
            street__icontains="dekan-laist"  # leave correctly placed courses alone
        ).update(
            street="Robert-Bosch-Straße 8",
            zip_code="55129",
            city="Mainz",
            latitude=LAT,
            longitude=LNG,
        )
        return updated

    def _deactivate_missing_future_courses(self, chamber_slug: str, current_offers) -> int:
        """
        Deactivate future courses in the DB that were NOT found in the current
        scrape. This handles courses removed from the website or with changed dates.
        Past courses are never touched.
        """
        from datetime import date as date_cls
        from courses.models import CourseOffer
        from chambers.models import Chamber

        today = date_cls.today()
        try:
            chamber = Chamber.objects.get(slug=chamber_slug)
        except Chamber.DoesNotExist:
            return 0

        # Build set of (source_url, start_date) from current scrape
        scraped_keys = set()
        for offer in current_offers:
            if offer.source_url:
                scraped_keys.add((offer.source_url, str(offer.start_date)))

        if not scraped_keys:
            return 0  # Safety: never deactivate if scrape returned nothing

        # Find active future DB records not in current scrape
        deactivated = 0
        db_offers = CourseOffer.objects.filter(
            chamber=chamber,
            is_active=True,
            start_date__gte=today,
        )
        for db_offer in db_offers:
            key = (db_offer.source_url, str(db_offer.start_date))
            if key not in scraped_keys:
                db_offer.is_active = False
                db_offer.save(update_fields=["is_active"])
                deactivated += 1
        return deactivated

    def _deactivate_stale_approx_dates(self, chamber_slug: str) -> int:
        """
        After a scrape, deactivate future first-of-month records (day=1)
        when an exact-date record exists for the same month/year/chamber/
        trade/parts/format. Past courses are never touched.
        """
        from datetime import date as date_cls
        from courses.models import CourseOffer
        from chambers.models import Chamber

        today = date_cls.today()
        deactivated = 0
        try:
            chamber = Chamber.objects.get(slug=chamber_slug)
        except Chamber.DoesNotExist:
            return 0

        # Only look at future approximate (first-of-month) records
        stale_candidates = CourseOffer.objects.filter(
            chamber=chamber,
            is_active=True,
            start_date__day=1,
            start_date__gte=today,
        )
        for stale in stale_candidates:
            # Is there an exact-date (day != 1) record for same month/year?
            exact_exists = CourseOffer.objects.filter(
                chamber=chamber,
                trade=stale.trade,
                has_part_1=stale.has_part_1,
                has_part_2=stale.has_part_2,
                has_part_3=stale.has_part_3,
                has_part_4=stale.has_part_4,
                format=stale.format,
                is_active=True,
                start_date__year=stale.start_date.year,
                start_date__month=stale.start_date.month,
            ).exclude(start_date__day=1).exists()

            if exact_exists:
                stale.is_active = False
                stale.save(update_fields=["is_active"])
                deactivated += 1
        return deactivated

    def handle(self, *args, **options):
        logging.basicConfig(level=logging.INFO,
                            format="%(levelname)s %(name)s: %(message)s")
        chamber = options.get("chamber")
        dry_run = options.get("dry_run")
        scrapers = (
            {chamber: SCRAPERS[chamber]} if chamber else SCRAPERS
        )
        for slug, cls in scrapers.items():
            self.stdout.write(f"\n▶ {slug}")
            scraper = cls()
            if dry_run:
                # Dry-run: fetch and log only, do not save
                offers = scraper.fetch_raw_courses()
                self.stdout.write(f"  Scraped {len(offers)} offers (dry-run, not saved)")
            else:
                # Full run: fetch offers first, then save
                current_offers = scraper.fetch_raw_courses()
                result = scraper.run()
                self.stdout.write(f"  Done: {result}")

                # Deactivate future courses no longer found on the website
                removed = self._deactivate_missing_future_courses(slug, current_offers)
                if removed:
                    self.stdout.write(f"  Cleanup: {removed} stale future course(s) deactivated")

                # Deactivate stale first-of-month records superseded by exact dates
                deactivated = self._deactivate_stale_approx_dates(slug)
                if deactivated:
                    self.stdout.write(
                        f"  Cleanup: {deactivated} stale approximate-date record(s) deactivated"
                    )
                # Force-set coordinates for known locations
                if slug == "hwk-saarland":
                    fixed = self._fix_saarland_coordinates()
                    if fixed:
                        self.stdout.write(f"  Coordinates: {fixed} Saarland record(s) updated")
                if slug == "hwk-rheinhessen":
                    fixed = self._fix_rheinhessen_coordinates()
                    if fixed:
                        self.stdout.write(f"  Coordinates: {fixed} Rheinhessen record(s) updated")