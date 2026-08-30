# 🧬 Taxonomy Explorer

A small Django application for browsing the biological classification of species.
Taxonomy data is fetched on demand from the [GBIF](https://www.gbif.org/) API and
cached in the local database, so each species' full lineage (kingdom → species)
is stored once and then browsable without spamming GBIF.

## Features

- Browse all cached taxa and drill into any one of them.
- Each taxon's page shows a **breadcrumb trail** of its full ancestry and a list of
  its immediate children, so the classification tree is navigable in both directions.
- A management command fetches a species from GBIF and builds its whole lineage,
  reusing any ancestors already in the database.

## Tech stack

- **Python 3.12** / **Django 6.1**
- **SQLite** (default dev database)
- **requests** for the GBIF API calls
- **python-dotenv** for environment-based configuration

## Getting started

```bash
# 1. Clone and enter the project
git clone https://github.com/myki-b/taxonomy-explorer.git
cd taxonomy-explorer

# 2. Create and activate a virtual environment
python -m venv venv
source venv/Scripts/activate        # Windows (Git Bash)
# source venv/bin/activate          # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure secrets
cp .env.example .env                # then set DJANGO_SECRET_KEY in .env

# 5. Set up the database
python manage.py migrate

# 6. Fetch some data
python manage.py fetch_taxon "Vulpes vulpes"
python manage.py fetch_taxon "Canis lupus"   # reuses the shared ancestors

# 7. Run the server
python manage.py runserver
```

Then open <http://127.0.0.1:8000/>.

## Fetching data

The `fetch_taxon` management command takes a scientific name, matches it against
GBIF, and stores the taxon along with every rank in its classification:

```bash
python manage.py fetch_taxon "Panthera leo"
```

Running it a second time creates nothing new — existing taxa are served from the
cache rather than re-fetched.

## Design decisions

A few choices worth calling out:

- **API results are cached in the DB via `get_or_create`.** The lookup matches on
  `name` + `rank`, so importing a second species in the same family reuses the
  existing ancestors instead of duplicating them. This is the caching requirement
  at the heart of the project.
- **Fetching lives in a management command, not a view.** Talking to a third-party
  API on every page load would be slow and fragile; a command is the idiomatic
  place for deliberate, batch-style data loading.
- **Ancestry logic lives on the model** (`Taxon.get_ancestors`), keeping views thin
  and the behaviour reusable across views, templates, and the shell.
- **Configuration comes from the environment.** The secret key is read from a
  `.env` file (git-ignored) rather than hard-coded, with a committed `.env.example`
  documenting what is required.

## Known limitations

- There is currently no way to track stale records - a new API request is never made
  for a record that exists within the DB.

## Next steps

- `get_ancestors()` walks the parent chain one query per level.
  Fine for shallow trees; a larger dataset would call for a dedicated tree library
  (e.g. `django-mptt`) or a recursive query.
- No search yet — species are added via the fetch command and browsed by hand.

## Running the tests

```bash
python manage.py test
```
