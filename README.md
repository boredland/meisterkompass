# MeisterVergleich

A comparison platform for Meister preparation courses offered by
Handwerkskammern (HWK) in Germany.

The scraper enables direct comparison of prices, duration, and exam fees,
as well as statistical analysis of the Meister education landscape.

Initial scope: four chambers in Rhineland-Palatinate (Koblenz, Pfalz,
Rheinhessen, Trier). Designed to scale to all chambers nationwide.

**Currently live:** HWK Koblenz, HWK Trier, HWK Pfalz, HWK Rheinhessen.

---

## Features

- Filterable course listings per trade, chamber, format, and exam part
- Multi-part filter with optional "include combination courses" toggle
- Course fees and examination fees displayed side by side
- "bis zu" qualifier for maximum-fee entries (e.g. HWK Koblenz)
- Interactive map with geocoded course location pins (Leaflet + OpenStreetMap)
- Automatic price/fee propagation from nearest dated course when missing
- "Termine nicht verfügbar" indicator for courses without scheduled dates
- Tab navigation: Kursfinder, Über MeisterVergleich, Zahlen zum Meister, Impressum
- Django admin for manual data entry and exam fee verification
- Weekly automated data updates via GitHub Actions

---

## Tech Stack

| Layer       | Technology                                      |
|-------------|-------------------------------------------------|
| Backend     | Django 6.x                                      |
| Database    | SQLite (dev) / PostgreSQL via Neon (prod)        |
| Scraping    | requests + BeautifulSoup (Playwright optional)  |
| Frontend    | Django Templates + Leaflet.js                   |
| Geocoding   | Nominatim / OpenStreetMap (no API key required) |
| Hosting     | Render (web app) + Neon (database)              |
| Cron        | GitHub Actions (every Friday 03:00 UTC)         |

---

## Project Structure

```
meistervergleich/
├── config/                   # Django project settings, URLs, WSGI
├── chambers/                 # Chamber and Trade models + admin
├── courses/                  # CourseOffer, ExamFee models + admin
│   ├── calculators.py        # Total cost calculation logic
│   └── views.py              # Course listing view with filters
├── scraper/                  # Scraper pipeline
│   ├── base.py               # Abstract base scraper + RawCourseOffer + build_course_title
│   ├── hwk_koblenz.py        # HWK Koblenz scraper ✓
│   ├── hwk_trier.py          # HWK Trier scraper ✓  (incl. exam fees)
│   ├── hwk_pfalz.py          # HWK Pfalz scraper ✓  (incl. exam fees)
│   ├── hwk_rheinhessen.py    # HWK Rheinhessen scraper ✓
│   └── management/
│       └── commands/
│           ├── run_scrapers.py    # python manage.py run_scrapers
│           └── geocode_offers.py  # python manage.py geocode_offers
├── templates/
│   ├── base.html             # Tab navigation, shared styles
│   ├── courses/
│   │   └── list.html         # Kursfinder (filterable list + map)
│   └── pages/
│       ├── about.html        # Über MeisterVergleich
│       ├── stat.html         # Zahlen zum Meister (statistics, planned)
│       └── imprint.html      # Impressum
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

pip install django dj-database-url python-decouple ^
  requests beautifulsoup4
```

### .env file

Create a `.env` file in the project root:

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

Admin interface: http://127.0.0.1:8000/admin/

---

## Data Model Overview

```
Chamber ──┐
          ├── CourseOffer   (one row per course listing on the chamber website)
Trade   ──┘
          └── ExamFee       (official exam fee per part, chamber and trade)
```

### CourseOffer

Each `CourseOffer` corresponds exactly to one listing on the chamber's website,
including its specific start date, price, location, and availability.

| Field              | Description                                                       |
|--------------------|-------------------------------------------------------------------|
| `title`            | Normalised title, e.g. "Metallbauer (Teile I + II)"              |
| `has_part_1..4`    | Which exam parts this course covers                               |
| `format`           | Vollzeit / Teilzeit                                               |
| `teaching_mode`    | Präsenz / Online / Hybrid (defaults to Präsenz)                   |
| `course_fee`       | Course fee in EUR                                                 |
| `exam_fee_scraped` | Exam fee from the course page (HWK Trier, HWK Pfalz)             |
| `city`             | City for map pin (full address can be added later)                |
| `source_url`       | Direct link to the course page on the chamber website             |

