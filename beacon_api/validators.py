"""
Input validators for Beacon API query endpoints
Prevents injection attacks and validates genomic coordinates
"""
import re

from .assembly import UnknownAssembly, canonical_assembly
from .query_vocabulary import (
    UnknownVariantType, canonical_variant_type, dataset_id_list,
)
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .filters import UnsupportedFilters, reject_filters
from .pagination import (
    DEFAULT_SKIP, InvalidPagination, MAX_SKIP, clamp_limit, parse_pagination,
)


class GenomicCoordinateValidator:
    """Validate genomic coordinates for safety and correctness"""
    
    # Valid chromosome names
    VALID_CHROMOSOMES = (
        ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10',
         '11', '12', '13', '14', '15', '16', '17', '18', '19', '20',
         '21', '22', 'X', 'Y', 'M', 'MT'] +
        [f'chr{i}' for i in range(1, 23)] +
        ['chrX', 'chrY', 'chrM', 'chrMT']
    )
    
    # Maximum coordinate value (human genome is ~3 billion bases)
    MAX_COORDINATE = 300_000_000
    
    # Maximum range for queries (prevent excessive resource usage)
    MAX_RANGE = 10_000_000  # 10 million bases
    
    @classmethod
    def validate_chromosome(cls, value):
        """Validate chromosome/reference name"""
        if not value:
            raise ValidationError("Chromosome/referenceName is required")
            
        # Remove any whitespace
        value = str(value).strip()
        
        # Check for injection attempts
        if re.search(r'[;\'"\$\{\}]', value):
            raise ValidationError("Invalid characters in chromosome name")
            
        # Validate against known chromosomes
        if value not in cls.VALID_CHROMOSOMES:
            raise ValidationError(f"Invalid chromosome: {value}")
            
        return value
    
    @classmethod
    def validate_position(cls, value, field_name='position'):
        """Validate genomic position"""
        if value is None:
            return None
            
        try:
            # Convert to integer
            position = int(value)
        except (ValueError, TypeError):
            raise ValidationError(f"{field_name} must be an integer")
            
        # Check range
        if position < 0:
            raise ValidationError(f"{field_name} must be non-negative")
        if position > cls.MAX_COORDINATE:
            raise ValidationError(f"{field_name} exceeds maximum value")
            
        return position
    
    @classmethod
    def validate_range(cls, start, end):
        """Validate genomic range"""
        if start is not None and end is not None:
            if start > end:
                raise ValidationError("Start position must be less than end position")
            
            range_size = end - start
            if range_size > cls.MAX_RANGE:
                raise ValidationError(f"Range too large (max {cls.MAX_RANGE} bases)")
        
        return start, end


class VariantQueryValidator:
    """Validate variant query parameters"""
    
    VALID_BASES = ['A', 'C', 'G', 'T', 'N']
    MAX_ALLELE_LENGTH = 1000
    
    @classmethod
    def validate_allele(cls, value, field_name='allele'):
        """Validate allele string"""
        if not value:
            return None
            
        value = str(value).strip().upper()
        
        # Check length
        if len(value) > cls.MAX_ALLELE_LENGTH:
            raise ValidationError(f"{field_name} too long (max {cls.MAX_ALLELE_LENGTH})")
        
        # Check for valid bases only
        if not all(base in cls.VALID_BASES for base in value):
            raise ValidationError(f"Invalid bases in {field_name}")
            
        return value
    
    @classmethod
    def validate_variant_type(cls, value):
        """Validate variant type"""
        valid_types = ['SNP', 'DEL', 'INS', 'DUP', 'INV', 'CNV', 'DUP:TANDEM', 'DEL:ME', 'INS:ME']
        
        if value and value not in valid_types:
            raise ValidationError(f"Invalid variant type: {value}")
            
        return value


