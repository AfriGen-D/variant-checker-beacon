from django.urls import path, include
from . import views

urlpatterns = [
    # Authentication endpoints (if enabled)
    path('auth/', include('beacon_api.auth_urls')),
    
    # Beacon v2 core endpoints (REQUIRED)
    path('', views.beacon_info, name='beacon-info'),
    # GA4GH Service Info
    path('info', views.beacon_info, name='beacon-service-info'),
    path('service-info', views.service_info, name='service-info'),  
    # Beacon configuration
    path('configuration', views.configuration, name='configuration'),  
    # Entry types
    path('entry_types', views.entry_types, name='entry-types'),  
    # Beacon map
    path('map', views.beacon_map, name='beacon-map'),  
    
    # Filtering terms endpoints (REQUIRED)
    path('filtering_terms', views.filtering_terms_list, name='filtering-terms-list'),
    path('filtering_terms/<str:term_id>', views.filtering_term_detail, name='filtering-term-detail'),
    
    # Beacon v2 query endpoints (REQUIRED)
    path('query', views.beacon_query, name='beacon-query'),
    
    # Entry type endpoints (DATA DISCOVERY ONLY - NO CREATE OPERATIONS)
    # Dataset endpoints
    path('datasets', views.datasets_list, name='datasets-list'),
    path('datasets/<str:dataset_id>', views.dataset_detail, name='dataset-detail'),
    
    # Individual endpoints  
    path('individuals', views.individuals_list, name='individuals-list'),
    path('individuals/<str:individual_id>', views.individual_detail, name='individual-detail'),
    
    # Genomic variant endpoints - using g_variants for Beacon v2 compliance
    path('g_variants', views.variant_list, name='variant-list'),
    path('g_variants/<str:variant_id>', views.variant_detail, name='variant-detail'),
    
    # Biosample endpoints
    path('biosamples', views.biosamples_list, name='biosamples-list'),
    path('biosamples/<str:biosample_id>', views.biosample_detail, name='biosample-detail'),
    
    # Analysis endpoints
    path('analyses', views.analyses_list, name='analyses-list'),
    path('analyses/<str:analysis_id>', views.analysis_detail, name='analysis-detail'),
    
    # Cohort endpoints
    path('cohorts', views.cohorts_list, name='cohorts-list'),
    path('cohorts/<str:cohort_id>', views.cohort_detail, name='cohort-detail'),
] 