from django.urls import path
from . import views

urlpatterns = [
    path('', views.taxon_list, name='taxon_list'),
    path('<int:pk>/', views.taxon_detail, name='taxon_detail'),
]