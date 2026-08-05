#!/usr/bin/env python3
"""
VCF to Beacon v2 Transformation Tool
Converts VCF files into Beacon v2 compliant JSON format for MongoDB storage.
"""

import os
import re
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Iterator, Set, Tuple
from dataclasses import dataclass, asdict

import yaml
import pandas as pd
import numpy as np
from tqdm import tqdm
import cyvcf2

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))


@dataclass
class VariantRecord:
    """Data class for Beacon v2 variant record."""
    id: str
    assembly_id: str
    reference_name: str
    start: int
    end: int
    reference_bases: str
    alternate_bases: str
    variant_type: str
    # Datasets this variant belongs to. The API filters on `dataset_ids` to
    # attribute a hit (and its allele frequency) to a dataset, so a record
    # without it is invisible per-dataset.
    dataset_ids: List[str] = None
    annotations: List[Dict] = None
    allele_frequency: float = None
    created: str = None
    updated: str = None

    def __post_init__(self):
        if self.created is None:
            self.created = datetime.now().isoformat()
        if self.updated is None:
            self.updated = datetime.now().isoformat()
        if self.annotations is None:
            self.annotations = []
        if self.dataset_ids is None:
            self.dataset_ids = []


@dataclass
class IndividualRecord:
    """Data class for Beacon v2 individual record."""
    id: str
    sex: Optional[str] = None
    ethnicity: Optional[str] = None
    geographic_origin: Optional[str] = None
    age: Optional[int] = None
    diseases: Dict = None
    phenotypic_features: Dict = None
    created: str = None
    updated: str = None

    def __post_init__(self):
        if self.created is None:
            self.created = datetime.now().isoformat()
        if self.updated is None:
            self.updated = datetime.now().isoformat()
        if self.diseases is None:
            self.diseases = {}
        if self.phenotypic_features is None:
            self.phenotypic_features = {}


