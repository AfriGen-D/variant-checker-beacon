#!/usr/bin/env python3
"""Boolean-mode streaming VCF → variants JSONL.

Bypasses the variant_individual_map / variant_genotypes accumulator (OOM source
in vcf_to_beacon.py) since boolean mode only needs the `variants` collection.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vcf_transform.vcf_to_beacon import VCFTransformer  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("vcf_file")
    p.add_argument("--output", required=True, help="output dir for variants_batch.jsonl")
    p.add_argument("--assembly", default="GRCh38")
    p.add_argument("--config", default=None)
    p.add_argument("--contigs", nargs="*", default=None,
                   help="optional list of contigs to restrict to (e.g. chr5 chr6 ... chrM)")
    p.add_argument("--report-every", type=int, default=100000)
    p.add_argument("--append", action="store_true",
                   help="append to existing variants_batch.jsonl (default: error if file exists)")
    args = p.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "variants_batch.jsonl"
    if out_file.exists() and not args.append:
        raise SystemExit(
            f"{out_file} already exists; pass --append to add to it or remove the file first"
        )
    mode = "a" if args.append else "w"

    t = VCFTransformer(args.config)
    import cyvcf2
    vcf = cyvcf2.VCF(args.vcf_file)

    contigs = args.contigs or vcf.seqnames
    n_total = 0
    n_kept = 0
    n_skipped_filter = 0

    started = datetime.now()
    print(f"[{started.isoformat(timespec='seconds')}] streaming → {out_file}")
    print(f"contigs: {contigs}")

    with out_file.open(mode) as fh:
        for contig in contigs:
            n_in_contig = 0
            try:
                contig_iter = vcf(contig)
            except Exception as e:
                print(f"  {contig}: skipped ({e})")
                continue
            for variant in contig_iter:
                n_total += 1
                n_in_contig += 1
                if not t._passes_quality_filters(variant):
                    n_skipped_filter += 1
                    continue
                record = t._create_variant_record(variant, args.assembly)
                doc = {
                    "id": record.id,
                    "assembly_id": record.assembly_id,
                    "reference_name": record.reference_name,
                    "start": record.start,
                    "end": record.end,
                    "reference_bases": record.reference_bases,
                    "alternate_bases": record.alternate_bases,
                    "variant_type": record.variant_type,
                    "annotations": record.annotations,
                    "created": record.created,
                    "updated": record.updated,
                }
                fh.write(json.dumps(doc) + "\n")
                n_kept += 1
                if n_kept % args.report_every == 0:
                    elapsed = (datetime.now() - started).total_seconds()
                    rate = n_kept / max(elapsed, 1)
                    print(f"  {contig}: kept={n_kept:,} total={n_total:,} "
                          f"elapsed={elapsed:.0f}s rate={rate:.0f}/s")
            print(f"  {contig}: contig done ({n_in_contig:,} variants)")

    elapsed = (datetime.now() - started).total_seconds()
    print(f"[{datetime.now().isoformat(timespec='seconds')}] done")
    print(f"  total seen={n_total:,} kept={n_kept:,} filtered={n_skipped_filter:,} elapsed={elapsed:.0f}s")


if __name__ == "__main__":
    main()

