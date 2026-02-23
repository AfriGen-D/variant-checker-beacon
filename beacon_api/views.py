from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime
from .models import Variant, Dataset, Individual, Biosample, Analysis, Cohort, FilteringTerm
from django.http import Http404
import json
import logging
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers, vary_on_cookie
from django.conf import settings
from django.utils.decorators import method_decorator
from functools import wraps
import hashlib
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

# Configure logger
logger = logging.getLogger('beacon_api')

def query_cache_key(request):
    """Generate a cache key based on the query parameters or request body."""
    if request.method == 'GET':
        params = request.GET
    else:  # POST method
        params = request.data
    
    # Generate a hash of the parameters
    param_str = json.dumps(dict(params), sort_keys=True)
    key = hashlib.md5(param_str.encode()).hexdigest()
    return f"beacon_query_{key}"

def cache_beacon_query(timeout=None):
    """Custom cache decorator for beacon queries."""
    timeout = timeout or getattr(settings, 'CACHE_TIMEOUT', 300)
    
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Skip cache in test environment or debug mode if requested
            if getattr(settings, 'TESTING', False) or (settings.DEBUG and request.GET.get('nocache') == 'true'):
                return view_func(request, *args, **kwargs)
                
            # Generate key
            cache_key = query_cache_key(request)
            
            # Try to get from cache
            from django.core.cache import cache
            cached_response = cache.get(cache_key)
            
            if cached_response is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_response
            
            # Generate response if not cached
            logger.debug(f"Cache miss for key: {cache_key}")
            response = view_func(request, *args, **kwargs)
            
            # Ensure response is rendered before caching
            if hasattr(response, 'render'):
                response.render()
            
            # Cache response
            cache.set(cache_key, response, timeout)
            
            return response
        return _wrapped_view
    return decorator

class BeaconResponse:
    """Standard response formatter for Beacon v2 API."""
    
    @staticmethod
    def success(data=None, message="Success", meta=None):
        """Format a successful response."""
        response = {
            "meta": {
                "apiVersion": "v2.0.0",
                "beaconId": "org.ga4gh.beacon",
                "timestamp": datetime.now().isoformat(),
                "info": message
            },
            "response": {
                "exists": True if data else False
            }
        }
        
        if data:
            response["response"]["results"] = data
        
        if meta:
            response["meta"].update(meta)
            
        return Response(response)
    
    @staticmethod
    def error(message="An error occurred", code=None, status_code=status.HTTP_400_BAD_REQUEST):
        """Format an error response."""
        response = {
            "meta": {
                "apiVersion": "v2.0.0",
                "beaconId": "org.ga4gh.beacon",
                "timestamp": datetime.now().isoformat(),
                "error": {
                    "errorCode": code or status_code,
                    "errorMessage": message
                }
            },
            "response": None
        }
        
        return Response(response, status=status_code)

class MongoSerializer:
    """A simple serializer for MongoEngine documents."""
    @staticmethod
    def serialize(document):
        """Convert a MongoEngine document to a Python dict."""
        if document is None:
            return None
        return json.loads(document.to_json())

    @staticmethod
    def serialize_many(documents):
        """Convert a list of MongoEngine documents to a list of Python dicts."""
        return [MongoSerializer.serialize(doc) for doc in documents]

@api_view(['GET'])
def beacon_info(request):
    """
    Beacon info endpoint, returns metadata about the beacon.
    """
    datasets = Dataset.objects.all()
    
    info = {
        'id': 'org.ga4gh.beacon',
        'name': 'GA4GH Beacon (MongoDB)',
        'apiVersion': 'v2.0.0',
        'organization': {
            'id': 'ga4gh',
            'name': 'Global Alliance for Genomics and Health'
        },
        'description': 'GA4GH Beacon v2.0 implemented with MongoDB',
        'version': 'v2.0',
        'welcomeUrl': 'https://ga4gh.org',
        'alternativeUrl': 'https://ga4gh.org/api',
        'createDateTime': datetime.now(),
        'updateDateTime': datetime.now(),
        'datasets': MongoSerializer.serialize_many(datasets)
    }
    
    return Response(info)

@api_view(['GET'])
def datasets_list(request):
    """
    List all available datasets.
    """
    datasets = Dataset.objects.all()
    return Response(MongoSerializer.serialize_many(datasets))

@api_view(['GET'])
def dataset_detail(request, dataset_id):
    """
    Get details for a specific dataset.
    """
    try:
        dataset = Dataset.objects.get(id=dataset_id)
    except Dataset.DoesNotExist:
        logger.warning(f"Dataset with ID {dataset_id} not found")
        return BeaconResponse.error(
            message=f"Dataset with ID {dataset_id} not found",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND
        )
    return Response(MongoSerializer.serialize(dataset))

