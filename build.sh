#!/usr/bin/env bash
# build.sh — Render build script
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# Create superuser if DJANGO_SUPERUSER_USERNAME is set.
# Fails silently if the user already exists.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  python manage.py createsuperuser --noinput || true
fi

# Fix HWK Saarland coordinates after every deploy
python manage.py shell -c "
from courses.models import CourseOffer
from chambers.models import Chamber
try:
    c = Chamber.objects.get(slug='hwk-saarland')
    n = CourseOffer.objects.filter(chamber=c, is_active=True).update(latitude=49.2297, longitude=6.9967)
    print(f'Saarland coordinates fixed: {n} records')
except Exception as e:
    print(f'Coordinate fix skipped: {e}')
"