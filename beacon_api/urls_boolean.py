"""
URL configuration for boolean-only Beacon API
Minimal endpoints for public discovery
"""
from django.urls import path
from . import views_boolean

urlpatterns = [
    # Core endpoints
    path('', views_boolean.beacon_info_boolean, name='beacon-info'),
    path('info', views_boolean.beacon_info_boolean, name='beacon-service-info'),

    # Query endpoints - Boolean only
    path('query/variants', views_boolean.variant_query_boolean, name='variant-query'),
    path('g_variants', views_boolean.variant_query_boolean, name='g-variants'),
    path('query/individuals', views_boolean.individual_query_boolean, name='individual-query'),

    # Catalog metadata (safe for public Boolean mode)
    path('datasets', views_boolean.datasets_boolean, name='datasets'),
    path('cohorts', views_boolean.cohorts_list_boolean, name='cohorts'),
    path('cohorts/<str:cohort_id>', views_boolean.cohort_detail_boolean, name='cohort-detail'),
    path('filtering_terms', views_boolean.filtering_terms_list_boolean, name='filtering-terms'),

    # Participant-level endpoints (individuals, biosamples, analyses)
    # are restricted to Secure mode only — see beacon_api/urls.py

    # Health check
    path('health', views_boolean.health_check, name='health-check'),
]
