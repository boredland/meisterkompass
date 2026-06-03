# MeisterKompass

An independent, non-commercial comparison platform for Meister preparation
courses offered by Handwerkskammern (HWK) in Germany.

Enables direct comparison of prices, duration, and exam fees across chambers,
as well as calculation of AFBG (Aufstiegs-BAföG) funding.

Initial scope: four chambers in Rhineland-Palatinate (Koblenz, Pfalz,
Rheinhessen, Trier). Designed to scale to all chambers nationwide.

**Currently live:** HWK Koblenz, HWK Trier, HWK Pfalz, HWK Rheinhessen.

---

## Features

- Filterable course listings per trade, chamber, format, and exam part
- Multi-part filter with optional "include combination courses" toggle
- "Plätze verfügbar" toggle to filter for courses with open spots
- Default view shows only upcoming courses; past courses visible via date filter
- Course fees and examination fees displayed side by side (no decimal places)
- "bis zu" qualifier and fee ranges for maximum-fee entries (e.g. HWK Koblenz)
- ⓘ tooltip explaining the source of exam fee data
- Interactive map with geocoded course location pins (Leaflet + CartoDB)
- Automatic price/fee propagation from nearest available course
- "Termine nicht verfügbar" indicator for courses without scheduled dates
- Responsive design for desktop, tablet, and mobile
- Tab navigation: Kursfinder, AFBG-Rechner, Über MeisterKompass, Impressum
- AFBG-Rechner: calculates Aufstiegs-BAföG funding for course fees and
  Meisterprojekt costs, with auto-fill from Kursfinder data
- Django admin for manual data entry and exam fee verification
- Weekly automated data updates via GitHub Actions

---

## Tech Stack

| Layer       | Technology                                      |
|-------------|-------------------------------------------------|
| Backend     | Django 6.x                                      |
| Database    | SQLite (dev) / PostgreSQL via Neon (prod)        |
| Scraping    | requests + BeautifulSoup                        |
| Frontend    | Django Templates + Leaflet.js                   |
| Map tiles   | CartoDB (no API key required)                   |
| Geocoding   | Nominatim / OpenStreetMap (no API key required) |
| Hosting     | Render (web app) + Neon (database)              |
| Cron        | GitHub Actions (every Friday 03:00 UTC)         |

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
python manage.py run_scrapers --chamber hwk-koblenz --dry-run
python manage.py geocode_offers
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
| `exam_fee_scraped` | Exam fee from the course page (HWK Trier, HWK Pfalz)             |
| `city`             | City for map pin                                                  |
| `source_url`       | Direct link to the course page on the chamber website             |

`start_date = None` → "Termine nicht verfügbar".
Past courses are retained in the DB and visible when a past date filter is applied.

### ExamFee

| Chamber     | Source                                    | Notes                     |
|-------------|-------------------------------------------|---------------------------|
| Trier       | Scraped from course detail pages          | Exact values              |
| Pfalz       | Scraped from course detail pages          | Exact values              |
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
manually. Generic Part III/IV courses are automatically included when a trade
is selected. Source: BMBF / AFBG — www.aufstiegs-bafoeg.de (Stand: Juni 2026).

---

## Roadmap

### Completed
- [x] All four RLP chambers scraped and live
- [x] Exam fees with qualifier, range display and tooltips
- [x] Filterable course list + interactive map
- [x] "Plätze verfügbar" availability filter
- [x] Default future-only view; past courses visible via date filter
- [x] Responsive design (desktop, tablet, mobile)
- [x] AFBG-Rechner with Meisterprojekt support
- [x] Tab navigation + Impressum with Haftungsausschluss

### Planned
- [ ] GitHub Actions cron job + Render/Neon deployment
- [ ] Berufenet links per trade (field already in model)
- [ ] Nationwide expansion (~53 HWK chambers)