class VCFTransformer:
    """Main class for transforming VCF files to Beacon v2format."""

    # Symbolic ALT alleles (<DEL>, <DUP:TANDEM>, ...) that map onto a Beacon
    # variant type directly. Anything else symbolic is reported as generic SV
    # rather than being guessed at from allele-string lengths.
    _SYMBOLIC_TYPES = {'DEL', 'DUP', 'INS', 'INV', 'CNV'}

    # SnpEff's ANN layout, from the "VCF annotation format" spec (v1.0). Used
    # when the VCF header does not declare the field list itself.
    _DEFAULT_ANN_COLUMNS = [
        'Allele', 'Annotation', 'Annotation_Impact', 'Gene_Name', 'Gene_ID',
        'Feature_Type', 'Feature_ID', 'Transcript_BioType', 'Rank', 'HGVS.c',
        'HGVS.p', 'cDNA.pos / cDNA.length', 'CDS.pos / CDS.length',
        'AA.pos / AA.length', 'Distance', 'ERRORS / WARNINGS / INFO',
    ]

    # Column (slugified) → VariantAnnotation field, so what is written can be
    # read back through the API's ODM and matched by its annotation filters.
    _VEP_FIELD_MAP = {
        'symbol': 'gene_symbol',
        'gene_symbol': 'gene_symbol',
        'gene': 'gene_id',
        'consequence': 'molecular_consequence',
        'clin_sig': 'clinical_significance',
    }
    _SNPEFF_FIELD_MAP = {
        'gene_name': 'gene_symbol',
        'gene_id': 'gene_id',
        'annotation': 'molecular_consequence',
    }

    # An annotation with none of these carries no usable information.
    _ANNOTATION_CORE_FIELDS = ('gene_symbol', 'gene_id', 'molecular_consequence')

    def __init__(self, config_path: str = None, dataset_id: str = None):
        """Initialize the VCF transformer with configuration.

        `dataset_id` is the Beacon dataset every variant from this VCF belongs
        to. It falls back to `dataset.id` in the config file so a pipeline that
        only passes --config can still attribute its variants.
        """
        self.config = self._load_config(config_path)
        self.dataset_id = dataset_id or (self.config.get('dataset') or {}).get('id')
        self._setup_logging()
        self.stats = {
            'variants_processed': 0,
            'variants_filtered': 0,
            'variants_skipped': 0,
            'skipped_reasons': {},
            'annotations_skipped': 0,
            'individuals_found': 0,
            'errors': 0
        }
        # CSQ column order varies per VEP invocation, so it is read from the
        # VCF header rather than assumed. None means "no declared format" —
        # in which case CSQ entries are left unparsed instead of guessed.
        self._csq_columns: Optional[List[str]] = None
        self._ann_columns: List[str] = list(self._DEFAULT_ANN_COLUMNS)
        self._unparseable_sources: Set[str] = set()

    def _load_config(self, config_path: str = None) -> Dict:
        """Load configuration from YAML file."""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "settings.yaml"
        
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logging.warning(f"Config file not found: {config_path}")
            return self._default_config()

    def _default_config(self) -> Dict:
        """Return default configuration if config file not found."""
        return {
            'vcf': {
                'default_assembly': 'GRCh38',
                'quality_filters': {
                    'min_qual': 20,
                    'min_depth': 10
                }
            },
            'processing': {
                'batch_size': 1000,
                'show_progress': True
            }
        }

    def _setup_logging(self):
        """Setup logging configuration."""
        log_level = self.config.get('processing', {}).get('log_level', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def parse_vcf(self, vcf_path: str, assembly_id: str = None) -> Iterator[VariantRecord]:
        """Parse VCF file and yield variant records (no per-sample genotype extraction)."""
        if assembly_id is None:
            assembly_id = self.config['vcf']['default_assembly']

        self.logger.info(f"Starting VCF parsing: {vcf_path}")

        try:
            vcf = cyvcf2.VCF(vcf_path)
            total_variants = 0

            # Column layouts for CSQ/ANN come from this file's own header.
            self._csq_columns = self._read_format_columns(vcf, 'CSQ')
            self._ann_columns = (self._read_format_columns(vcf, 'ANN')
                                 or list(self._DEFAULT_ANN_COLUMNS))
            self._unparseable_sources = set()

            # Get sample names (individuals)
            samples = vcf.samples
            self.stats['individuals_found'] = len(samples)

            for variant in vcf:
                total_variants += 1

                # Apply quality filters
                if not self._passes_quality_filters(variant):
                    self.stats['variants_filtered'] += 1
                    continue

                # One record per ALT allele. A multi-allelic site written as a
                # single "T,G" document can never match an exact-allele query
                # and would carry ALT-1's frequency on the joined string.
                for alt_index in range(max(1, len(self._alt_alleles(variant)))):
                    record = self._create_variant_record(variant, assembly_id, alt_index)
                    if record is None:
                        continue  # unrepresentable allele — counted in stats
                    yield record
                    self.stats['variants_processed'] += 1

        except Exception as e:
            self.logger.error(f"Error parsing VCF file: {e}")
            self.stats['errors'] += 1
            raise

        self.logger.info(
            f"VCF parsing completed. Total: {total_variants}, "
            f"records emitted: {self.stats['variants_processed']}, "
            f"quality-filtered: {self.stats['variants_filtered']}, "
            f"skipped alleles: {self.stats['variants_skipped']} "
            f"{self.stats['skipped_reasons'] or ''}"
        )

    def _passes_quality_filters(self, variant) -> bool:
        """Check if variant passes quality filters."""
        quality_filters = self.config['vcf']['quality_filters']

        # Check QUAL field
        if variant.QUAL is not None and variant.QUAL < quality_filters.get('min_qual', 0):
            return False

        # Check depth (DP in INFO field). Read via INFO.get(): cyvcf2's INFO
        # object iterates as (key, value) pairs, so `'DP' in variant.INFO` is
        # always False and the depth filter never fired.
        depth = self._info_get(variant, 'DP')
        if depth is not None:
            try:
                if float(depth) < quality_filters.get('min_depth', 0):
                    return False
            except (TypeError, ValueError):
                pass

        return True

    @staticmethod
    def _info_get(variant, key: str):
        """Read one INFO field, tolerating variants without an INFO object."""
        info = getattr(variant, 'INFO', None)
        getter = getattr(info, 'get', None)
        if not callable(getter):
            return None
        try:
            return getter(key)
        except KeyError:
            return None

    @staticmethod
    def _alt_alleles(variant) -> List[str]:
        """Return the site's ALT alleles as a list of strings."""
        alt = getattr(variant, 'ALT', None)
        if alt is None:
            return []
        if isinstance(alt, (list, tuple)):
            return [str(a) for a in alt if a is not None]
        return [str(alt)]

    @staticmethod
    def _per_allele_value(value, alt_index: int):
        """Narrow a per-ALT INFO value (AF, AC, ...) to a single ALT allele.

        A sequence carries one entry per ALT; anything shorter than alt_index+1
        is treated as absent rather than mispaired with the wrong allele. A
        scalar describes only the first ALT.
        """
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return value[alt_index] if alt_index < len(value) else None
        return value if alt_index == 0 else None

    def _create_variant_record(self, variant, assembly_id: str,
                               alt_index: int = 0) -> Optional[VariantRecord]:
        """Create a VariantRecord for one ALT allele of a cyvcf2 variant.

        Returns None when the allele cannot be represented faithfully (a
        spanning-deletion `*`, or a symbolic allele whose span the VCF never
        states). Such alleles are counted in `stats['skipped_reasons']` rather
        than stored with a fabricated span.
        """
        alts = self._alt_alleles(variant)
        alt_allele = alts[alt_index] if alt_index < len(alts) else ''

        # `*` marks an allele deleted by an overlapping upstream event. It is
        # not a sequence, so it can neither be queried nor spanned.
        if alt_allele == '*':
            self._record_skip('spanning_deletion_allele')
            return None

        reference_name = self._normalize_chromosome(variant.CHROM)
        ref = variant.REF or ''
        start = variant.POS - 1  # Convert to 0-based coordinates

        # Determine variant type for this allele specifically
        variant_type = self._determine_variant_type(ref, [alt_allele])

        end = self._compute_end(variant, ref, alt_allele, start, variant_type, alt_index)
        if end is None:
            self._record_skip('symbolic_allele_without_span')
            self.logger.warning(
                f"Skipping {reference_name}:{variant.POS} {alt_allele}: symbolic "
                f"allele with neither INFO/END nor SVLEN — span is unknown"
            )
            return None

        # Natural key — unique per emitted allele, not per site
        variant_id = f"{reference_name}:{variant.POS}:{ref}:{alt_allele}"

        # Extract annotations, with AF/AC narrowed to this allele
        annotations = self._extract_annotations(variant, alt_index)

        # Aggregate allele frequency, given a queryable home (not just the blob)
        allele_frequency = self._extract_allele_frequency(variant, alt_index)

        return VariantRecord(
            id=variant_id,
            assembly_id=assembly_id,
            reference_name=reference_name,
            start=start,
            end=end,
            reference_bases=ref,
            alternate_bases=alt_allele,
            variant_type=variant_type,
            dataset_ids=[self.dataset_id] if self.dataset_id else [],
            annotations=annotations,
            allele_frequency=allele_frequency,
        )

    def _record_skip(self, reason: str):
        """Count a skipped allele under a named reason for the run summary."""
        self.stats['variants_skipped'] += 1
        reasons = self.stats.setdefault('skipped_reasons', {})
        reasons[reason] = reasons.get(reason, 0) + 1

    # ------------------------------------------------------------------
    # Chromosome naming
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_chromosome(chrom) -> str:
        """Normalise a contig name to the bare form Beacon v2 queries use.

        `chr1`/`1` → `1`, `chrX` → `X`, `chrM`/`MT` → `MT`. Source panels
        disagree on the prefix, and storing both forms forced the API into a
        `$in` that cannot use the plain `reference_name` index. Unrecognised
        contigs (scaffolds, decoys, alt loci) are returned untouched — mangling
        them would be worse than leaving them verbatim.
        """
        if chrom is None:
            return ''
        name = str(chrom).strip()
        core = name[3:] if name[:3].lower() == 'chr' else name
        upper = core.upper()
        if core.isdigit() and 1 <= int(core) <= 22:
            return str(int(core))
        if upper in ('X', 'Y'):
            return upper
        if upper in ('M', 'MT'):
            return 'MT'
        return name

    # ------------------------------------------------------------------
    # Allele typing and spans
    # ------------------------------------------------------------------

    @classmethod
    def _extract_allele_frequency(cls, variant, alt_index: int = 0) -> float:
        """Return this ALT allele's AF from the VCF INFO field as a float, or None.

        cyvcf2's INFO exposes `.get(key)`; for a multi-allelic site AF is a
        tuple/list with one entry per ALT, so it is indexed by alt_index.
        """
        af = cls._per_allele_value(cls._info_get(variant, 'AF'), alt_index)
        try:
            return float(af) if af is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _symbolic_base(alt: str) -> Optional[str]:
        """Return the base type of a symbolic ALT (`<DUP:TANDEM>` → `DUP`)."""
        if not alt or not (alt.startswith('<') and alt.endswith('>')):
            return None
        inner = alt[1:-1].strip()
        return inner.split(':')[0].strip().upper() or None

    @staticmethod
    def _is_breakend(alt: str) -> bool:
        """Detect VCF breakend notation, e.g. `A[chr2:321682[` or `]chr2:321681]T`."""
        return bool(alt) and ('[' in alt or ']' in alt)

    def _determine_variant_type(self, ref: str, alt: List[str]) -> str:
        """Determine variant type based on REF and ALT alleles.

        Symbolic and breakend alleles are classified by what they declare, not
        by string length — `<DEL>` is 5 characters and was previously recorded
        as an insertion against a 1-character REF.
        """
        if not alt or not alt[0]:
            return "unknown"

        alt_allele = str(alt[0])

        if alt_allele == '*':
            return "unknown"  # allele removed by an upstream deletion

        if self._is_breakend(alt_allele):
            return "BND"

        symbolic = self._symbolic_base(alt_allele)
        if symbolic:
            return symbolic if symbolic in self._SYMBOLIC_TYPES else "SV"

        if not ref:
            return "unknown"

        if len(ref) == len(alt_allele) == 1:
            return "SNV"  # Single Nucleotide Variant
        elif len(ref) > len(alt_allele):
            return "DEL"  # Deletion
        elif len(ref) < len(alt_allele):
            return "INS"  # Insertion
        else:
            return "COMPLEX"  # Complex variant

    def _compute_end(self, variant, ref: str, alt_allele: str, start: int,
                     variant_type: str, alt_index: int = 0) -> Optional[int]:
        """Return the 0-based, half-open end coordinate for this allele.

        `INFO/END` is authoritative when present (it is 1-based inclusive, which
        equals the 0-based exclusive end). Without it, a symbolic allele's span
        comes from SVLEN. A 10 kb `<DEL>` used to be stored as a 1 bp span, so
        no overlapping range query could ever find it.
        """
        end_value = self._info_get(variant, 'END')
        if end_value is not None:
            try:
                end = int(end_value)
                if end > start:
                    return end
                self.logger.warning(
                    f"Ignoring INFO/END={end_value} at {variant.CHROM}:{variant.POS}: "
                    f"not past the variant start"
                )
            except (TypeError, ValueError):
                self.logger.warning(f"Ignoring non-integer INFO/END={end_value!r}")

        if self._symbolic_base(alt_allele) is None:
            # Sequence allele (including breakends): REF spans the reference.
            return start + max(1, len(ref))

        if variant_type == 'INS':
            # A symbolic insertion adds sequence without consuming reference.
            return start + max(1, len(ref))

        svlen = self._per_allele_value(self._info_get(variant, 'SVLEN'), alt_index)
        try:
            span = abs(int(svlen)) if svlen is not None else 0
        except (TypeError, ValueError):
            span = 0
        if span:
            return start + span

        return None

    def _extract_annotations(self, variant, alt_index: int = 0) -> List[Dict]:
        """Extract variant annotations from INFO field for one ALT allele.

        Every emitted annotation uses the API's `VariantAnnotation` shape
        (gene_id / gene_symbol / molecular_consequence / clinical_significance
        / additional_annotations), so the records can be read back through the
        ODM and matched by the `annotations__gene_symbol` filters.
        """
        annotations = []

        info = getattr(variant, 'INFO', None)
        if info is None or not callable(getattr(info, 'get', None)):
            return annotations

        alts = self._alt_alleles(variant)
        alt_allele = alts[alt_index] if alt_index < len(alts) else ''
        ref = getattr(variant, 'REF', '') or ''

        # VEP (CSQ) and SnpEff (ANN). These were read with `'CSQ' in info`,
        # which is always False on a cyvcf2 INFO object — it iterates as
        # (key, value) tuples — so no annotation was ever extracted.
        annotations.extend(self._parse_vep_annotations(
            self._info_get(variant, 'CSQ'), ref, alt_allele, alt_index, len(alts)))
        annotations.extend(self._parse_snpeff_annotations(
            self._info_get(variant, 'ANN'), ref, alt_allele, alt_index, len(alts)))

        # Basic INFO fields. AF and AC are per-ALT, so they are narrowed to the
        # allele this record describes; GENE and AN are site-level.
        extra = {'source': 'INFO'}
        gene_symbol = None
        for field in ['GENE', 'AF', 'AC', 'AN']:
            val = self._info_get(variant, field)
            if field in ('AF', 'AC'):
                val = self._per_allele_value(val, alt_index)
            if val is None:
                continue
            if field == 'GENE':
                gene_symbol = str(val)
            else:
                extra[field.lower()] = val

        if gene_symbol or len(extra) > 1:
            basic = {'additional_annotations': extra}
            if gene_symbol:
                basic['gene_symbol'] = gene_symbol
            annotations.append(basic)

        return annotations

    # ------------------------------------------------------------------
    # VEP / SnpEff annotation parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _slugify_column(name: str) -> str:
        """`HGVS.c` → `hgvs_c`, `cDNA.pos / cDNA.length` → `cdna_pos_cdna_length`."""
        return re.sub(r'[^0-9a-z]+', '_', str(name).lower()).strip('_')

    @staticmethod
    def _split_annotation_entries(value) -> List[str]:
        """Split a CSQ/ANN INFO value into its per-transcript entries.

        cyvcf2 hands back one comma-joined string for a `Number=.` String field;
        other producers hand back a list. Both are accepted.
        """
        if value is None:
            return []
        items = value if isinstance(value, (list, tuple)) else [value]
        entries = []
        for item in items:
            for part in str(item).split(','):
                part = part.strip()
                if part:
                    entries.append(part)
        return entries

    def _read_format_columns(self, vcf, key: str) -> Optional[List[str]]:
        """Read the pipe-delimited column layout an INFO field declares.

        VEP writes `Format: Allele|Consequence|IMPACT|SYMBOL|Gene|...` and
        SnpEff writes `Functional annotations: 'Allele | Annotation | ...'`.
        The column order varies per invocation, so it is never assumed.
        """
        description = None

        getter = getattr(vcf, 'get_header_type', None)
        if callable(getter):
            try:
                header = getter(key)
            except (KeyError, TypeError, ValueError):
                header = None
            if isinstance(header, dict):
                description = header.get('Description')

        if not isinstance(description, str):
            raw = getattr(vcf, 'raw_header', None)
            if isinstance(raw, str):
                match = re.search(rf'^##INFO=<ID={re.escape(key)},.*$', raw, re.MULTILINE)
                description = match.group(0) if match else None

        if not isinstance(description, str):
            return None

        match = (re.search(r"Format:\s*([^\"'>]+)", description)
                 or re.search(r"annotations:\s*'([^']+)'", description, re.IGNORECASE))
        if not match:
            return None

        columns = [c.strip() for c in match.group(1).split('|')]
        columns = [c for c in columns if c]
        return columns or None

    def _parse_annotation_entries(self, raw_value, columns: Optional[List[str]],
                                  field_map: Dict[str, str], source: str,
                                  ref: str, alt_allele: str,
                                  alt_index: int, n_alts: int) -> List[Dict]:
        """Map pipe-delimited annotation entries onto VariantAnnotation fields.

        An entry is dropped — never guessed at — when the column layout is
        unknown, when it carries more fields than the layout declares (which
        would shift every value onto the wrong column), or when it cannot be
        attributed to this ALT allele at a multi-allelic site. A wrong gene
        symbol is worse than a missing one.
        """
        entries = self._split_annotation_entries(raw_value)
        if not entries:
            return []

        if not columns:
            self.stats['annotations_skipped'] += len(entries)
            if source not in self._unparseable_sources:
                self._unparseable_sources.add(source)
                self.logger.warning(
                    f"{source} annotations present but no column format declared in "
                    f"the VCF header — they are left unparsed rather than guessed at"
                )
            return []

        slugs = [self._slugify_column(c) for c in columns]
        candidates = self._allele_candidates(ref, alt_allele)
        annotations = []

        for entry in entries:
            parts = entry.split('|')
            if len(parts) > len(slugs):
                self.stats['annotations_skipped'] += 1
                continue

            values = dict(zip(slugs, [p.strip() for p in parts]))
            if not self._entry_applies(values, candidates, alt_index, n_alts):
                self.stats['annotations_skipped'] += 1
                continue

            annotation = {}
            extra = {'source': source}
            for slug, value in values.items():
                if not value:
                    continue
                target = field_map.get(slug)
                if target:
                    annotation[target] = value
                else:
                    extra[slug] = value

            if not any(annotation.get(f) for f in self._ANNOTATION_CORE_FIELDS):
                self.stats['annotations_skipped'] += 1
                continue

            annotation['additional_annotations'] = extra
            annotations.append(annotation)

        return annotations

    @staticmethod
    def _allele_candidates(ref: str, alt_allele: str) -> Set[str]:
        """Forms an annotator may use to name this ALT allele.

        VEP writes the minimal representation: with REF=`CA` ALT=`C` the CSQ
        allele is `-`, and with REF=`C` ALT=`CA` it is `A`.
        """
        if not alt_allele:
            return set()
        candidates = {alt_allele.upper()}
        if ref and alt_allele[0].upper() == ref[0].upper() and (len(ref) > 1 or len(alt_allele) > 1):
            candidates.add(alt_allele[1:].upper() or '-')
        symbolic = alt_allele[1:-1] if alt_allele.startswith('<') and alt_allele.endswith('>') else None
        if symbolic:
            candidates.add(symbolic.upper())
        return candidates

    @staticmethod
    def _entry_applies(values: Dict[str, str], candidates: Set[str],
                       alt_index: int, n_alts: int) -> bool:
        """Decide whether one annotation entry describes the ALT being emitted.

        On a bi-allelic site there is only one ALT to attribute to. On a
        multi-allelic site the entry must say which allele it means — via
        VEP's ALLELE_NUM or a matching allele column — otherwise it is dropped.
        """
        if n_alts <= 1:
            return True

        allele_num = values.get('allele_num')
        if allele_num:
            try:
                return int(allele_num) == alt_index + 1
            except (TypeError, ValueError):
                pass

        allele = values.get('allele')
        if allele:
            return allele.upper() in candidates

        return False

    def _parse_vep_annotations(self, csq_data, ref: str = '', alt_allele: str = '',
                               alt_index: int = 0, n_alts: int = 1) -> List[Dict]:
        """Parse VEP CSQ annotations using the header-declared column order."""
        return self._parse_annotation_entries(
            csq_data, self._csq_columns, self._VEP_FIELD_MAP, 'VEP',
            ref, alt_allele, alt_index, n_alts)

    def _parse_snpeff_annotations(self, ann_data, ref: str = '', alt_allele: str = '',
                                  alt_index: int = 0, n_alts: int = 1) -> List[Dict]:
        """Parse SnpEff ANN annotations (header layout, else the documented one)."""
        return self._parse_annotation_entries(
            ann_data, self._ann_columns, self._SNPEFF_FIELD_MAP, 'SnpEff',
            ref, alt_allele, alt_index, n_alts)

    def _extract_genotype_info(self, variant, sample_idx: int) -> Optional[Dict]:
        """Extract genotype information for a sample."""
        try:
            gt = variant.genotypes[sample_idx]
            
            # Skip if no genotype
            if gt[0] == -1 and gt[1] == -1:
                return None
                
            genotype_info = {
                'alleles': [gt[0], gt[1]],
                'phased': bool(gt[2])
            }
            
            # Extract FORMAT fields (cyvcf2: variant.format(field) returns numpy array)
            try:
                dp = variant.format('DP')
                if dp is not None:
                    genotype_info['depth'] = int(dp[sample_idx][0])
            except (KeyError, IndexError):
                pass
            try:
                gq = variant.format('GQ')
                if gq is not None:
                    genotype_info['quality'] = int(gq[sample_idx][0])
            except (KeyError, IndexError):
                pass
            try:
                ad = variant.format('AD')
                if ad is not None:
                    genotype_info['allelic_depths'] = ad[sample_idx].tolist()
            except (KeyError, IndexError):
                pass
                    
            return genotype_info
            
        except (IndexError, KeyError) as e:
            self.logger.warning(f"Error extracting genotype info: {e}")
            return None

    def create_individuals_from_vcf(self, vcf_path: str, metadata_file: str = None) -> List[IndividualRecord]:
        """Create individual records from VCF samples."""
        individuals = []
        
        try:
            vcf = cyvcf2.VCF(vcf_path)
            samples = vcf.samples
            
            # Load additional metadata if provided
            metadata = {}
            if metadata_file and os.path.exists(metadata_file):
                metadata = self._load_individual_metadata(metadata_file)
            
            for sample_id in samples:
                individual_data = metadata.get(sample_id, {})
                
                individual = IndividualRecord(
                    id=sample_id,
                    sex=individual_data.get('sex'),
                    ethnicity=individual_data.get('ethnicity'),
                    geographic_origin=individual_data.get('geographic_origin'),
                    age=individual_data.get('age')
                )
                
                individuals.append(individual)
                
        except Exception as e:
            self.logger.error(f"Error creating individuals from VCF: {e}")
            raise
            
        return individuals

    def _load_individual_metadata(self, metadata_file: str) -> Dict:
        """Load additional individual metadata from file."""
        try:
            if metadata_file.endswith('.csv'):
                df = pd.read_csv(metadata_file)
            elif metadata_file.endswith('.tsv'):
                df = pd.read_csv(metadata_file, sep='\t')
            elif metadata_file.endswith('.xlsx'):
                df = pd.read_excel(metadata_file)
            else:
                raise ValueError(f"Unsupported metadata file format: {metadata_file}")
                
            # Convert to dictionary with sample_id as key
            metadata = {}
            for _, row in df.iterrows():
                sample_id = row.get('sample_id') or row.get('individual_id') or row.get('id')
                if sample_id:
                    metadata[sample_id] = row.to_dict()
                    
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error loading metadata file: {e}")
            return {}

    def transform_vcf_to_beacon(self, vcf_path: str, output_dir: str, 
                              assembly_id: str = None, metadata_file: str = None) -> Dict:
        """Transform VCF file to Beacon v2 format."""
        self.logger.info(f"Starting VCF transformation: {vcf_path}")
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Process VCF — variant-level only (no per-sample genotypes for Boolean mode)
        variants = []
        batch_size = self.config['processing']['batch_size']
        show_progress = self.config['processing']['show_progress']

        with tqdm(desc="Processing variants", disable=not show_progress) as pbar:
            for variant_record in self.parse_vcf(vcf_path, assembly_id):
                variants.append(asdict(variant_record))
                pbar.update(1)

                if len(variants) >= batch_size:
                    self._write_batch(variants, output_path / "variants_batch.jsonl")
                    variants = []

        if variants:
            self._write_batch(variants, output_path / "variants_batch.jsonl")

        # Create individuals list from VCF header (no genotype data)
        individuals = self.create_individuals_from_vcf(vcf_path, metadata_file)
        self._write_json_file([asdict(ind) for ind in individuals], output_path / "individuals.json")

        # Write empty genotypes file (placeholder for Secure mode later)
        self._write_json_file([], output_path / "variant_genotypes.json")
        
        # Generate summary
        summary = {
            'transformation_date': datetime.now().isoformat(),
            'input_file': str(vcf_path),
            'output_directory': str(output_path),
            'assembly_id': assembly_id or self.config['vcf']['default_assembly'],
            'dataset_id': self.dataset_id,
            'statistics': self.stats,
            'files_created': [
                'variants_batch.jsonl',
                'individuals.json',
                'variant_genotypes.json'
            ]
        }
        
        self._write_json_file(summary, output_path / "transformation_summary.json")
        
        self.logger.info(f"Transformation completed. Output written to: {output_path}")
        return summary

    def _write_batch(self, data: List[Dict], file_path: Path):
        """Write data batch to JSONL file."""
        with open(file_path, 'a') as f:
            for record in data:
                f.write(json.dumps(record) + '\n')

    def _write_json_file(self, data: any, file_path: Path):
        """Write data to JSON file."""
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)