@extend_schema(
    methods=['GET'],
    summary="Query variants (simple)",
    description="Query genomic variants using URL parameters. This is a data discovery endpoint - no data creation.",
    parameters=[
        OpenApiParameter(name='assemblyId', type=OpenApiTypes.STR, description='Genome assembly ID (e.g., GRCh38)'),
        OpenApiParameter(name='referenceName', type=OpenApiTypes.STR, description='Chromosome or contig name (e.g., chr1, 1)'),
        OpenApiParameter(name='start', type=OpenApiTypes.INT, description='Start position (0-based)'),
        OpenApiParameter(name='end', type=OpenApiTypes.INT, description='End position (0-based)'),
        OpenApiParameter(name='referenceBases', type=OpenApiTypes.STR, description='Reference bases at the position'),
        OpenApiParameter(name='alternateBases', type=OpenApiTypes.STR, description='Alternate bases (mutation)'),
    ],
    tags=['Data Discovery - Variants'],
)
@extend_schema(
    methods=['POST'],
    summary="Query variants (complex)",
    description="Query genomic variants using complex filters and JSON body. This is a data discovery endpoint - no data creation.",
    tags=['Data Discovery - Variants'],
    examples=[
        OpenApiExample(
            'Complex variant query',
            value={
                "query": {
                    "assemblyId": "GRCh38",
                    "referenceName": "chr1",
                    "start": 100000,
                    "referenceBases": "A",
                    "alternateBases": "T"
                },
                "filters": [
                    {
                        "id": "gene:BRCA1",
                        "value": "BRCA1"
                    }
                ]
            }
        )
    ]
)
@api_view(['GET', 'POST'])
def variant_list(request):
    """
    Query variants (Beacon v2 compliant). GET for simple queries, POST for complex queries with filters.
    """
    if request.method == 'GET':
        # Simple query via URL parameters
        variants = Variant.objects.all()
        
        # Apply query parameters for filtering (Beacon v2 request parameters)
        assembly_id = request.GET.get('assemblyId')
        reference_name = request.GET.get('referenceName') 
        start = request.GET.get('start')
        end = request.GET.get('end')
        reference_bases = request.GET.get('referenceBases')
        alternate_bases = request.GET.get('alternateBases')
        
        if assembly_id:
            variants = variants.filter(assembly_id=assembly_id)
        if reference_name:
            variants = variants.filter(reference_name=reference_name)
        if start:
            variants = variants.filter(start=int(start))
        if end:
            variants = variants.filter(end=int(end))
        if reference_bases:
            variants = variants.filter(reference_bases=reference_bases)
        if alternate_bases:
            variants = variants.filter(alternate_bases=alternate_bases)
            
        return BeaconResponse.success(
            data=MongoSerializer.serialize_many(variants),
            message="Variants query successful"
        )
    
    elif request.method == 'POST':
        # Complex query via JSON body with filters (Beacon v2 compliant)
        try:
            query_data = request.data
            variants = Variant.objects.all()
            
            # Handle Beacon v2 query structure
            if 'query' in query_data:
                query = query_data['query']
                # Apply genomic query parameters
                if 'assemblyId' in query:
                    variants = variants.filter(assembly_id=query['assemblyId'])
                if 'referenceName' in query:
                    variants = variants.filter(reference_name=query['referenceName'])
                if 'start' in query:
                    variants = variants.filter(start=query['start'])
                if 'end' in query:
                    variants = variants.filter(end=query['end'])
                if 'referenceBases' in query:
                    variants = variants.filter(reference_bases=query['referenceBases'])
                if 'alternateBases' in query:
                    variants = variants.filter(alternate_bases=query['alternateBases'])
            
            # Handle Beacon v2 filters
            if 'filters' in query_data:
                for filter_item in query_data['filters']:
                    filter_id = filter_item.get('id')
                    filter_value = filter_item.get('value')
                    filter_operator = filter_item.get('operator', '=')
                    
                    # Apply filters based on ontology terms or specific fields
                    if filter_id and filter_value:
                        # Custom filter logic based on your data model
                        if 'gene' in filter_id.lower():
                            variants = variants.filter(annotations__gene_symbol__contains=filter_value)
                        elif 'aminoacid' in filter_id.lower():
                            variants = variants.filter(annotations__molecular_consequence__contains=filter_value)
            
            return BeaconResponse.success(
                data=MongoSerializer.serialize_many(variants),
                message="Complex variants query successful"
            )
            
        except Exception as e:
            logger.error(f"Error in variants query: {str(e)}")
            return BeaconResponse.error(
                message=f"Error processing variants query: {str(e)}",
                code="QUERY_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST
            )

@api_view(['GET'])
def variant_detail(request, variant_id):
    """
    Get details for a specific variant.
    """
    try:
        variant = Variant.objects.get(id=variant_id)
    except Variant.DoesNotExist:
        logger.warning(f"Variant with ID {variant_id} not found")
        return BeaconResponse.error(
            message=f"Variant with ID {variant_id} not found",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND
        )
    return Response(MongoSerializer.serialize(variant))

