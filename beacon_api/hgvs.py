"""Parse a Beacon v2 ``genomicAlleleShortForm`` (HGVS g. substitution) (G7b).

Standalone (no Django) like ``unsupported_params.py``. NOT wired into any view
yet: the parameter is still refused until a query path uses this and a
production positive control (rs334, ``NC_000011.10:g.5227002T>A``) passes.

Fail closed: only single-base substitutions on a known RefSeq chromosome
accession are accepted. An unknown accession version raises rather than
guessing an assembly, because a wrong assembly gives a confident wrong answer.
HGVS positions are 1-based; the stored ``start`` is 0-based.
"""
import re

#: RefSeq NC_ chromosome number -> (GRCh37 version, GRCh38 version).
#: GRCh38 is GRCh37 + 1 for every primary chromosome.
_GRCH37_VERSIONS = {
    1: 10, 2: 11, 3: 11, 4: 11, 5: 9, 6: 11, 7: 13, 8: 10, 9: 11, 10: 10,
    11: 9, 12: 11, 13: 10, 14: 8, 15: 9, 16: 9, 17: 10, 18: 9, 19: 9,
    20: 10, 21: 8, 22: 10, 23: 10, 24: 9,
}
_NAMES = {23: 'X', 24: 'Y'}

_PATTERN = re.compile(r'^NC_0000(\d\d)\.(\d+):g\.(\d+)([ACGT])>([ACGT])$', re.IGNORECASE)


class HgvsError(ValueError):
    """The string is not a genomic substitution this beacon can answer."""


def parse_genomic_allele_short_form(value):
    if not isinstance(value, str) or not value.strip():
        raise HgvsError('genomicAlleleShortForm must be a non-empty string')
    match = _PATTERN.match(value.strip())
    if not match:
        raise HgvsError('only HGVS g. single-base substitutions on an NC_ accession are supported')
    chrom, version, pos, ref, alt = match.groups()
    chrom, version, pos = int(chrom), int(version), int(pos)
    ref, alt = ref.upper(), alt.upper()
    if chrom not in _GRCH37_VERSIONS:
        raise HgvsError(f'unknown chromosome accession NC_0000{chrom:02d}')
    if version == _GRCH37_VERSIONS[chrom]:
        assembly = 'GRCh37'
    elif version == _GRCH37_VERSIONS[chrom] + 1:
        assembly = 'GRCh38'
    else:
        raise HgvsError(f'accession version .{version} matches no supported assembly')
    if pos < 1:
        raise HgvsError('HGVS positions are 1-based; 0 is not a position')
    if ref == alt:
        raise HgvsError('reference and alternate bases are identical')
    return {
        'assemblyId': assembly,
        'referenceName': _NAMES.get(chrom, str(chrom)),
        'start': pos - 1,
        'referenceBases': ref,
        'alternateBases': alt,
    }


#: The request key the Beacon v2 spec uses for an HGVS allele.
KEY = 'genomicAlleleShortForm'

#: Locus fields the HGVS string already fixes; sending both is ambiguous.
_LOCUS_FIELDS = ('referenceName', 'chromosome', 'start', 'end', 'position',
                 'referenceBases', 'alternateBases')


def expand_genomic_allele_short_form(params):
    """Return a copy of `params` with ``genomicAlleleShortForm`` replaced by the
    explicit query fields (string values, as from a query string).

    Refuses a request that also sets a locus field, or an ``assemblyId`` that
    disagrees with the accession: guessing which one the caller meant would
    answer a question they may not have asked."""
    if KEY not in params:
        return params
    clashes = [name for name in _LOCUS_FIELDS if name in params]
    if clashes:
        raise HgvsError(
            f'{KEY} already fixes the locus; do not also send {", ".join(clashes)}')
    parsed = parse_genomic_allele_short_form(params[KEY])
    asked = params.get('assemblyId')
    if asked is not None and asked != parsed['assemblyId']:
        raise HgvsError(
            f'assemblyId {str(asked)[:40]} disagrees with the accession, which is {parsed["assemblyId"]}')
    expanded = {k: v for k, v in params.items() if k != KEY}
    expanded.update({k: str(v) for k, v in parsed.items()})
    return expanded
