"""
Check that allele frequencies are extracted from a real VCF.

The gate before an allele-frequency reload (docs/AF_RELOAD_RUNBOOK.md, Step 0):
read the first records of a VCF, run the transformer's OWN extraction on each, and
report how many came out with a frequency. No database and no pipeline.

It calls ``VCFTransformer._extract_allele_frequency`` rather than a copy of it. An
earlier version of this check re-implemented the logic and said it was
"identical"; the real function later became per-ALT, the copy kept reading only
the first value, and the check could pass while the transformer lost frequencies.

A multi-allelic site passes only if EVERY ALT has a frequency, because that is
what the transformer needs to write one record per ALT.

    python validate_af_extraction.py /path/to/panel.vcf.gz [--limit 1000]

Exit status: 0 when every checked record has a frequency, 1 otherwise, and 1 for
a VCF with no records (an empty file is not a pass).
"""
import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Iterable

# Run as `python path/to/validate_af_extraction.py` the package root is not on
# the path (the container sets PYTHONPATH, a plain environment does not).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vcf_transform.vcf_to_beacon import VCFTransformer  # noqa: E402


def count_allele_frequencies(variants: Iterable[Any], limit: int) -> Dict[str, Any]:
    """Run the real extraction over the first ``limit`` variants."""
    checked = with_af = 0
    examples = []
    for variant in variants:
        if checked >= limit:
            break
        alts = VCFTransformer._alt_alleles(variant)
        freqs = [VCFTransformer._extract_allele_frequency(variant, i) for i in range(len(alts) or 1)]
        checked += 1
        if all(f is not None for f in freqs):
            with_af += 1
        if len(examples) < 5:
            examples.append(
                f"{variant.CHROM}:{variant.POS} {variant.REF}>{','.join(alts) or '.'} "
                f"allele_frequency={freqs[0] if len(freqs) == 1 else freqs}"
            )
    return {"checked": checked, "with_af": with_af, "examples": examples}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check allele-frequency extraction on a real VCF.")
    parser.add_argument("vcf", help="path to a .vcf.gz or .bcf")
    parser.add_argument("--limit", type=int, default=1000, help="records to check (default 1000)")
    args = parser.parse_args(argv)

    if not Path(args.vcf).is_file():
        print(f"ERROR: VCF not found: {args.vcf}", file=sys.stderr)
        return 2
    try:
        import cyvcf2
    except ImportError:
        print("ERROR: cyvcf2 is not available; run this inside the beacon-tools container", file=sys.stderr)
        return 2

    result = count_allele_frequencies(cyvcf2.VCF(args.vcf), args.limit)
    for line in result["examples"]:
        print(f"  {line}")
    checked, with_af = result["checked"], result["with_af"]
    print(f"\nRESULT: {with_af}/{checked} of the first records have a non-null allele_frequency")
    if checked == 0:
        print("CHECK - no records were read, so nothing was verified")
        return 1
    if with_af == checked:
        print("PASS - allele-frequency extraction works on this data")
        return 0
    print("CHECK - some records lacked a frequency")
    return 1


if __name__ == "__main__":
    sys.exit(main())