@extend_schema(
    methods=['GET'],
    summary="Query individuals (simple)",
    description="Query individuals/participants using URL parameters. This is a data discovery endpoint - no data creation.",
    parameters=[
        OpenApiParameter(name='id', type=OpenApiTypes.STR, description='Individual ID'),
        OpenApiParameter(name='sex', type=OpenApiTypes.STR, description='Sex (MALE, FEMALE, OTHER, UNKNOWN)'),
    ],
    tags=['Data Discovery - Individuals'],
)
@extend_schema(
    methods=['POST'],
    summary="Query individuals (complex)",
    description="Query individuals using complex filters and JSON body. This is a data discovery endpoint - no data creation.",
    tags=['Data Discovery - Individuals'],
    examples=[
        OpenApiExample(
            'Complex individual query',
            value={
                "query": {
                    "sex": "FEMALE"
                },
                "filters": [
                    {
                        "id": "HP:0000002",
                        "value": "Abnormality of body height"
                    }
                ]
            }
        )
    ]
)
@api_view(['GET', 'POST'])
def individuals_list(request):
    """
    Query individuals (Beacon v2 compliant). GET for simple queries, POST for complex queries with filters.
    """
    if request.method == 'GET':
        # Simple query via URL parameters
        individuals = Individual.objects.all()
        
        # Apply query parameters for filtering
        individual_id = request.GET.get('id')
        sex = request.GET.get('sex')
        
        if individual_id:
            individuals = individuals.filter(id=individual_id)
        if sex:
            individuals = individuals.filter(sex=sex)
            
        return BeaconResponse.success(
            data=MongoSerializer.serialize_many(individuals),
            message="Individuals query successful"
        )
    
    elif request.method == 'POST':
        # Complex query via JSON body with filters (Beacon v2 compliant)
        try:
            query_data = request.data
            individuals = Individual.objects.all()
            
            # Handle Beacon v2 query structure
            if 'query' in query_data:
                query = query_data['query']
                if 'id' in query:
                    individuals = individuals.filter(id=query['id'])
                if 'sex' in query:
                    individuals = individuals.filter(sex=query['sex'])
            
            # Handle Beacon v2 filters (ontology terms, phenotypes, etc.)
            if 'filters' in query_data:
                for filter_item in query_data['filters']:
                    filter_id = filter_item.get('id')
                    filter_value = filter_item.get('value')
                    
                    # Apply filters based on ontology terms
                    if filter_id and filter_value:
                        # Example: phenotype filters
                        if 'phenotype' in filter_id.lower() or 'hp:' in filter_id.lower():
                            individuals = individuals.filter(phenotypicFeatures__type__id=filter_id)
                        elif 'disease' in filter_id.lower():
                            individuals = individuals.filter(diseases__diseaseCode__id=filter_id)
            
            return BeaconResponse.success(
                data=MongoSerializer.serialize_many(individuals),
                message="Complex individuals query successful"
            )
            
        except Exception as e:
            logger.error(f"Error in individuals query: {str(e)}")
            return BeaconResponse.error(
                message=f"Error processing individuals query: {str(e)}",
                code="QUERY_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST
            )

@api_view(['GET'])
def individual_detail(request, individual_id):
    """
    Get details for a specific individual.
    """
    try:
        individual = Individual.objects.get(id=individual_id)
    except Individual.DoesNotExist:
        logger.warning(f"Individual with ID {individual_id} not found")
        return BeaconResponse.error(
            message=f"Individual with ID {individual_id} not found",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND
        )
    return Response(MongoSerializer.serialize(individual))

@api_view(['GET', 'POST'])
def biosamples_list(request):
    """
    Query biosamples (Beacon v2 compliant). GET for simple queries, POST for complex queries with filters.
    """
    if request.method == 'GET':
        # Simple query via URL parameters
        biosamples = Biosample.objects.all()
        
        # Apply query parameters for filtering
        biosample_id = request.GET.get('id')
        individual_id = request.GET.get('individualId')
        biosample_type = request.GET.get('biosampleType')
        
        if biosample_id:
            biosamples = biosamples.filter(id=biosample_id)
        if individual_id:
            biosamples = biosamples.filter(individual_id=individual_id)
        if biosample_type:
            biosamples = biosamples.filter(biosampleType=biosample_type)
            
        return BeaconResponse.success(
            data=MongoSerializer.serialize_many(biosamples),
            message="Biosamples query successful"
        )
    
    elif request.method == 'POST':
        # Complex query via JSON body with filters (Beacon v2 compliant)
        try:
            query_data = request.data
            biosamples = Biosample.objects.all()
                
            # Handle Beacon v2 query structure
            if 'query' in query_data:
                query = query_data['query']
                if 'id' in query:
                    biosamples = biosamples.filter(id=query['id'])
                if 'individualId' in query:
                    biosamples = biosamples.filter(individual_id=query['individualId'])
                if 'biosampleType' in query:
                    biosamples = biosamples.filter(biosampleType=query['biosampleType'])
            
            # Handle Beacon v2 filters (ontology terms, tissue types, etc.)
            if 'filters' in query_data:
                for filter_item in query_data['filters']:
                    filter_id = filter_item.get('id')
                    filter_value = filter_item.get('value')
                    
                    # Apply filters based on ontology terms
                    if filter_id and filter_value:
                        # Example: tissue type filters
                        if 'tissue' in filter_id.lower() or 'uberon:' in filter_id.lower():
                            biosamples = biosamples.filter(sampleOriginType__id=filter_id)
                        elif 'cell' in filter_id.lower() or 'cl:' in filter_id.lower():
                            biosamples = biosamples.filter(cellType__id=filter_id)
            
            return BeaconResponse.success(
                data=MongoSerializer.serialize_many(biosamples),
                message="Complex biosamples query successful"
            )
            
        except Exception as e:
            logger.error(f"Error in biosamples query: {str(e)}")
            return BeaconResponse.error(
                message=f"Error processing biosamples query: {str(e)}",
                code="QUERY_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST
            )

