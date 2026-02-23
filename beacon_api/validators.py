"""
Input validators for Beacon API query endpoints
Prevents injection attacks and validates genomic coordinates
"""
import re
from rest_framework import serializers
from rest_framework.exceptions import ValidationError


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
        """Sanitize input value"""
        if value is None:
            return None
            
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
        sanitized = {}
        
        for key, value in params.items():
            # Sanitize key
            key = cls.sanitize(key)
            
            # Sanitize value (handle lists)
            if isinstance(value, list):
                value = [cls.sanitize(v) for v in value]
            else:
                value = cls.sanitize(value)
                
            sanitized[key] = value
            
        return sanitized


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
    datasetIds = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    
    def validate(self, data):
        """Cross-field validation"""
        
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
        
        # Validate variant type
        if 'variantType' in data:
            data['variantType'] = VariantQueryValidator.validate_variant_type(data['variantType'])
        
        # Validate assembly
        valid_assemblies = ['GRCh37', 'GRCh38', 'hg19', 'hg38']
        if data.get('assemblyId') not in valid_assemblies:
            raise ValidationError(f"Invalid assembly: {data.get('assemblyId')}")
        
        return data


def validate_query_request(request_data):
    """
    Main validation function for query requests
    Returns sanitized and validated data
    """
    # Sanitize all input parameters first
    sanitized = QueryParameterSanitizer.sanitize_query_params(request_data)
    
    # Validate using serializer
    serializer = BeaconQuerySerializer(data=sanitized)
    serializer.is_valid(raise_exception=True)
    
    return serializer.validated_data