`start_date = None` indicates "Termine nicht verfügbar" — price is known but
no course dates have been announced yet (e.g. some HWK Rheinhessen trades).

### Exam parts

| Part | Content                        | Trade-specific? |
|------|--------------------------------|-----------------|
| I    | Fachpraxis (practical)         | Yes             |
| II   | Fachtheorie (theory)           | Yes             |
| III  | Wirtschaft und Recht           | No              |
| IV   | Berufs- und Arbeitspädagogik   | No              |

### ExamFee

Authoritative per-part exam fees used by the total-cost calculator.

| Chamber     | Source                                         |
|-------------|------------------------------------------------|
| Trier       | Scraped directly from course detail pages      |
| Pfalz       | Scraped directly from course detail pages      |
| Koblenz     | Manual entry from PDF Gebührenverzeichnis      |
| Rheinhessen | Manual entry (exam fee pages per trade)        |

The `fee_qualifier` field (e.g. "bis zu") is displayed before the fee amount
where the source states a maximum rather than a fixed fee (HWK Koblenz).

To protect a manually entered fee from being overwritten by the scraper,
set `scraper_may_overwrite = False` and `manually_verified = True` in admin.

---

## Running the Scrapers

```bat
# Run all scrapers
python manage.py run_scrapers

# Run a single chamber
python manage.py run_scrapers --chamber hwk-koblenz
python manage.py run_scrapers --chamber hwk-trier
python manage.py run_scrapers --chamber hwk-pfalz
python manage.py run_scrapers --chamber hwk-rheinhessen

# Dry run (parse and print without writing to DB)
python manage.py run_scrapers --chamber hwk-koblenz --dry-run

# Geocode course locations (city -> coordinates via Nominatim/OSM)
python manage.py geocode_offers
```

---

## Weekly Scraper (Production)

The scraper runs every Friday at 03:00 UTC via GitHub Actions
(`.github/workflows/weekly_scraper.yml`).
To trigger manually: GitHub -> Actions -> "Weekly Scraper" -> Run workflow.

---

## Trade Name Normalisation

Each scraper maps chamber-specific trade name variants to a shared canonical
name so that the same trade from different chambers is stored as one `Trade`
record. Mappings are defined in `TRADE_ALIASES` in each scraper file.

Example (`hwk_trier.py`):
```python
"Friseure":               "Friseur",
"KFZ-Techniker":          "Kfz.-Techniker",
"Kraftfahrzeugtechniker": "Kfz.-Techniker",
```

---

## Roadmap

### Completed
- [x] Django project structure and data model
- [x] Django admin with exam fee verification and "bis zu" qualifier
- [x] HWK Koblenz scraper (~110 courses)
- [x] HWK Trier scraper (22 courses, incl. exam fees)
- [x] HWK Pfalz scraper (32 courses, incl. exam fees)
- [x] HWK Rheinhessen scraper (24+ courses, WordPress-based)
- [x] Course listing frontend with filters
      (chamber, trade, format, teaching mode, parts, date range, per-page)
- [x] Tab navigation (Kursfinder, Über, Zahlen, Impressum)
- [x] Interactive Leaflet map with geocoded location pins
- [x] Trade name normalisation across chambers
- [x] Missing price propagation from nearest dated course
- [x] "Termine nicht verfügbar" for courses without scheduled dates

### In Progress / Planned
- [ ] Exam fees for HWK Koblenz (manual entry from Gebührenverzeichnis)
- [ ] Exam fees for HWK Rheinhessen (manual entry per trade)
- [ ] Total cost comparison view (all four parts combined)
- [ ] Statistics page (Zahlen zum Meister)
- [ ] GitHub Actions cron job setup
- [ ] Render + Neon deployment
- [ ] AFBG / Meister-BAföG funding calculator
- [ ] Berufenet links per trade (field already in model)
- [ ] Nationwide expansion (~53 HWK chambers)