@api_view(['GET'])
def biosample_detail(request, biosample_id):
    """
    Get details for a specific biosample.
    """
    try:
        biosample = Biosample.objects.get(id=biosample_id)
    except Biosample.DoesNotExist:
        logger.warning(f"Biosample with ID {biosample_id} not found")
        return BeaconResponse.error(
            message=f"Biosample with ID {biosample_id} not found",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND
        )
    return Response(MongoSerializer.serialize(biosample))

@api_view(['GET', 'POST'])
def analyses_list(request):
    """
    Query analyses (Beacon v2 compliant). GET for simple queries, POST for complex queries with filters.
    """
    if request.method == 'GET':
        # Simple query via URL parameters
        analyses = Analysis.objects.all()
        
        # Apply query parameters for filtering
        analysis_id = request.GET.get('id')
        biosample_id = request.GET.get('biosampleId')
        analysis_type = request.GET.get('analysisType')
        
        if analysis_id:
            analyses = analyses.filter(id=analysis_id)
        if biosample_id:
            analyses = analyses.filter(biosample_id=biosample_id)
        if analysis_type:
            analyses = analyses.filter(analysisType=analysis_type)
            
        return BeaconResponse.success(
            data=MongoSerializer.serialize_many(analyses),
            message="Analyses query successful"
        )
    
    elif request.method == 'POST':
        # Complex query via JSON body with filters (Beacon v2 compliant)
        try:
            query_data = request.data
            analyses = Analysis.objects.all()
            
            # Handle Beacon v2 query structure
            if 'query' in query_data:
                query = query_data['query']
                if 'id' in query:
                    analyses = analyses.filter(id=query['id'])
                if 'biosampleId' in query:
                    analyses = analyses.filter(biosample_id=query['biosampleId'])
                if 'analysisType' in query:
                    analyses = analyses.filter(analysisType=query['analysisType'])
            
            # Handle Beacon v2 filters (ontology terms, analysis types, etc.)
            if 'filters' in query_data:
                for filter_item in query_data['filters']:
                    filter_id = filter_item.get('id')
                    filter_value = filter_item.get('value')
                    
                    # Apply filters based on ontology terms
                    if filter_id and filter_value:
                        # Example: analysis type filters
                        if 'sequencing' in filter_id.lower() or 'efo:' in filter_id.lower():
                            analyses = analyses.filter(analysisType__id=filter_id)
                        elif 'platform' in filter_id.lower():
                            analyses = analyses.filter(platform=filter_value)
            
            return BeaconResponse.success(
                data=MongoSerializer.serialize_many(analyses),
                message="Complex analyses query successful"
            )
            
        except Exception as e:
            logger.error(f"Error in analyses query: {str(e)}")
            return BeaconResponse.error(
                message=f"Error processing analyses query: {str(e)}",
                code="QUERY_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST
            )

@api_view(['GET'])
def analysis_detail(request, analysis_id):
    """
    Get details for a specific analysis.
    """
    try:
        analysis = Analysis.objects.get(id=analysis_id)
    except Analysis.DoesNotExist:
        logger.warning(f"Analysis with ID {analysis_id} not found")
        return BeaconResponse.error(
            message=f"Analysis with ID {analysis_id} not found",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND
        )
    return Response(MongoSerializer.serialize(analysis))

