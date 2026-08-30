from django.core.management.base import BaseCommand, CommandError

from taxa.models import Taxon
from taxa.services import GBIFError, fetch_and_cache_taxon


class Command(BaseCommand):
    help = "Fetch a taxon (and its classification) from GBIF and cache it in the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "name",
            type=str,
            nargs="?",
            help="Scientific or common name, e.g. 'Vulpes vulpes'. Omit when using --all.",
        )
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Re-fetch enrichment for taxa that are already cached.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Refresh every taxon already in the database (implies --refresh).",
        )

    def handle(self, *args, **options):
        if options["all"]:
            self.refresh_all()
            return

        name = options["name"]
        if not name:
            raise CommandError("Provide a name, or use --all to refresh everything.")

        try:
            taxon = fetch_and_cache_taxon(name, refresh=options["refresh"])
        except GBIFError as exc:
            raise CommandError(str(exc))

        if taxon is None:
            raise CommandError(f"GBIF found no match for '{name}'.")

        self.stdout.write(self.style.SUCCESS(
            f"Cached '{taxon.name}' ({taxon.get_rank_display()}) and its lineage."
        ))

    def refresh_all(self):
        """Re-fetch enrichment for every taxon already in the database."""
        names = list(Taxon.objects.values_list("name", flat=True))
        if not names:
            self.stdout.write(self.style.WARNING("Nothing cached yet — nothing to refresh."))
            return

        for name in names:
            try:
                fetch_and_cache_taxon(name, refresh=True)
            except GBIFError as exc:
                self.stdout.write(self.style.ERROR(f"{name}: {exc}"))
            else:
                self.stdout.write(f"Refreshed {name}")

        self.stdout.write(self.style.SUCCESS(f"Refreshed {len(names)} taxa."))
