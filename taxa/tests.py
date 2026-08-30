from django.test import TestCase
from django.urls import reverse

from .models import Taxon


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