@api_view(['GET', 'POST'])
def cohorts_list(request):
    """
    Query cohorts (Beacon v2 compliant). GET for simple queries, POST for complex queries with filters.
    """
    if request.method == 'GET':
        # Simple query via URL parameters
        cohorts = Cohort.objects.all()
        
        # Apply query parameters for filtering
        cohort_id = request.GET.get('id')
        cohort_name = request.GET.get('name')
        cohort_type = request.GET.get('cohortType')
        
        if cohort_id:
            cohorts = cohorts.filter(id=cohort_id)
        if cohort_name:
            cohorts = cohorts.filter(name=cohort_name)
        if cohort_type:
            cohorts = cohorts.filter(cohortType=cohort_type)
            
        return BeaconResponse.success(
            data=MongoSerializer.serialize_many(cohorts),
            message="Cohorts query successful"
        )
    
    elif request.method == 'POST':
        # Complex query via JSON body with filters (Beacon v2 compliant)
        try:
            query_data = request.data
            cohorts = Cohort.objects.all()
                
            # Handle Beacon v2 query structure
            if 'query' in query_data:
                query = query_data['query']
                if 'id' in query:
                    cohorts = cohorts.filter(id=query['id'])
                if 'name' in query:
                    cohorts = cohorts.filter(name=query['name'])
                if 'cohortType' in query:
                    cohorts = cohorts.filter(cohortType=query['cohortType'])
            
            # Handle Beacon v2 filters (ontology terms, cohort types, etc.)
            if 'filters' in query_data:
                for filter_item in query_data['filters']:
                    filter_id = filter_item.get('id')
                    filter_value = filter_item.get('value')
                    
                    # Apply filters based on ontology terms
                    if filter_id and filter_value:
                        # Example: cohort type filters
                        if 'study' in filter_id.lower() or 'ncit:' in filter_id.lower():
                            cohorts = cohorts.filter(cohortType__id=filter_id)
                        elif 'size' in filter_id.lower():
                            cohorts = cohorts.filter(cohortSize=int(filter_value))
            
            return BeaconResponse.success(
                data=MongoSerializer.serialize_many(cohorts),
                message="Complex cohorts query successful"
            )
            
        except Exception as e:
            logger.error(f"Error in cohorts query: {str(e)}")
            return BeaconResponse.error(
                message=f"Error processing cohorts query: {str(e)}",
                code="QUERY_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST
            )

@api_view(['GET'])
def cohort_detail(request, cohort_id):
    """
    Get details for a specific cohort.
    """
    try:
        cohort = Cohort.objects.get(id=cohort_id)
    except Cohort.DoesNotExist:
        logger.warning(f"Cohort with ID {cohort_id} not found")
        return BeaconResponse.error(
            message=f"Cohort with ID {cohort_id} not found",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND
        )
    return Response(MongoSerializer.serialize(cohort))

@api_view(['GET', 'POST'])
def filtering_terms_list(request):
    """
    Query filtering terms (Beacon v2 compliant). GET for simple queries, POST for complex queries with filters.
    """
    if request.method == 'GET':
        # Simple query via URL parameters
        terms = FilteringTerm.objects.all()
        
        # Apply query parameters for filtering
        term_id = request.GET.get('id')
        ontology = request.GET.get('ontology')
        label = request.GET.get('label')
        
        if term_id:
            terms = terms.filter(id=term_id)
        if ontology:
            terms = terms.filter(ontology=ontology)
        if label:
            terms = terms.filter(label__icontains=label)
            
        return BeaconResponse.success(
            data=MongoSerializer.serialize_many(terms),
            message="Filtering terms query successful"
        )
    
    elif request.method == 'POST':
        # Complex query via JSON body with filters (Beacon v2 compliant)
        try:
            query_data = request.data
            terms = FilteringTerm.objects.all()
            
            # Handle Beacon v2 query structure
            if 'query' in query_data:
                query = query_data['query']
                if 'id' in query:
                    terms = terms.filter(id=query['id'])
                if 'ontology' in query:
                    terms = terms.filter(ontology=query['ontology'])
                if 'label' in query:
                    terms = terms.filter(label__icontains=query['label'])
            
            # Handle Beacon v2 filters (ontology-specific searches)
            if 'filters' in query_data:
                for filter_item in query_data['filters']:
                    filter_id = filter_item.get('id')
                    filter_value = filter_item.get('value')
                    
                    # Apply filters based on ontology terms
                    if filter_id and filter_value:
                        # Example: ontology-specific filters
                        if 'ontology' in filter_id.lower():
                            terms = terms.filter(ontology=filter_value)
                        elif 'scope' in filter_id.lower():
                            terms = terms.filter(scope__contains=filter_value)
            
            return BeaconResponse.success(
                data=MongoSerializer.serialize_many(terms),
                message="Complex filtering terms query successful"
            )
            
        except Exception as e:
            logger.error(f"Error in filtering terms query: {str(e)}")
            return BeaconResponse.error(
                message=f"Error processing filtering terms query: {str(e)}",
                code="QUERY_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST
            )