class QueryParameterSanitizer:
    """Sanitize query parameters to prevent injection attacks"""
    
    # Pattern to detect potential injection attempts
    INJECTION_PATTERNS = [
        r'\$where',  # MongoDB injection
        r'\$[\w]+',  # MongoDB operators
        r'[;\'"\\]',  # SQL/NoSQL injection characters
        r'<script',  # XSS attempts
        r'javascript:',  # XSS attempts
        r'{\s*\$',  # MongoDB query injection
    ]
    
    @classmethod
    def sanitize(cls, value):
        """Sanitize input value, walking nested containers.

        Containers are recursed into rather than stringified. ``str()`` on a
        dict or list renders Python's repr, whose quotes and braces then match
        INJECTION_PATTERNS -- so a spec-shaped POST body would be rejected as
        an injection attempt over punctuation this method itself produced. GET
        never hit it because ``request.GET.dict()`` yields flat strings, while
        POST passes ``request.data`` through with ``requestParameters`` still
        an object.

        Recursing also tightens the check rather than loosening it: every key
        and every leaf is now matched individually, so a Mongo operator key
        such as ``$where`` is still caught by the ``\\$[\\w]+`` pattern instead
        of being one substring inside a much larger flattened blob.
        """
        if value is None:
            return None

        if isinstance(value, dict):
            return {cls.sanitize(key): cls.sanitize(item) for key, item in value.items()}

        if isinstance(value, (list, tuple)):
            return [cls.sanitize(item) for item in value]

        value = str(value)

        # Check for injection patterns
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                raise ValidationError("Invalid characters detected in query")

        # Remove any non-printable characters
        value = ''.join(char for char in value if char.isprintable())

        return value.strip()

    @classmethod
    def sanitize_query_params(cls, params):
        """Sanitize all query parameters"""
        return {cls.sanitize(key): cls.sanitize(value) for key, value in params.items()}


