# 🧬 Taxonomy Explorer

## What is it?

A small Django application for browsing the biological classification of species.
Taxonomy data is fetched on demand from the [GBIF](https://www.gbif.org/) API and
cached in the local database, so each species' full lineage (kingdom → species)
is stored once and then browsable without spamming GBIF.

This application is not designed to be practically useful in the real world.
There are other services which perform this role to a much better degree.
It is simply an excuse to build a Django application to serve as a learning exercise
and quick portfolio piece.

<img width="802" height="807" alt="image" src="https://github.com/user-attachments/assets/e12c1744-b920-439e-abbd-2f980dba84df" />

## Features

- The home page lists the **kingdoms** to drill down from, rather than every
  cached taxon, so it stays readable as the database grows.
- A **taxon spotlight** on the home page, picked deterministically from the
  current date.
- Each taxon's page shows a **breadcrumb trail** of its full ancestry and a list of
  its immediate children, so the classification tree is navigable in both directions.
- A management command fetches a species from GBIF and builds its whole lineage,
  reusing any ancestors already in the database.
- **Search any species** from the header on every page, by **scientific or common
  name** — "Vulpes vulpes", "red fox", "bald eagle" and "giant panda" all work.
  Cached taxa are matched locally; on a miss the app resolves the name, fetches
  the species from GBIF, caches it, and jumps straight to its page (a cache-aside
  strategy, with the database as the cache).
- Each taxon is **enriched from Wikipedia** with a summary, photo, common name, and
  a link to the full article — also cached, so the API is called once per taxon.

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

# 6. Load the sample data (instant, no network needed)
python manage.py loaddata sample_taxa

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

### Seeding

`seed_taxa` populates the database with a curated list of ~220 species spanning
animals, plants and fungi, including a cluster of domestic and veterinary
species. It pauses between requests to stay within the APIs' rate limits:

```bash
python manage.py seed_taxa                  # the full curated list
python manage.py seed_taxa --limit 10       # a quick trial run
python manage.py seed_taxa --file names.txt # your own list, one name per line
```

A snapshot of the seeded database is committed as a fixture, so a fresh clone
can skip the API calls entirely with `python manage.py loaddata sample_taxa`.

### Refreshing

To deliberately re-fetch data that is already cached:

```bash
python manage.py fetch_taxon "Panthera leo" --refresh   # one lineage
python manage.py fetch_taxon --all                      # everything in the database
```

## Design decisions

- **API results are cached in the DB via `get_or_create`.** The lookup matches on
  `name` + `rank`, so importing a second species in the same family reuses the
  existing ancestors instead of duplicating them. This is the caching requirement
  at the heart of the project.
- **Fetching lives in a management command, not a view.** Talking to a third-party
  API on every page load would be slow and fragile; a command is the idiomatic
  place for deliberate, batch-style data loading.
- **Ancestry logic lives on the model** (`Taxon.get_ancestors`), keeping views thin
  and the behaviour reusable across views, templates, and the shell.
- **The spotlight taxon is derived, not stored.** `Taxon.spotlight()` indexes
  into the cached species using `date.toordinal() % count`, so the choice is
  stable for a whole day and rotates at midnight without a scheduled job or an
  extra table. The date can be injected, which makes it straightforward to test.
- **External API integration lives in a service module** (`taxa/services.py`), so
  the management command and the search view share one copy of the fetch-and-cache
  logic instead of duplicating it.
- **Wikipedia enrichment fails soft.** A missing article or an unreachable
  Wikipedia leaves the taxon without a blurb rather than breaking the request;
  GBIF failures, by contrast, raise, because without them there is nothing to show.
- **Common names are resolved in three escalating stages**, cheapest first, so the
  common case costs a single API call:
  1. treat the query as a scientific name and ask GBIF to match it;
  2. search GBIF's vernacular index, accepting a result only if it genuinely
     lists the query as one of its common names (GBIF's search is fuzzy, and
     "lion" otherwise matches a lizard called *Anolis lionotus*);
  3. fall back to Wikipedia, following the article to its Wikidata item and
     reading the "taxon name" property — this catches everyday single-word
     names such as "tiger" that GBIF's vernacular index misses.
- **Configuration comes from the environment.** The secret key is read from a
  `.env` file (git-ignored) rather than hard-coded, with a committed `.env.example`
  documenting what is required.

## Known limitations

- The spotlight taxon is an index into the cached species, so caching a new
  species can change the pick before midnight - it is stable for a given date
  and dataset, not for a given date alone. Persisting the choice per date would
  make it fully stable, at the cost of an extra table.
- Cached records have no expiry or staleness tracking: a taxon in the database is
  never automatically re-fetched. Refreshing is a manual, explicit action
  (`--refresh` / `--all`). A production version would store a `last_fetched`
  timestamp and treat records older than some TTL as stale.
- Wikipedia's `extract_html` is rendered with Django's `|safe` filter, which turns
  off auto-escaping for that field. This is acceptable because the HTML comes from
  a trusted API returning a small set of formatting tags, but a hardened version
  would sanitise it (e.g. with `bleach`) before storing it, rather than trusting
  the upstream response.

## Running the tests

```bash
python manage.py test
```