def main():
    """Main function for command-line interface."""
    parser = argparse.ArgumentParser(
        description="Transform VCF files to Beacon v2 format"
    )
    
    parser.add_argument(
        'vcf_file',
        help='Path to input VCF file'
    )
    
    parser.add_argument(
        '-o', '--output',
        required=True,
        help='Output directory for transformed data'
    )
    
    parser.add_argument(
        '-a', '--assembly',
        default='GRCh38',
        help='Genome assembly ID (default: GRCh38)'
    )
    
    parser.add_argument(
        '-m', '--metadata',
        help='Path to individual metadata file (CSV/TSV/XLSX)'
    )

    parser.add_argument(
        '-d', '--dataset-id',
        help='Beacon dataset ID these variants belong to '
             '(defaults to dataset.id in the config file)'
    )
    
    parser.add_argument(
        '-c', '--config',
        help='Path to configuration file'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Set up logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    
    # Initialize transformer
    transformer = VCFTransformer(args.config, dataset_id=args.dataset_id)
    
    try:
        # Transform VCF
        summary = transformer.transform_vcf_to_beacon(
            vcf_path=args.vcf_file,
            output_dir=args.output,
            assembly_id=args.assembly,
            metadata_file=args.metadata
        )
        
        print("VCF transformation completed successfully!")
        print(f"Statistics: {summary['statistics']}")
        print(f"Output files: {summary['files_created']}")
        
    except Exception as e:
        print(f"Error during transformation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 