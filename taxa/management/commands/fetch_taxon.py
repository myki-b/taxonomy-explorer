import requests

from django.core.management.base import BaseCommand, CommandError

from taxa.models import Taxon

# GBIF's "match" endpoint takes a name and returns the best-matching taxon
# along with its full classification (kingdom -> species).
GBIF_MATCH_URL = "https://api.gbif.org/v1/species/match"

# The GBIF ranks we care about, ordered from broadest to most specific.
# We build the tree in this order so each taxon's parent already exists
# by the time we create the taxon itself.
HIERARCHY = ["kingdom", "phylum", "class", "order", "family", "genus", "species"]


class Command(BaseCommand):
    help = "Fetch a taxon (and its classification) from GBIF and cache it in the database"

    def add_arguments(self, parser):
        parser.add_argument("name", type=str, help="Scientific name, e.g. 'Vulpes vulpes'")

    def handle(self, *args, **options):
        name = options["name"]

        # --- 1. Call the external API -------------------------------------
        try:
            response = requests.get(GBIF_MATCH_URL, params={"name": name}, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            # Turn any network/HTTP error into a clean Django command error
            # instead of a raw traceback.
            raise CommandError(f"Could not reach GBIF: {exc}")

        data = response.json()

        # GBIF returns matchType "NONE" when it can't find the name.
        if data.get("matchType") == "NONE":
            raise CommandError(f"GBIF found no match for '{name}'.")

        # --- 2. Walk the classification, creating/linking each level ------
        parent = None  # the previous (broader) taxon becomes this one's parent
        created_names = []

        for rank in HIERARCHY:
            # GBIF gives us the name of each level under a key matching the rank,
            # e.g. data["family"] == "Canidae". Skip levels this record doesn't have.
            rank_name = data.get(rank)
            if not rank_name:
                continue

            taxon, created = Taxon.objects.get_or_create(
                name=rank_name,
                rank=rank,
                defaults={"parent": parent},
            )

            # If the taxon already existed but had no parent recorded, backfill it.
            if not created and taxon.parent is None and parent is not None:
                taxon.parent = parent
                taxon.save()

            if created:
                created_names.append(f"{rank_name} ({rank})")

            # This taxon becomes the parent of the next, more specific one.
            parent = taxon

        # --- 3. Report what happened --------------------------------------
        if created_names:
            self.stdout.write(self.style.SUCCESS(
                "Created: " + ", ".join(created_names)
            ))
        else:
            self.stdout.write(self.style.WARNING(
                "Nothing new created — every taxon in this classification was already cached."
            ))
