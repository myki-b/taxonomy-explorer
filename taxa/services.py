"""Talking to GBIF and Wikipedia, and caching the results.

Kept separate from views and management commands so both can share exactly
the same fetch-and-cache logic.
"""
import urllib.parse

import requests

from .models import Taxon

# GBIF's "match" endpoint takes a name and returns the best-matching taxon
# along with its full classification (kingdom -> species). It only understands
# scientific names, so common names have to be resolved first (see below).
GBIF_MATCH_URL = "https://api.gbif.org/v1/species/match"
# GBIF's full-text search can be pointed at vernacular (everyday) names.
GBIF_SEARCH_URL = "https://api.gbif.org/v1/species/search"

# Wikipedia's REST API returns a JSON summary (extract + thumbnail) for a title.
WIKIPEDIA_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/"
# The MediaWiki and Wikidata APIs let us turn an article title into its
# Wikidata item, and that item's "taxon name" (P225) into a scientific name.
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
WIKIDATA_TAXON_NAME_PROPERTY = "P225"
# Wikipedia asks all API clients to identify themselves with a User-Agent.
WIKIPEDIA_HEADERS = {"User-Agent": "TaxonomyExplorer/1.0 (portfolio project)"}

# The GBIF ranks we care about, ordered from broadest to most specific, so
# each taxon's parent already exists by the time we create the taxon itself.
HIERARCHY = ["kingdom", "phylum", "class", "order", "family", "genus", "species"]


class GBIFError(Exception):
    """Raised when GBIF can't be reached or returns an unusable response."""


def _scientific_name_from_gbif_vernacular(name):
    """Resolve a common name to a scientific name using GBIF's vernacular index.

    GBIF's search is fuzzy, so we only trust a result that actually lists the
    query as one of its vernacular names — otherwise "lion" happily matches
    a lizard called *Anolis lionotus*.
    """
    try:
        response = requests.get(
            GBIF_SEARCH_URL,
            params={
                "q": name,
                "qField": "VERNACULAR",
                "rank": "SPECIES",
                "status": "ACCEPTED",
                "limit": 20,
            },
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None

    wanted = name.strip().lower()
    for result in response.json().get("results", []):
        vernaculars = {
            (v.get("vernacularName") or "").lower()
            for v in (result.get("vernacularNames") or [])
        }
        if wanted in vernaculars and result.get("canonicalName"):
            return result["canonicalName"]
    return None


def _scientific_name_from_wikidata(name):
    """Resolve a common name to a scientific name via Wikipedia and Wikidata.

    Looks up the article for ``name``, follows it to its Wikidata item, and
    reads that item's "taxon name" (P225) property. This catches everyday
    single-word names such as "tiger" that GBIF's vernacular index misses.
    """
    try:
        page_response = requests.get(
            WIKIPEDIA_API_URL,
            params={
                "action": "query",
                "titles": name.replace(" ", "_"),
                "prop": "pageprops",
                "redirects": 1,
                "format": "json",
            },
            headers=WIKIPEDIA_HEADERS,
            timeout=10,
        )
        page_response.raise_for_status()

        pages = page_response.json().get("query", {}).get("pages", {})
        item_id = None
        for page in pages.values():
            item_id = (page.get("pageprops") or {}).get("wikibase_item")
            break
        if not item_id:
            return None

        claim_response = requests.get(
            WIKIDATA_API_URL,
            params={
                "action": "wbgetclaims",
                "entity": item_id,
                "property": WIKIDATA_TAXON_NAME_PROPERTY,
                "format": "json",
            },
            headers=WIKIPEDIA_HEADERS,
            timeout=10,
        )
        claim_response.raise_for_status()
        claims = claim_response.json().get("claims", {}).get(WIKIDATA_TAXON_NAME_PROPERTY)
    except (requests.RequestException, ValueError):
        return None

    if not claims:
        return None

    try:
        return claims[0]["mainsnak"]["datavalue"]["value"]
    except (KeyError, IndexError, TypeError):
        return None


def fetch_wikipedia_summary(name):
    """Return {description, image_url, wikipedia_url} for ``name`` from Wikipedia.

    Returns ``None`` if there's no usable article. Wikipedia enrichment is a
    "nice to have", so any failure here is swallowed rather than raised — it
    must never break the core GBIF caching.
    """
    title = urllib.parse.quote(name.replace(" ", "_"))
    try:
        response = requests.get(
            WIKIPEDIA_SUMMARY_URL + title,
            headers=WIKIPEDIA_HEADERS,
            timeout=10,
        )
    except requests.RequestException:
        return None

    if response.status_code != 200:
        return None

    data = response.json()

    # Disambiguation pages aren't real articles — skip them.
    if data.get("type") == "disambiguation":
        return None

    return {
        # extract_html keeps Wikipedia's formatting (e.g. italic scientific names).
        "description": data.get("extract_html", ""),
        # The article title is the everyday name, e.g. "Red fox" for Vulpes vulpes.
        "common_name": data.get("title", ""),
        "image_url": (data.get("thumbnail") or {}).get("source", ""),
        "wikipedia_url": (data.get("content_urls", {}).get("desktop", {}) or {}).get("page", ""),
    }


def _gbif_match(name):
    """Return GBIF's classification for a scientific ``name``, or None."""
    try:
        response = requests.get(GBIF_MATCH_URL, params={"name": name}, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise GBIFError(f"Could not reach GBIF: {exc}")

    data = response.json()
    return None if data.get("matchType") == "NONE" else data


def fetch_and_cache_taxon(name, refresh=False):
    """Fetch ``name`` from GBIF and cache it and its lineage in the database.

    ``name`` may be a scientific name ("Vulpes vulpes") or an everyday one
    ("red fox"); common names are resolved to a scientific name first.

    Returns the most specific matched Taxon, or ``None`` if nothing matched.
    Raises ``GBIFError`` on a network/HTTP failure talking to GBIF.

    Pass ``refresh=True`` to re-fetch the Wikipedia enrichment for taxa that
    are already cached, overwriting whatever is stored.
    """
    # Stage 1: assume a scientific name — the common case, and one API call.
    data = _gbif_match(name)

    # Stages 2 and 3: it wasn't a scientific name, so try to resolve the
    # common name, then match again on whatever we resolved it to.
    if data is None:
        scientific_name = (
            _scientific_name_from_gbif_vernacular(name)
            or _scientific_name_from_wikidata(name)
        )
        if scientific_name:
            data = _gbif_match(scientific_name)

    if data is None:
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
        changed = False

        # Backfill a parent onto a taxon that was cached earlier without one.
        if not created and taxon.parent is None and parent is not None:
            taxon.parent = parent
            changed = True

        # Enrich from Wikipedia only if we haven't already got anything
        # (or if the caller explicitly asked for fresh data).
        if refresh or (not taxon.description and not taxon.image_url):
            summary = fetch_wikipedia_summary(rank_name)
            if summary:
                taxon.description = summary["description"]
                # Only store the common name when it differs from the scientific
                # name, so we don't label "Vulpes" as its own common name.
                if summary["common_name"].lower() != taxon.name.lower():
                    taxon.common_name = summary["common_name"]
                taxon.image_url = summary["image_url"]
                taxon.wikipedia_url = summary["wikipedia_url"]
                changed = True

        if changed:
            taxon.save()

        parent = taxon
        most_specific = taxon

    return most_specific