class BeaconQuerySerializer(serializers.Serializer):
    """Serializer for beacon query validation"""
    
    # Genomic coordinates
    referenceName = serializers.CharField(required=False, allow_blank=False)
    chromosome = serializers.CharField(required=False, allow_blank=False)
    start = serializers.IntegerField(required=False, min_value=0)
    end = serializers.IntegerField(required=False, min_value=0)
    position = serializers.IntegerField(required=False, min_value=0)
    
    # Alleles
    referenceBases = serializers.CharField(required=False, max_length=1000)
    alternateBases = serializers.CharField(required=False, max_length=1000)
    
    # Variant info
    variantType = serializers.CharField(required=False, max_length=50)
    
    # Assembly
    assemblyId = serializers.CharField(required=False, default='GRCh38')
    
    # Dataset
    # A GET query string collapses to one value per key, so the list form can
    # only arrive on POST. Accept the comma-separated spelling too, or the
    # parameter is unusable from a URL — see query_vocabulary.dataset_id_list.
    datasetIds = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )

    def to_internal_value(self, data):
        if 'datasetIds' in data:
            data = dict(data)
            data['datasetIds'] = dataset_id_list(data['datasetIds'])
        return super().to_internal_value(data)

    # Granularity (Beacon v2). Default 'boolean'; 'aggregated' returns allele
    # frequencies. 'count'/'record' are accepted but not distinct in this
    # aggregate-panel beacon.
    requestedGranularity = serializers.ChoiceField(
        choices=['boolean', 'count', 'aggregated', 'record'],
        required=False,
        default='boolean',
    )

    # Pagination (Beacon v2). Bounds live in beacon_api/pagination.py so the
    # collection endpoints — which never reach this serializer — enforce the
    # identical limits. Note the deliberate asymmetry between the two:
    #
    #   * `limit` has no max_value here; clamp_limit() caps it in validate().
    #     An over-large limit means "give me everything", and clamping it while
    #     reporting the applied value in receivedRequestSummary answers that
    #     honestly.
    #   * `skip` IS hard-capped, because silently reducing an offset would
    #     serve a *different page* than the one requested while the response
    #     claimed otherwise — the exact class of lie this work removes.
    skip = serializers.IntegerField(required=False, min_value=0, max_value=MAX_SKIP)
    limit = serializers.IntegerField(required=False, min_value=0)

    def validate(self, data):
        """Cross-field validation"""

        # Always resolve pagination, including when the caller omitted it, so
        # downstream code and the echoed receivedRequestSummary read the same
        # two numbers rather than each inventing a default.
        data['skip'] = data.get('skip', DEFAULT_SKIP)
        data['limit'] = clamp_limit(data.get('limit'))


        # Get chromosome (handle both referenceName and chromosome fields)
        chromosome = data.get('referenceName') or data.get('chromosome')
        if chromosome:
            data['referenceName'] = GenomicCoordinateValidator.validate_chromosome(chromosome)
        
        # Validate positions
        if 'start' in data:
            data['start'] = GenomicCoordinateValidator.validate_position(data['start'], 'start')
        if 'end' in data:
            data['end'] = GenomicCoordinateValidator.validate_position(data['end'], 'end')
        if 'position' in data:
            data['position'] = GenomicCoordinateValidator.validate_position(data['position'], 'position')
        
        # Validate range
        if 'start' in data and 'end' in data:
            GenomicCoordinateValidator.validate_range(data['start'], data['end'])
        
        # Validate alleles
        if 'referenceBases' in data:
            data['referenceBases'] = VariantQueryValidator.validate_allele(
                data['referenceBases'], 'referenceBases'
            )
        if 'alternateBases' in data:
            data['alternateBases'] = VariantQueryValidator.validate_allele(
                data['alternateBases'], 'alternateBases'
            )
        
        # Validate variant type. Canonicalised, not whitelisted: the old list
        # contained SNP while ingest writes SNV, so the correct term was
        # rejected while DEL was accepted and then silently discarded.
        if 'variantType' in data:
            try:
                data['variantType'] = canonical_variant_type(data['variantType'])
            except UnknownVariantType as exc:
                raise ValidationError(str(exc))
        
        # Validate assembly. Canonicalise rather than whitelist: the old flat
        # list accepted hg38 and GRCh38 as equally valid and then let the query
        # path compare the caller's literal spelling against stored data, so a
        # UCSC-vocabulary caller was told the variant does not exist.
        try:
            data['assemblyId'] = canonical_assembly(data.get('assemblyId'))
        except UnknownAssembly as exc:
            raise ValidationError(str(exc))
        
        return data


def validate_query_request(request_data):
    """
    Main validation function for query requests
    Returns sanitized and validated data

    Raises DRF ``ValidationError`` for every rejection, including the
    filters/pagination ones raised as plain ``ValueError`` subclasses by the
    standalone modules. Converting here means callers keep a single
    ``except ValidationError`` and the existing ``extract_error_message()``
    path renders all of them identically.
    """
    # `filters` must be judged BEFORE sanitization. QueryParameterSanitizer
    # stringifies each value and rejects quotes and braces, so a spec-shaped
    # POST body — filters: [{"id": "NCIT:C16576"}] — would otherwise fail as
    # "Invalid characters detected in query", which tells the client nothing
    # about the real reason (this beacon publishes no filtering terms).
    try:
        reject_filters(request_data if isinstance(request_data, dict) else {})
    except UnsupportedFilters as e:
        raise ValidationError(str(e))

    # Same reason for pagination: parse it off the raw request so a POST body
    # carrying a non-scalar skip/limit gets a pagination-specific message.
    try:
        skip, limit = parse_pagination(request_data)
    except InvalidPagination as e:
        raise ValidationError(str(e))

    # Sanitize all input parameters first
    sanitized = QueryParameterSanitizer.sanitize_query_params(request_data)

    # Validate using serializer
    serializer = BeaconQuerySerializer(data=sanitized)
    serializer.is_valid(raise_exception=True)

    validated = serializer.validated_data
    # parse_pagination() saw the untouched values; the serializer saw the
    # stringified copies. They agree, but the former is the canonical parse
    # shared with the collection endpoints, so it wins.
    validated['skip'] = skip
    validated['limit'] = limit
    return validated