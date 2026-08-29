from django.shortcuts import render, get_object_or_404
from .models import Taxon

def taxon_list(request):
    taxons = Taxon.objects.all()
    return render(request, 'taxa/taxon_list.html', {'taxons': taxons})

def taxon_detail(request, pk):
    taxon = get_object_or_404(Taxon, pk=pk)
    return render(request, 'taxa/taxon_detail.html', {'taxon': taxon})