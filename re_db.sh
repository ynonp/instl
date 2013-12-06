export DJANGO_SETTINGS_MODULE="djinstl.settings"

rm db.sqlite3

python manage.py syncdb --noinput

python load_index_data.py
