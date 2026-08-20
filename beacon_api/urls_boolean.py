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
    path('service-info', views_boolean.beacon_info_boolean, name='beacon-service-info-alias'),

    # GA4GH Beacon v2 required discovery endpoints
    path('entry_types', views_boolean.beacon_entry_types, name='beacon-entry-types'),
    path('configuration', views_boolean.beacon_configuration, name='beacon-configuration'),
    path('map', views_boolean.beacon_map, name='beacon-map'),

    # Query endpoints - Boolean only
    path('query/variants', views_boolean.variant_query_boolean, name='variant-query'),
    path('g_variants', views_boolean.variant_query_boolean, name='g-variants'),
    path('query/individuals', views_boolean.individual_query_boolean, name='individual-query'),

    # Catalog metadata (safe for public)
    path('datasets', views_boolean.datasets_boolean, name='datasets'),
    path('cohorts', views_boolean.cohorts_list_boolean, name='cohorts'),
    path('cohorts/<str:cohort_id>', views_boolean.cohort_detail_boolean, name='cohort-detail'),
    path('filtering_terms', views_boolean.filtering_terms_list_boolean, name='filtering-terms'),

    # Beacon v2 entry-type list endpoints (currently empty stubs — see views_boolean.py).
    # Required by the spec verifier; clients see numTotalResults=0 until data is loaded.
    # /individuals and /query/individuals are the SAME view, routed twice — not a
    # wrapper that calls the other. A wrapper delegating to an @api_view-decorated
    # function double-wraps the request and 500s; routing twice cannot.
    path('individuals', views_boolean.individual_query_boolean, name='individuals-list'),
    path('biosamples', views_boolean.biosamples_list_boolean, name='biosamples-list'),
    path('analyses', views_boolean.analyses_list_boolean, name='analyses-list'),
    path('runs', views_boolean.runs_list_boolean, name='runs-list'),

    # Dataset-scoped routes the spec verifier probes (single + sub-entity stubs).
    path('datasets/<str:dataset_id>', views_boolean.dataset_detail_boolean, name='dataset-detail'),
    path('datasets/<str:dataset_id>/<str:entry_type>', views_boolean.dataset_scoped_query_boolean, name='dataset-scoped-query'),

    # Health check
    path('health', views_boolean.health_check, name='health-check'),
]
