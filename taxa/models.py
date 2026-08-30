from datetime import date

from django.db import models

# Create your models here.
class Taxon(models.Model):
    RANK_CHOICES = [
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
    @classmethod
    def spotlight(cls, today=None):
        """Return the spotlight taxon, chosen deterministically from the date.

        The same date and the same set of cached species always yield the same
        taxon, and the choice moves on at midnight, without storing anything or
        running a scheduled job. Note that the pick is an index into the cached
        species, so caching new species can also change it. Species with a
        description are preferred so the spotlight card has something to show.

        ``today`` can be passed in to make the choice testable.
        """
        candidates = cls.objects.filter(rank='species').exclude(description='')
        if not candidates.exists():
            candidates = cls.objects.all()

        count = candidates.count()
        if not count:
            return None

        # toordinal() increases by exactly one per day, so the index advances
        # predictably and wraps around the available taxa.
        day_number = (today or date.today()).toordinal()
        return candidates.order_by('pk')[day_number % count]
