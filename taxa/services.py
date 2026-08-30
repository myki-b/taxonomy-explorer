"""Talking to GBIF and caching the results.

Kept separate from views and management commands so both can share exactly
the same fetch-and-cache logic.
"""
import requests

from .models import Taxon

# GBIF's "match" endpoint takes a name and returns the best-matching taxon
# along with its full classification (kingdom -> species).
GBIF_MATCH_URL = "https://api.gbif.org/v1/species/match"

# The GBIF ranks we care about, ordered from broadest to most specific, so
# each taxon's parent already exists by the time we create the taxon itself.
HIERARCHY = ["kingdom", "phylum", "class", "order", "family", "genus", "species"]


class GBIFError(Exception):
    """Raised when GBIF can't be reached or returns an unusable response."""


def fetch_and_cache_taxon(name):
    """Fetch ``name`` from GBIF and cache it and its lineage in the database.

    Returns the most specific matched Taxon, or ``None`` if GBIF has no match.
    Raises ``GBIFError`` on a network/HTTP failure.
    """
    try:
        response = requests.get(GBIF_MATCH_URL, params={"name": name}, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise GBIFError(f"Could not reach GBIF: {exc}")

    data = response.json()

    if data.get("matchType") == "NONE":
        return None

    parent = None            # the previous (broader) taxon becomes this one's parent
    most_specific = None     # the deepest taxon we create — what we return

    for rank in HIERARCHY:
        rank_name = data.get(rank)
        if not rank_name:
            continue

        taxon, created = Taxon.objects.get_or_create(
            name=rank_name,
            rank=rank,
            defaults={"parent": parent},
        )

        # Backfill a parent onto a taxon that was cached earlier without one.
        if not created and taxon.parent is None and parent is not None:
            taxon.parent = parent
            taxon.save()

        parent = taxon
        most_specific = taxon

    return most_specific
