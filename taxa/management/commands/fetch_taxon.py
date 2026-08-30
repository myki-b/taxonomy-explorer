from django.core.management.base import BaseCommand, CommandError

from taxa.services import GBIFError, fetch_and_cache_taxon


class Command(BaseCommand):
    help = "Fetch a taxon (and its classification) from GBIF and cache it in the database"

    def add_arguments(self, parser):
        parser.add_argument("name", type=str, help="Scientific name, e.g. 'Vulpes vulpes'")

    def handle(self, *args, **options):
        name = options["name"]

        try:
            taxon = fetch_and_cache_taxon(name)
        except GBIFError as exc:
            raise CommandError(str(exc))

        if taxon is None:
            raise CommandError(f"GBIF found no match for '{name}'.")

        self.stdout.write(self.style.SUCCESS(
            f"Cached '{taxon.name}' ({taxon.get_rank_display()}) and its lineage."
        ))
