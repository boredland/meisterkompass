# MeisterKompass

An independent, non-commercial comparison platform for Meister preparation
courses offered by Handwerkskammern (HWK) in Germany.

Enables direct comparison of prices, duration, and exam fees across chambers,
as well as calculation of AFBG (Aufstiegs-BAföG) funding.

Current scope: five chambers — four in Rhineland-Palatinate (Koblenz, Pfalz,
Rheinhessen, Trier) and HWK des Saarlandes. Designed to scale to all chambers
nationwide.

**Currently live:** HWK Koblenz, HWK Trier, HWK Pfalz, HWK Rheinhessen,
HWK des Saarlandes.

---

## Features

- Filterable course listings per trade, chamber, format, and exam part
- Multi-part filter with optional "include combination courses" toggle
- "Plätze verfügbar" toggle to filter for courses with open spots
- Default view shows only upcoming courses; past courses visible via date filter
- Course fees and examination fees displayed side by side (no decimal places)
- "bis zu" qualifier and fee ranges for maximum-fee entries (e.g. HWK Koblenz)
- ⓘ tooltip explaining the source of exam fee data
- **Laufzeit column**: start and end date stacked in one column
- **Availability badges**: Freie Plätze (green), Warteliste (orange), Ausgebucht (red)
- Interactive map with geocoded course location pins (Leaflet + CartoDB)
- Automatic price/fee propagation from nearest available course
- "Termine nicht verfügbar" indicator for courses without scheduled dates
- Responsive design for desktop, tablet, and mobile
- Tab navigation: Kursfinder, AFBG-Rechner, Über MeisterKompass, Impressum
- AFBG-Rechner: calculates Aufstiegs-BAföG funding for course fees and
  Meisterprojekt costs, with auto-fill from Kursfinder data
- AFBG-Rechner: combo course deduplication (prefers combo when all parts selected)
- AFBG-Rechner: "Einzelne Kursteile bevorzugen" option to override combos
- AFBG-Rechner: fallback to combo if no individual course exists
- Django admin for manual data entry and exam fee verification
- Weekly automated data updates via GitHub Actions

---

## Tech Stack

| Layer       | Technology                                      |
|-------------|--------------------------------------------------|
| Backend     | Django 6.x                                       |
| Database    | SQLite (dev) / PostgreSQL via Neon (prod)        |
| Scraping    | requests + BeautifulSoup                         |
| Frontend    | Django Templates + Leaflet.js                    |
| Map tiles   | CartoDB (no API key required)                    |
| Geocoding   | Nominatim / OpenStreetMap (no API key required)  |
| Hosting     | Render (web app) + Neon (database)               |
| Cron        | GitHub Actions (every Friday 03:00 UTC)          |

---

## Project Structure

```
meisterkompass/
├── config/                   # Django project settings, URLs, WSGI
├── chambers/                 # Chamber and Trade models + admin
├── courses/                  # CourseOffer, ExamFee models + admin
│   ├── calculators.py        # Total cost calculation logic
│   └── views.py              # CourseListView + AfbgView
├── scraper/                  # Scraper pipeline
│   ├── base.py               # Abstract base + RawCourseOffer + build_course_title
│   ├── hwk_koblenz.py        # HWK Koblenz ✓
│   ├── hwk_trier.py          # HWK Trier ✓  (incl. exam fees)
│   ├── hwk_pfalz.py          # HWK Pfalz ✓  (incl. exam fees)
│   ├── hwk_rheinhessen.py    # HWK Rheinhessen ✓  (WordPress-based)
│   ├── hwk_saarland.py       # HWK des Saarlandes ✓  (WordPress-based)
│   └── management/commands/
│       ├── run_scrapers.py    # python manage.py run_scrapers
│       └── geocode_offers.py  # python manage.py geocode_offers
├── templates/
│   ├── base.html             # Nav bar + shared styles + responsive
│   ├── courses/
│   │   └── list.html         # Kursfinder (filterable list + map)
│   └── pages/
│       ├── afbg.html         # AFBG-Rechner
│       ├── about.html        # Über MeisterKompass
│       └── imprint.html      # Impressum + Haftungsausschluss
├── .env                      # Local secrets — never commit to Git
├── requirements.txt
└── README.md
```

---

## Local Development Setup

### Prerequisites

- Python 3.11 or later
- Git

### Installation (Windows)

```bat
python -m venv .venv
.venv\Scripts\activate

pip install django dj-database-url python-decouple requests beautifulsoup4
```

### .env file

```
SECRET_KEY=replace-with-a-long-random-string
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3
ALLOWED_HOSTS=127.0.0.1,localhost
```

### Database setup

