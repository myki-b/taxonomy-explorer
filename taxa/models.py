from django.db import models

# Create your models here.
class Taxon(models.Model):
    RANK_CHOICES = [
        ('domain', 'Domain'),
        ('kingdom', 'Kingdom'),
        ('phylum', 'Phylum'),
        ('class', 'Class'),
        ('order', 'Order'),
        ('family', 'Family'),
        ('genus', 'Genus'),
        ('species', 'Species'),
    ]

    name = models.CharField(max_length=200)
    rank = models.CharField(max_length=20, choices=RANK_CHOICES)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children')

    # Enrichment fetched from Wikipedia and cached. Blank when unavailable.
    common_name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    wikipedia_url = models.URLField(blank=True)

    def __str__(self):
        return self.name

    def get_ancestors(self):
        """Return this taxon's ancestors, ordered from the root down to the
        immediate parent (this taxon itself is not included)."""
        ancestors = []
        node = self.parent
        while node is not None:
            ancestors.append(node)
            node = node.parent
        ancestors.reverse()  # collected child->root, so flip to root->parent
        return ancestors