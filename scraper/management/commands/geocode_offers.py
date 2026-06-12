"""
scraper/management/commands/geocode_offers.py

Geocodes CourseOffer records using Nominatim (OpenStreetMap).
Uses the full address (street + ZIP + city) when available for pin-level
precision; falls back to city-only when street is missing.

Usage:
    python manage.py geocode_offers
    python manage.py geocode_offers --force   # re-geocode all existing coords
"""

import time
import requests
from django.core.management.base import BaseCommand
from courses.models import CourseOffer


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "MeisterKompassBot/1.0 (+https://meisterkompass.de)"}
DELAY = 1.1   # Nominatim rate limit: max 1 request/second


class Command(BaseCommand):
    help = "Geocode CourseOffer records via Nominatim (OpenStreetMap)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true",
            help="Re-geocode offers that already have coordinates.",
        )

    def handle(self, *args, **options):
        force = options["force"]
        qs = CourseOffer.objects.filter(city__gt="").select_related("chamber")
        if not force:
            qs = qs.filter(latitude__isnull=True)

        total = qs.count()
        self.stdout.write(f"Geocoding {total} offer(s)...\n")

        cache: dict[str, tuple | None] = {}
        success = failed = 0

        for offer in qs.iterator():
            query = self._build_query(offer)

            if query not in cache:
                coords = self._geocode(query)
                cache[query] = coords
                time.sleep(DELAY)
            else:
                coords = cache[query]

            if coords:
                offer.latitude, offer.longitude = coords
                offer.save(update_fields=["latitude", "longitude"])
                success += 1
                self.stdout.write(
                    f"  ✔ {query[:60]} → {coords[0]:.4f}, {coords[1]:.4f}"
                )
            else:
                failed += 1
                self.stdout.write(
                    self.style.WARNING(f"  ✘ Could not geocode: {query[:60]}")
                )

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Success: {success} | Failed: {failed}"
        ))

    def _build_query(self, offer: CourseOffer) -> str:
        """
        Build Nominatim query string.
        Full address (street + ZIP + city) when available — gives pin-level
        accuracy. Falls back to city + region for city-centre coordinates.
        """
        city   = offer.city or ""
        street = (offer.street or "").strip()
        zcode  = (offer.zip_code or "").strip()
        region = getattr(offer.chamber, "region", "") or "Deutschland"

        if street and zcode:
            # Precise: "Dagobertstraße 2, 55116 Mainz, Deutschland"
            return f"{street}, {zcode} {city}, Deutschland"
        elif street:
            return f"{street}, {city}, Deutschland"
        elif zcode:
            return f"{zcode} {city}, Deutschland"
        else:
            return f"{city}, {region}, Deutschland"

    def _geocode(self, query: str) -> tuple[float, float] | None:
        try:
            r = requests.get(
                NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": 1},
                headers=HEADERS,
                timeout=10,
            )
            r.raise_for_status()
            results = r.json()
            if results:
                return float(results[0]["lat"]), float(results[0]["lon"])
        except Exception as exc:
            self.stdout.write(
                self.style.ERROR(f"  Nominatim error for {query!r}: {exc}")
            )
        return None