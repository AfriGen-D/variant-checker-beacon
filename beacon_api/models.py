import mongoengine as me
from datetime import datetime

class VariantAnnotation(me.EmbeddedDocument):
    gene_id = me.StringField()
    gene_symbol = me.StringField()
    molecular_consequence = me.StringField()
    clinical_significance = me.StringField()
    additional_annotations = me.DictField()
    
    def __str__(self):
        return f"Annotation for {self.gene_symbol}"

class Variant(me.Document):
    id = me.StringField(primary_key=True)
    assembly_id = me.StringField(required=True)
    reference_name = me.StringField(required=True)  # Chromosome
    start = me.IntField(required=True)
    end = me.IntField(required=True)
    reference_bases = me.StringField(required=True)
    alternate_bases = me.StringField(required=True)
    variant_type = me.StringField()
    dataset_ids = me.ListField(me.StringField())

    # Aggregate population allele frequency. For the aggregate reference panel
    # this is public summary data, served at GA4GH 'aggregated' granularity.
    allele_frequency = me.FloatField()

    # Embedded annotations
    annotations = me.EmbeddedDocumentListField(VariantAnnotation)
    
    # Metadata fields
    created = me.DateTimeField(default=datetime.now)
    updated = me.DateTimeField(default=datetime.now)
    
    meta = {
        'collection': 'variants',
        'indexes': [
            # Single-field indexes retained from the original schema.
            'assembly_id',
            'reference_name',
            'start',
            'reference_bases',
            'alternate_bases',

            # --- Compound indexes for the queries actually issued ---------
            # These are declarations only; nothing is built automatically
            # because auto_create_index is False. Run:
            #     python manage.py create_indexes
            #
            # 1. Hot path: the positional overlap query in
            #    views_boolean.variant_query_boolean builds
            #    {reference_name__in, start__lt, end__gt}. Leading equality
            #    key reference_name, then the two range keys. Without this,
            #    the planner falls back to the single-field `reference_name`
            #    index and fetches every variant on the chromosome
            #    (millions) to evaluate the position range.
            {'fields': ['reference_name', 'start', 'end'],
             'name': 'variant_locus_overlap'},

            # 2. Exact-allele lookup: the same view adds reference_bases and
            #    alternate_bases whenever the caller supplies them, which is
            #    the common "does this specific SNV exist" query. Equality on
            #    reference_name, range on start, then the two allele
            #    equalities so they are evaluated inside the index rather
            #    than by fetching candidate documents.
            {'fields': ['reference_name', 'start', 'reference_bases', 'alternate_bases'],
             'name': 'variant_exact_allele'},

            # 3. Per-dataset attribution: the same view then re-filters the
            #    matched set with `dataset_ids=<id>` once per dataset. That
            #    field had no index at all, so each of those N follow-up
            #    queries degraded into a scan. Multikey index over the array.
            {'fields': ['dataset_ids'], 'name': 'variant_dataset_ids'},
        ],
        'auto_create_index': False,  # Disable auto index creation
    }
    
    def __str__(self):
        return f"{self.reference_name}:{self.start}:{self.reference_bases}>{self.alternate_bases}"

class Individual(me.Document):
    id = me.StringField(primary_key=True)
    sex = me.StringField()
    ethnicity = me.StringField()
    geographic_origin = me.StringField()
    age = me.IntField()
    
    # Extended fields for Beacon v2
    diseases = me.DictField()
    phenotypic_features = me.DictField()
    
    # Metadata fields
    created = me.DateTimeField(default=datetime.now)
    updated = me.DateTimeField(default=datetime.now)
    
    meta = {
        'collection': 'individuals',
        'auto_create_index': False,  # Disable auto index creation
    }
    
    def __str__(self):
        return self.id

class Dataset(me.Document):
    id = me.StringField(primary_key=True)
    name = me.StringField(required=True)
    description = me.StringField()
    assembly_id = me.StringField(required=True)
    
    # Extended fields for Beacon v2
    dataset_type = me.StringField(default="genomics")
    dataset_size = me.DictField()  # For storing variant count, sample count, etc.
    contact_info = me.DictField()
    
    # Metadata fields
    create_date = me.DateTimeField(default=datetime.now)
    update_date = me.DateTimeField(default=datetime.now)
    
    meta = {
        'collection': 'datasets',
        'auto_create_index': False,  # Disable auto index creation
    }
    
    def __str__(self):
        return self.name

# Additional models required for Beacon v2 compliance

