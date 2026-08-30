from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .models import Taxon
from .services import fetch_and_cache_taxon


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
