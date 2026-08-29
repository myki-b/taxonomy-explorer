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

    def __str__(self):
        return self.name