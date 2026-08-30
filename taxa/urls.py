from django.urls import path
from . import views

urlpatterns = [
    path('', views.taxon_list, name='taxon_list'),
    path('search/', views.taxon_search, name='taxon_search'),
    path('<int:pk>/', views.taxon_detail, name='taxon_detail'),
]