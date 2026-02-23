from rest_framework import serializers
from .models import (
    Variant, Individual, Dataset, VariantAnnotation, VariantInDataset,
    Biosample, Analysis, Cohort, FilteringTerm
)


class VariantAnnotationSerializer(serializers.Serializer):
    gene_id = serializers.CharField(required=False, allow_null=True)
    gene_symbol = serializers.CharField(required=False, allow_null=True)
    molecular_consequence = serializers.CharField(required=False, allow_null=True)
    clinical_significance = serializers.CharField(required=False, allow_null=True)
    additional_annotations = serializers.DictField(required=False)


class VariantSerializer(serializers.Serializer):
    id = serializers.CharField()
    assembly_id = serializers.CharField()
    reference_name = serializers.CharField()
    start = serializers.IntegerField()
    end = serializers.IntegerField()
    reference_bases = serializers.CharField()
    alternate_bases = serializers.CharField()
    variant_type = serializers.CharField(required=False)
    annotations = VariantAnnotationSerializer(many=True, required=False)
    created = serializers.DateTimeField()
    updated = serializers.DateTimeField()
    
    def create(self, validated_data):
        annotations_data = validated_data.pop('annotations', [])
        variant = Variant(**validated_data)
        
        for annotation_data in annotations_data:
            variant.annotations.append(VariantAnnotation(**annotation_data))
        
        variant.save()
        return variant
    
    def update(self, instance, validated_data):
        instance.assembly_id = validated_data.get('assembly_id', instance.assembly_id)
        instance.reference_name = validated_data.get('reference_name', instance.reference_name)
        instance.start = validated_data.get('start', instance.start)
        instance.end = validated_data.get('end', instance.end)
        instance.reference_bases = validated_data.get('reference_bases', instance.reference_bases)
        instance.alternate_bases = validated_data.get('alternate_bases', instance.alternate_bases)
        instance.variant_type = validated_data.get('variant_type', instance.variant_type)
        
        # Update annotations if provided
        if 'annotations' in validated_data:
            instance.annotations = []
            for annotation_data in validated_data.get('annotations', []):
                instance.annotations.append(VariantAnnotation(**annotation_data))
        
        instance.save()
        return instance


class IndividualSerializer(serializers.Serializer):
    id = serializers.CharField()
    sex = serializers.CharField(required=False, allow_null=True)
    ethnicity = serializers.CharField(required=False, allow_null=True)
    geographic_origin = serializers.CharField(required=False, allow_null=True)
    age = serializers.IntegerField(required=False, allow_null=True)
    diseases = serializers.DictField(required=False, allow_null=True)
    phenotypic_features = serializers.DictField(required=False, allow_null=True)
    created = serializers.DateTimeField()
    updated = serializers.DateTimeField()
    
    def create(self, validated_data):
        return Individual.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class DatasetSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_null=True)
    assembly_id = serializers.CharField()
    dataset_type = serializers.CharField(required=False, default="genomics")
    dataset_size = serializers.DictField(required=False, allow_null=True)
    contact_info = serializers.DictField(required=False, allow_null=True)
    create_date = serializers.DateTimeField()
    update_date = serializers.DateTimeField()
    
    def create(self, validated_data):
        return Dataset.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class VariantInDatasetSerializer(serializers.ModelSerializer):
    variant = VariantSerializer(read_only=True)
    dataset = DatasetSerializer(read_only=True)
    individual = IndividualSerializer(read_only=True)
    
    class Meta:
        model = VariantInDataset
        fields = '__all__'


# New serializers for Beacon v2 compliance
class BiosampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Biosample
        fields = '__all__'


class AnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = Analysis
        fields = '__all__'


class CohortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cohort
        fields = '__all__'


class FilteringTermSerializer(serializers.ModelSerializer):
    class Meta:
        model = FilteringTerm
        fields = '__all__'


# Beacon specific serializers for the API responses
class BeaconInfoSerializer(serializers.Serializer):
    """Serializer for Beacon info endpoint"""
    id = serializers.CharField(default="org.ga4gh.beacon")
    name = serializers.CharField(default="GA4GH Beacon")
    apiVersion = serializers.CharField(default="v2.0.0")
    organization = serializers.DictField(default={
        "id": "ga4gh",
        "name": "Global Alliance for Genomics and Health"
    })
    description = serializers.CharField(default="GA4GH Beacon v2.0")
    version = serializers.CharField(default="v2.0")
    welcomeUrl = serializers.CharField(default="https://ga4gh.org")
    alternativeUrl = serializers.CharField(default="https://ga4gh.org/api")
    createDateTime = serializers.DateTimeField(format="%Y-%m-%dT%H:%M:%SZ", read_only=True)
    updateDateTime = serializers.DateTimeField(format="%Y-%m-%dT%H:%M:%SZ", read_only=True)
    datasets = DatasetSerializer(many=True, read_only=True)


class BeaconVariantResponseSerializer(serializers.Serializer):
    """Serializer for Beacon variant query responses"""
    beaconId = serializers.CharField(default="org.ga4gh.beacon")
    apiVersion = serializers.CharField(default="v2.0.0")
    exists = serializers.BooleanField()
    alleleRequest = serializers.DictField()
    datasetAlleleResponses = serializers.ListField(child=serializers.DictField())
    error = serializers.DictField(required=False)


# Additional response serializers for Beacon v2
class BeaconResultsetResponseSerializer(serializers.Serializer):
    """Serializer for Beacon resultset responses (used in Beacon v2)"""
    beaconId = serializers.CharField(default="org.ga4gh.beacon")
    apiVersion = serializers.CharField(default="v2.0.0")
    exists = serializers.BooleanField()
    resultsHandover = serializers.ListField(child=serializers.DictField(), default=[])
    results = serializers.ListField(default=[])
    info = serializers.DictField(default={})
    error = serializers.DictField(required=False) 