class Biosample(me.Document):
    id = me.StringField(primary_key=True)
    individual_id = me.StringField(required=True)
    description = me.StringField()
    sample_type = me.StringField()
    collection_date = me.DateTimeField()
    
    # Extended fields for Beacon v2
    tissue = me.StringField()
    sample_processing = me.StringField()
    material_used = me.StringField()
    additional_properties = me.DictField()
    
    # Metadata fields
    created = me.DateTimeField(default=datetime.now)
    updated = me.DateTimeField(default=datetime.now)
    
    meta = {
        'collection': 'biosamples',
        'indexes': [
            'individual_id'
        ],
        'auto_create_index': False,  # Disable auto index creation
    }
    
    def __str__(self):
        return f"Biosample {self.id} from individual {self.individual_id}"

class Analysis(me.Document):
    id = me.StringField(primary_key=True)
    biosample_id = me.StringField()
    analysis_type = me.StringField(required=True)
    analysis_date = me.DateTimeField()
    
    # Extended fields for Beacon v2
    software = me.StringField()
    software_version = me.StringField()
    pipeline_name = me.StringField()
    pipeline_version = me.StringField()
    analysis_results = me.DictField()
    
    # Metadata fields
    created = me.DateTimeField(default=datetime.now)
    updated = me.DateTimeField(default=datetime.now)
    
    meta = {
        'collection': 'analyses',
        'indexes': [
            'biosample_id'
        ],
        'auto_create_index': False,  # Disable auto index creation
    }
    
    def __str__(self):
        return f"Analysis {self.id} of type {self.analysis_type}"

class Cohort(me.Document):
    id = me.StringField(primary_key=True)
    name = me.StringField(required=True)
    description = me.StringField()
    
    # Extended fields for Beacon v2
    cohort_type = me.StringField()
    cohort_size = me.IntField()
    individual_ids = me.ListField(me.StringField())
    
    # Metadata fields
    created = me.DateTimeField(default=datetime.now)
    updated = me.DateTimeField(default=datetime.now)
    
    meta = {
        'collection': 'cohorts',
        'indexes': [
            'name'
        ],
        'auto_create_index': False,  # Disable auto index creation
    }
    
    def __str__(self):
        return self.name

class VariantInDataset(me.Document):
    """Join model linking a variant to a dataset with per-individual genotype data."""
    variant = me.ReferenceField(Variant, required=True)
    dataset = me.ReferenceField(Dataset, required=True)
    individual = me.ReferenceField(Individual)
    genotype = me.StringField()
    allele_frequency = me.FloatField()

    # Metadata fields
    created = me.DateTimeField(default=datetime.now)
    updated = me.DateTimeField(default=datetime.now)

    meta = {
        'collection': 'variant_in_dataset',
        'indexes': [
            'variant',
            'dataset',
            'individual',
            {'fields': ['variant', 'dataset', 'individual'], 'unique': True},
        ],
        'auto_create_index': False,
    }

    def __str__(self):
        return f"Variant {self.variant.id} in dataset {self.dataset.id}"


class FilteringTerm(me.Document):
    id = me.StringField(primary_key=True)
    label = me.StringField(required=True)
    description = me.StringField()
    
    # Extended fields for Beacon v2
    ontology = me.StringField()  # E.g., "HP", "MONDO", "HPO", etc.
    ontology_id = me.StringField()  # The term ID in the ontology
    term_category = me.StringField()  # E.g., "phenotype", "disease", "gene", etc.
    
    # Metadata fields
    created = me.DateTimeField(default=datetime.now)
    updated = me.DateTimeField(default=datetime.now)
    
    meta = {
        'collection': 'filtering_terms',
        'indexes': [
            'ontology',
            'ontology_id'
        ],
        'auto_create_index': False,  # Disable auto index creation
    }

    def __str__(self):
        return f"{self.label} ({self.ontology}:{self.ontology_id})"


class QueryLog(me.Document):
    """Audit log of API queries served by this beacon. Best-effort write from
    QueryLogMiddleware — failures here must not break the beacon response."""
    query_type = me.StringField(required=True, max_length=50)
    query_params = me.DictField()
    response_status = me.IntField(required=True)
    response_time_ms = me.IntField(required=True)
    hits_count = me.IntField(default=0)
    client_ip = me.StringField(max_length=64)
    created = me.DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'query_logs',
        'indexes': ['created', 'query_type', '-created'],
        'auto_create_index': True,
    }
