from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Taxon
from .services import GBIFError, fetch_and_cache_taxon


class TaxonModelTests(TestCase):
    def test_get_ancestors_returns_root_to_parent_in_order(self):
        kingdom = Taxon.objects.create(name="Animalia", rank="kingdom")
        phylum = Taxon.objects.create(name="Chordata", rank="phylum", parent=kingdom)
        species = Taxon.objects.create(name="Vulpes vulpes", rank="species", parent=phylum)

        ancestors = species.get_ancestors()

        # Ordered from the root down to the immediate parent, excluding self.
        self.assertEqual(ancestors, [kingdom, phylum])

    def test_root_taxon_has_no_ancestors(self):
        root = Taxon.objects.create(name="Animalia", rank="kingdom")
        self.assertEqual(root.get_ancestors(), [])


class TaxonSpotlightTests(TestCase):
    def setUp(self):
        for name in ["Vulpes vulpes", "Panthera leo", "Ursus maritimus"]:
            Taxon.objects.create(name=name, rank="species", description="<p>A species.</p>")

    def test_same_date_always_gives_the_same_taxon(self):
        first = Taxon.spotlight(today=date(2026, 8, 30))
        second = Taxon.spotlight(today=date(2026, 8, 30))
        self.assertEqual(first, second)

    def test_choice_changes_from_one_day_to_the_next(self):
        picks = {Taxon.spotlight(today=date(2026, 8, d)).pk for d in range(1, 4)}
        # Three consecutive days should cycle through three different taxa.
        self.assertEqual(len(picks), 3)

    def test_prefers_species_that_have_a_description(self):
        Taxon.objects.create(name="Animalia", rank="kingdom")  # no description
        for _ in range(10):
            self.assertNotEqual(Taxon.spotlight(today=date(2026, 8, 30)).name, "Animalia")

    def test_returns_none_when_database_is_empty(self):
        Taxon.objects.all().delete()
        self.assertIsNone(Taxon.spotlight(today=date(2026, 8, 30)))


class HomePageTests(TestCase):
    def test_lists_kingdoms_but_not_deeper_ranks(self):
        Taxon.objects.create(name="Animalia", rank="kingdom")
        Taxon.objects.create(name="Vulpes vulpes", rank="species")

        response = self.client.get(reverse("taxon_list"))

        self.assertContains(response, "Animalia")
        # Species are reachable by drilling down or searching, not listed here.
        self.assertNotContains(response, "Vulpes vulpes")