@api_view(['GET'])
def filtering_term_detail(request, term_id):
    """
    Get details for a specific filtering term.
    """
    try:
        term = FilteringTerm.objects.get(id=term_id)
    except FilteringTerm.DoesNotExist:
        logger.warning(f"Filtering term with ID {term_id} not found")
        return BeaconResponse.error(
            message=f"Filtering term with ID {term_id} not found",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND
        )
    return Response(MongoSerializer.serialize(term))

@api_view(['POST', 'GET'])
@cache_beacon_query()
def beacon_query(request):
    """
    Beacon query endpoint according to Beacon v2 API.
    """
    try:
        if request.method == 'GET':
            # Extract query parameters
            assembly_id = request.GET.get('assemblyId')
            reference_name = request.GET.get('referenceName')
            start = request.GET.get('start')
            reference_bases = request.GET.get('referenceBases')
            alternate_bases = request.GET.get('alternateBases')
            
            query_params = {
                'assemblyId': assembly_id,
                'referenceName': reference_name,
                'start': start,
                'referenceBases': reference_bases,
                'alternateBases': alternate_bases
            }
        else:  # POST method
            # Extract query from request body
            query_params = {
                'assemblyId': request.data.get('assemblyId'),
                'referenceName': request.data.get('referenceName'),
                'start': request.data.get('start'),
                'referenceBases': request.data.get('referenceBases'),
                'alternateBases': request.data.get('alternateBases')
            }
        
        # Check for required parameters
        missing_params = []
        for param in ['assemblyId', 'referenceName', 'start', 'referenceBases']:
            if not query_params.get(param):
                missing_params.append(param)
                
        if missing_params:
            logger.warning(f"Missing required parameters in beacon query: {', '.join(missing_params)}")
            return BeaconResponse.error(
                message=f"Missing required parameters: {', '.join(missing_params)}",
                code="INVALID_REQUEST",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Convert start to int for query
        try:
            start = int(query_params['start'])
        except (ValueError, TypeError):
            logger.warning(f"Invalid start position: {query_params['start']}")
            return BeaconResponse.error(
                message="Start position must be an integer",
                code="INVALID_PARAMETER",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Query using MongoEngine
        query = {
            'assembly_id': query_params['assemblyId'],
            'reference_name': query_params['referenceName'],
            'start': start,
            'reference_bases': query_params['referenceBases']
        }
        
        # Add alternate bases if provided
        if query_params['alternateBases']:
            query['alternate_bases'] = query_params['alternateBases']
        
        # Log the query
        logger.info(f"Processing beacon query: {query}")
        
        # Execute the query
        try:
            variants = Variant.objects(**query)
            exists = variants.count() > 0
        except Exception as e:
            logger.error(f"Database query error: {str(e)}")
            return BeaconResponse.error(
                message=f"Database query error: {str(e)}",
                code="DATABASE_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Format the response
        query_meta = {
            "request": {
                "referenceName": query_params['referenceName'],
                "start": start,
                "referenceBases": query_params['referenceBases'],
                "assemblyId": query_params['assemblyId'],
                "alternateBases": query_params['alternateBases'] if query_params['alternateBases'] else None
            }
        }
        
        # Return the response
        if exists:
            logger.info(f"Found {variants.count()} matching variants")
            return BeaconResponse.success(
                data=MongoSerializer.serialize_many(variants), 
                message="Matching variants found",
                meta=query_meta
            )
        else:
            logger.info("No matching variants found")
            return BeaconResponse.success(
                data=None,
                message="No matching variants found",
                meta=query_meta
            )
            
    except Exception as e:
        logger.exception(f"Error processing beacon query: {str(e)}")
        return BeaconResponse.error(
            message=f"An error occurred while processing the query: {str(e)}",
            code="SERVER_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def health_check(request):
    """
    Health check endpoint to verify the application is running correctly.
    Checks MongoDB and Redis connections.
    """
    health_status = {
        "status": "UP",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "mongodb": {"status": "DOWN"},
            "redis": {"status": "DOWN"},
            "application": {"status": "UP"}
        }
    }
    
    # Check MongoDB connection
    try:
        # Simple query to verify MongoDB is working
        count = Variant.objects.limit(1).count()
        health_status["components"]["mongodb"] = {
            "status": "UP",
            "details": "Connection successful"
        }
    except Exception as e:
        logger.error(f"MongoDB health check failed: {str(e)}")
        health_status["components"]["mongodb"] = {
            "status": "DOWN",
            "details": str(e)
        }
        health_status["status"] = "DEGRADED"
    
    # Check Redis connection
    try:
        from django.core.cache import cache
        cache.set("health_check", "OK", 10)
        if cache.get("health_check") == "OK":
            health_status["components"]["redis"] = {
                "status": "UP",
                "details": "Connection successful"
            }
        else:
            raise Exception("Could not retrieve test value from cache")
    except Exception as e:
        logger.error(f"Redis health check failed: {str(e)}")
        health_status["components"]["redis"] = {
            "status": "DOWN",
            "details": str(e)
        }
        health_status["status"] = "DEGRADED"
    
    # If any component is down, the overall status should be DEGRADED or DOWN
    if any(component["status"] == "DOWN" for component in health_status["components"].values()):
        if health_status["components"]["mongodb"]["status"] == "DOWN":
            health_status["status"] = "DOWN"  # MongoDB is critical
        else:
            health_status["status"] = "DEGRADED"  # Redis is important but not critical
    
    # Set status code based on health
    status_code = status.HTTP_200_OK
    if health_status["status"] == "DOWN":
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif health_status["status"] == "DEGRADED":
        status_code = status.HTTP_207_MULTI_STATUS
    
    return Response(health_status, status=status_code) 

@api_view(['GET'])
def service_info(request):
    """
    GA4GH Service Info endpoint for Beacon v2 compliance.
    """
    service_info = {
        "id": "org.ga4gh.beacon",
        "name": "GA4GH Beacon v2 API",
        "type": {
            "group": "org.ga4gh",
            "artifact": "beacon",
            "version": "2.0.0"
        },
        "description": "GA4GH Beacon v2.0 implementation with MongoDB for genomic data discovery",
        "organization": {
            "name": "GA4GH Beacon Implementation",
            "url": "https://ga4gh.org"
        },
        "contactUrl": "https://ga4gh.org/contact",
        "documentationUrl": "https://docs.genomebeacons.org/",
        "createdAt": "2022-01-01T00:00:00Z",
        "updatedAt": datetime.now().isoformat() + "Z",
        "environment": "production" if not settings.DEBUG else "development",
        "version": "2.0.0"
    }
    return Response(service_info)

@api_view(['GET'])
def configuration(request):
    """
    Beacon configuration endpoint - returns configuration details.
    """
    config = {
        "$schema": "https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/framework/json/configuration/beaconConfigurationSchema.json",
        "maturityAttributes": {
            "productionStatus": "development"
        },
        "securityAttributes": {
            "defaultGranularity": "record",
            "securityLevels": ["PUBLIC"]
        },
        "entryTypes": {
            "genomicVariation": {
                "id": "genomicVariation",
                "name": "Genomic Variations",
                "ontologyTermForThisType": {
                    "id": "EDAM:data_3498",
                    "label": "Sequence variations"
                },
                "partOfSpecification": "Beacon v2.0.0",
                "description": "Genomic variations including SNVs, indels, and structural variants",
                "defaultSchema": {
                    "id": "ga4gh-beacon-genomicvariation-v2.0.0",
                    "name": "Default schema for genomic variations",
                    "referenceToSchemaDefinition": "https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/models/json/beacon-v2-default-model/genomicVariations/defaultSchema.json",
                    "schemaVersion": "v2.0.0"
                },
                "aCollectionOf": [
                    {
                        "id": "genomicVariation",
                        "name": "Genomic Variation"
                    }
                ],
                "additionalSupportedSchemas": []
            },
            "individual": {
                "id": "individual", 
                "name": "Individuals",
                "ontologyTermForThisType": {
                    "id": "NCIT:C25190",
                    "label": "Person"
                },
                "partOfSpecification": "Beacon v2.0.0",
                "description": "Individual/patient/participant records",
                "defaultSchema": {
                    "id": "ga4gh-beacon-individual-v2.0.0",
                    "name": "Default schema for individuals",
                    "referenceToSchemaDefinition": "https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/models/json/beacon-v2-default-model/individuals/defaultSchema.json",
                    "schemaVersion": "v2.0.0"
                }
            },
            "biosample": {
                "id": "biosample",
                "name": "Biosamples", 
                "ontologyTermForThisType": {
                    "id": "NCIT:C70699",
                    "label": "Biospecimen"
                },
                "partOfSpecification": "Beacon v2.0.0",
                "description": "Biological samples",
                "defaultSchema": {
                    "id": "ga4gh-beacon-biosample-v2.0.0",
                    "name": "Default schema for biosamples",
                    "referenceToSchemaDefinition": "https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/models/json/beacon-v2-default-model/biosamples/defaultSchema.json",
                    "schemaVersion": "v2.0.0"
                }
            },
            "dataset": {
                "id": "dataset",
                "name": "Datasets",
                "ontologyTermForThisType": {
                    "id": "NCIT:C47824", 
                    "label": "Data Set"
                },
                "partOfSpecification": "Beacon v2.0.0",
                "description": "Dataset records",
                "defaultSchema": {
                    "id": "ga4gh-beacon-dataset-v2.0.0",
                    "name": "Default schema for datasets",
                    "referenceToSchemaDefinition": "https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/models/json/beacon-v2-default-model/datasets/defaultSchema.json", 
                    "schemaVersion": "v2.0.0"
                }
            },
            "cohort": {
                "id": "cohort",
                "name": "Cohorts",
                "ontologyTermForThisType": {
                    "id": "NCIT:C61512",
                    "label": "Cohort"
                },
                "partOfSpecification": "Beacon v2.0.0", 
                "description": "Cohort records",
                "defaultSchema": {
                    "id": "ga4gh-beacon-cohort-v2.0.0",
                    "name": "Default schema for cohorts",
                    "referenceToSchemaDefinition": "https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/models/json/beacon-v2-default-model/cohorts/defaultSchema.json",
                    "schemaVersion": "v2.0.0"
                }
            },
            "analysis": {
                "id": "analysis",
                "name": "Analyses", 
                "ontologyTermForThisType": {
                    "id": "efo:EFO_0000001",
                    "label": "Analysis"
                },
                "partOfSpecification": "Beacon v2.0.0",
                "description": "Analysis records",
                "defaultSchema": {
                    "id": "ga4gh-beacon-analysis-v2.0.0",
                    "name": "Default schema for analyses",
                    "referenceToSchemaDefinition": "https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/models/json/beacon-v2-default-model/analyses/defaultSchema.json",
                    "schemaVersion": "v2.0.0"
                }
            }
        }
    }
    return Response(config)

@api_view(['GET'])
def entry_types(request):
    """
    Entry types endpoint - returns available entry types.
    """
    entry_types = {
        "entryTypes": {
            "genomicVariation": {
                "id": "genomicVariation",
                "name": "Genomic Variations",
                "ontologyTermForThisType": {
                    "id": "EDAM:data_3498",
                    "label": "Sequence variations"
                },
                "partOfSpecification": "Beacon v2.0.0"
            },
            "individual": {
                "id": "individual", 
                "name": "Individuals",
                "ontologyTermForThisType": {
                    "id": "NCIT:C25190",
                    "label": "Person"
                },
                "partOfSpecification": "Beacon v2.0.0"
            },
            "biosample": {
                "id": "biosample",
                "name": "Biosamples",
                "ontologyTermForThisType": {
                    "id": "NCIT:C70699", 
                    "label": "Biospecimen"
                },
                "partOfSpecification": "Beacon v2.0.0"
            },
            "dataset": {
                "id": "dataset",
                "name": "Datasets",
                "ontologyTermForThisType": {
                    "id": "NCIT:C47824",
                    "label": "Data Set"
                },
                "partOfSpecification": "Beacon v2.0.0"
            },
            "cohort": {
                "id": "cohort", 
                "name": "Cohorts",
                "ontologyTermForThisType": {
                    "id": "NCIT:C61512",
                    "label": "Cohort"
                },
                "partOfSpecification": "Beacon v2.0.0"
            },
            "analysis": {
                "id": "analysis",
                "name": "Analyses",
                "ontologyTermForThisType": {
                    "id": "efo:EFO_0000001",
                    "label": "Analysis"
                },
                "partOfSpecification": "Beacon v2.0.0"
            }
        }
    }
    return Response(entry_types)

@api_view(['GET'])
def beacon_map(request):
    """
    Beacon map endpoint - returns sitemap of available endpoints.
    """
    base_url = request.build_absolute_uri('/api/')
    
    beacon_map = {
        "$schema": "https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/framework/json/responses/beaconMapResponse.json",
        "endpointSets": {
            "rootUrl": base_url,
            "entryTypes": {
                "genomicVariation": {
                    "rootUrl": f"{base_url}g_variants",
                    "singleEntryUrl": f"{base_url}g_variants/{{id}}",
                    "endpoints": {
                        "genomicVariation": {
                            "returnedEntryType": "genomicVariation"
                        }
                    }
                },
                "individual": {
                    "rootUrl": f"{base_url}individuals", 
                    "singleEntryUrl": f"{base_url}individuals/{{id}}",
                    "endpoints": {
                        "individual": {
                            "returnedEntryType": "individual"
                        }
                    }
                },
                "biosample": {
                    "rootUrl": f"{base_url}biosamples",
                    "singleEntryUrl": f"{base_url}biosamples/{{id}}",
                    "endpoints": {
                        "biosample": {
                            "returnedEntryType": "biosample"
                        }
                    }
                },
                "dataset": {
                    "rootUrl": f"{base_url}datasets",
                    "singleEntryUrl": f"{base_url}datasets/{{id}}",
                    "endpoints": {
                        "dataset": {
                            "returnedEntryType": "dataset"
                        }
                    }
                },
                "cohort": {
                    "rootUrl": f"{base_url}cohorts",
                    "singleEntryUrl": f"{base_url}cohorts/{{id}}",
                    "endpoints": {
                        "cohort": {
                            "returnedEntryType": "cohort"
                        }
                    }
                },
                "analysis": {
                    "rootUrl": f"{base_url}analyses",
                    "singleEntryUrl": f"{base_url}analyses/{{id}}",
                    "endpoints": {
                        "analysis": {
                            "returnedEntryType": "analysis"
                        }
                    }
                }
            }
        }
    }
    return Response(beacon_map) 