```bat
python manage.py makemigrations chambers courses scraper
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

---

## Running the Scrapers

```bat
python manage.py run_scrapers
python manage.py run_scrapers --chamber hwk-saarland --dry-run
python manage.py run_scrapers --chamber hwk-koblenz
python manage.py geocode_offers
```

After each full run, `run_scrapers` automatically:
1. Deactivates stale first-of-month records superseded by exact-date entries
2. Force-sets correct coordinates for all HWK des Saarlandes courses

### HWK des Saarlandes — first-time setup

After the first scrape, fix any legacy "Allgemein" city records:

```python
from courses.models import CourseOffer
from chambers.models import Chamber
chamber = Chamber.objects.get(slug="hwk-saarland")
CourseOffer.objects.filter(chamber=chamber).exclude(city="Saarbrücken").update(
    city="Saarbrücken", zip_code="66117", street="Hohenzollernstraße 47-49"
)
```

---

## Data Model

### CourseOffer

| Field              | Description                                                       |
|--------------------|-------------------------------------------------------------------|
| `title`            | Normalised title, e.g. "Metallbauer (Teile I + II)"              |
| `has_part_1..4`    | Which exam parts this course covers                               |
| `format`           | Vollzeit / Teilzeit                                               |
| `teaching_mode`    | Präsenz / Online / Hybrid (defaults to Präsenz)                   |
| `course_fee`       | Course fee in EUR                                                 |
| `exam_fee_scraped` | Exam fee from the course page (HWK Trier, Pfalz, Saarland)       |
| `start_date`       | Course start; `None` = "Termine nicht verfügbar"                  |
| `end_date`         | Course end date (where available)                                 |
| `city`             | City for map pin and geocoding                                    |
| `street`           | Street address                                                    |
| `zip_code`         | Postal code                                                       |
| `source_url`       | Direct link to the course page on the chamber website             |

Past courses are retained in the DB and visible when a past date filter is applied.

### Availability states

| Value       | Badge       | Meaning                          |
|-------------|-------------|----------------------------------|
| `available` | 🟢 Freie Plätze | Open spots (incl. "wenige Plätze") |
| `waitlist`  | 🟠 Warteliste   | Waitlist only                    |
| `full`      | 🔴 Ausgebucht   | No spots available               |
| `unknown`   | —           | Not stated on website            |

### ExamFee

| Chamber     | Source                                    | Notes                     |
|-------------|-------------------------------------------|---------------------------|
| Trier       | Scraped from course detail pages          | Exact values              |
| Pfalz       | Scraped from course detail pages          | Exact values              |
| Saarland    | Scraped from course detail pages          | Exact values              |
| Koblenz     | Manual entry from Gebührenverzeichnis     | "bis zu" qualifier        |
| Rheinhessen | Manual entry per trade                    | Range or exact            |

- `fee_qualifier = "bis zu"` → "bis zu 380 €" with ⓘ tooltip
- `fee_max` set → "600 bis 2.000 €" with ⓘ tooltip
- `trade = null` → fee applies to all trades at this chamber for the given part

---

## AFBG-Rechner

Available at `/afbg/`. Calculates Aufstiegs-BAföG funding based on:

**Lehrgangs- und Prüfungsgebühren (up to €15,000):**
- 50 % Zuschuss (non-repayable)
- 50 % KfW-Darlehen
- 50 % Darlehenserlass upon passing

**Meisterprojekt (separate, up to €2,000):**
- 50 % Zuschuss
- 50 % KfW-Darlehen (no Darlehenserlass)

Fees can be auto-filled from Kursfinder data (by chamber + trade) or entered
manually. Combo courses are automatically preferred when all their parts are
selected; the "Einzelne Kursteile bevorzugen" option forces individual part
fees where available. Generic Part III/IV courses are automatically included
when a trade is selected.

Source: BMBFSFJ — www.aufstiegs-bafoeg.de (Stand: 03. Juni 2026).

---

## Roadmap

### Completed
- [x] All four RLP chambers scraped and live
- [x] HWK des Saarlandes scraped and live (incl. multi-run date parsing)
- [x] Exam fees with qualifier, range display and tooltips
- [x] Filterable course list + interactive map
- [x] Availability: Freie Plätze / Warteliste / Ausgebucht
- [x] Default future-only view; past courses visible via date filter
- [x] Responsive design (desktop, tablet, mobile)
- [x] AFBG-Rechner with Meisterprojekt support and combo deduplication
- [x] AFBG-Rechner "Einzelne Kursteile bevorzugen" option
- [x] Tab navigation + Impressum (DDG § 5) with Datenschutzerklärung
- [x] Automatic stale-date cleanup after each scrape
- [x] Laufzeit column (start + end date combined)

### Planned
- [ ] GitHub Actions cron job + Render/Neon deployment
- [ ] Berufenet links per trade (field already in model)
- [ ] Nationwide expansion (~53 HWK chambers)