class TaxonViewTests(TestCase):
    def test_detail_page_shows_taxon_and_breadcrumb(self):
        kingdom = Taxon.objects.create(name="Animalia", rank="kingdom")
        species = Taxon.objects.create(name="Vulpes vulpes", rank="species", parent=kingdom)

        response = self.client.get(reverse("taxon_detail", args=[species.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vulpes vulpes")
        self.assertContains(response, "Animalia")  # the ancestor appears in the breadcrumb

    def test_detail_page_404_for_missing_taxon(self):
        response = self.client.get(reverse("taxon_detail", args=[9999]))
        self.assertEqual(response.status_code, 404)


class CommonNameResolutionTests(TestCase):
    """The service should fall back to common-name lookups when GBIF's
    scientific-name match finds nothing."""

    LINEAGE = {"kingdom": "Animalia", "genus": "Panthera", "species": "Panthera leo"}

    @patch("taxa.services._scientific_name_from_wikidata")
    @patch("taxa.services._scientific_name_from_gbif_vernacular", return_value="Panthera leo")
    @patch("taxa.services.fetch_wikipedia_summary", return_value=None)
    @patch("taxa.services._gbif_match")
    def test_common_name_resolved_via_gbif_vernacular(
        self, mock_match, mock_summary, mock_vernacular, mock_wikidata
    ):
        # First call (the raw query) misses; the second, with the resolved
        # scientific name, succeeds.
        mock_match.side_effect = [None, self.LINEAGE]

        taxon = fetch_and_cache_taxon("lion")

        self.assertEqual(taxon.name, "Panthera leo")
        mock_vernacular.assert_called_once_with("lion")
        # Wikidata is only a last resort, so it should not have been needed.
        mock_wikidata.assert_not_called()

    @patch("taxa.services._scientific_name_from_wikidata", return_value="Panthera tigris")
    @patch("taxa.services._scientific_name_from_gbif_vernacular", return_value=None)
    @patch("taxa.services.fetch_wikipedia_summary", return_value=None)
    @patch("taxa.services._gbif_match")
    def test_falls_back_to_wikidata_when_vernacular_fails(
        self, mock_match, mock_summary, mock_vernacular, mock_wikidata
    ):
        mock_match.side_effect = [None, {"species": "Panthera tigris"}]

        taxon = fetch_and_cache_taxon("tiger")

        self.assertEqual(taxon.name, "Panthera tigris")
        mock_wikidata.assert_called_once_with("tiger")

    @patch("taxa.services._scientific_name_from_wikidata", return_value=None)
    @patch("taxa.services._scientific_name_from_gbif_vernacular", return_value=None)
    @patch("taxa.services._gbif_match", return_value=None)
    def test_returns_none_when_nothing_resolves(self, mock_match, mock_vern, mock_wd):
        self.assertIsNone(fetch_and_cache_taxon("zzznotathing"))


class SeedCommandTests(TestCase):
    """The seed command should drive the shared service and survive failures."""

    @patch("taxa.management.commands.seed_taxa.time.sleep")  # no real waiting
    @patch("taxa.management.commands.seed_taxa.fetch_and_cache_taxon")
    def test_limit_controls_how_many_species_are_fetched(self, mock_fetch, mock_sleep):
        mock_fetch.return_value = Taxon(name="Stub", rank="species")

        call_command("seed_taxa", limit=3, delay=0, stdout=StringIO())

        self.assertEqual(mock_fetch.call_count, 3)

    @patch("taxa.management.commands.seed_taxa.time.sleep")
    @patch("taxa.management.commands.seed_taxa.fetch_and_cache_taxon")
    def test_one_failure_does_not_abort_the_batch(self, mock_fetch, mock_sleep):
        # The first species blows up; the remaining two must still be attempted.
        mock_fetch.side_effect = [
            GBIFError("network down"),
            Taxon(name="Stub", rank="species"),
            None,  # no match
        ]

        out = StringIO()
        call_command("seed_taxa", limit=3, delay=0, stdout=out)

        self.assertEqual(mock_fetch.call_count, 3)
        self.assertIn("2 failed", out.getvalue())

    @patch("taxa.management.commands.seed_taxa.time.sleep")
    @patch("taxa.management.commands.seed_taxa.fetch_and_cache_taxon")
    def test_reads_names_from_a_file(self, mock_fetch, mock_sleep):
        mock_fetch.return_value = Taxon(name="Stub", rank="species")
        path = Path(self.temp_dir.name) / "names.txt"
        path.write_text("Vulpes vulpes\n\nPanthera leo\n", encoding="utf-8")

        call_command("seed_taxa", file=str(path), delay=0, stdout=StringIO())

        # Blank lines are ignored.
        self.assertEqual(
            [call.args[0] for call in mock_fetch.call_args_list],
            ["Vulpes vulpes", "Panthera leo"],
        )

    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)


class TaxonSearchTests(TestCase):
    def test_search_finds_cached_taxon_without_calling_gbif(self):
        Taxon.objects.create(name="Vulpes vulpes", rank="species")

        # patch the service so a cache hit never touches the network.
        with patch("taxa.views.fetch_and_cache_taxon") as mock_fetch:
            response = self.client.get(reverse("taxon_search"), {"q": "Vulpes"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vulpes vulpes")
        mock_fetch.assert_not_called()

    def test_search_matches_common_name(self):
        Taxon.objects.create(name="Vulpes vulpes", rank="species", common_name="Red fox")

        # Searching the everyday name should find the taxon without hitting GBIF.
        with patch("taxa.views.fetch_and_cache_taxon") as mock_fetch:
            response = self.client.get(reverse("taxon_search"), {"q": "red fox"})

        self.assertContains(response, "Vulpes vulpes")
        mock_fetch.assert_not_called()

    def test_search_falls_back_to_gbif_and_redirects_on_miss(self):
        # The query matches nothing cached, so the view should call the service.
        # The service (mocked) "returns" a taxon as if freshly fetched from GBIF.
        fetched = Taxon.objects.create(name="Panthera leo", rank="species")

        with patch("taxa.views.fetch_and_cache_taxon", return_value=fetched) as mock_fetch:
            response = self.client.get(reverse("taxon_search"), {"q": "Lion"})

        mock_fetch.assert_called_once_with("Lion")
        self.assertRedirects(response, reverse("taxon_detail", args=[fetched.pk]))
