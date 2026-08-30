from django.shortcuts import render, get_object_or_404, redirect

from .models import Taxon
from .services import GBIFError, fetch_and_cache_taxon


def taxon_list(request):
    taxons = Taxon.objects.all()
    return render(request, 'taxa/taxon_list.html', {'taxons': taxons})


def taxon_detail(request, pk):
    taxon = get_object_or_404(Taxon, pk=pk)
    return render(request, 'taxa/taxon_detail.html', {'taxon': taxon})


def taxon_search(request):
    query = request.GET.get('q', '').strip()
    results = []
    error = None

    if query:
        # 1. Look in the cache (the local database) first.
        results = list(Taxon.objects.filter(name__icontains=query))

        # 2. On a cache miss, ask GBIF, store the result, and jump to it.
        if not results:
            try:
                taxon = fetch_and_cache_taxon(query)
            except GBIFError as exc:
                error = str(exc)
            else:
                if taxon is not None:
                    return redirect('taxon_detail', pk=taxon.pk)

    return render(request, 'taxa/search.html', {
        'query': query,
        'results': results,
        'error': error,
    })
