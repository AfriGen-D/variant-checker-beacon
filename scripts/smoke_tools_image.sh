#!/usr/bin/env bash
# Smoke test for the tools image (nextflow/docker/Dockerfile.tools).
#
# Runs INSIDE the image, against the repository's own test fixtures, and walks the
# same path the ILIFU guide does: transform a VCF, validate the output with
# --strict, transform phenotypes, validate those, and check the importer starts.
# Every validate_json.py call exits non-zero on invalid input, so a regression in
# the image or in the transformers fails this script.
#
# From a checkout, after building the image as beacon-tools:ci:
#
#   docker run --rm \
#     -v "$PWD/scripts/smoke_tools_image.sh:/smoke.sh:ro" \
#     -v "$PWD/afrigend-beacon2-tools/tests/fixtures:/fixtures:ro" \
#     --entrypoint bash beacon-tools:ci /smoke.sh
set -euo pipefail

TOOLS=/opt/beacon-tools
FIXTURES=/fixtures
OUT=$(mktemp -d)

echo "bcftools: $(bcftools --version | head -1)"
python -c "import cyvcf2, pandas, numpy, yaml, jsonschema, pymongo, pronto; print('python imports ok')"

echo "--- transform the fixture VCF"
python "$TOOLS/vcf_transform/vcf_to_beacon.py" "$FIXTURES/vcf/sample_multi.vcf" \
    --output "$OUT/vcf" --assembly GRCh38 --config "$TOOLS/config/settings.yaml" > /dev/null

echo "--- validate variants and individuals (no --metadata, so unknown fields must be absent)"
python "$TOOLS/validation/validate_json.py" "$OUT/vcf/variants_batch.jsonl" \
    --schema-type variant --strict
python "$TOOLS/validation/validate_json.py" "$OUT/vcf/individuals.json" \
    --schema-type individual --strict

echo "--- transform and validate the fixture phenotypes"
python "$TOOLS/phenotype_transform/phenotype_to_beacon.py" "$FIXTURES/phenotype/phenotypes_standard.csv" \
    --output "$OUT/pheno" --individuals "$OUT/vcf/individuals.json" \
    --config "$TOOLS/config/settings.yaml" > /dev/null
python "$TOOLS/validation/validate_json.py" "$OUT/pheno/phenotypes.json" \
    --schema-type phenotype --strict

echo "--- the importer starts"
python "$TOOLS/data_import/import_to_mongo.py" --help > /dev/null

echo "smoke test passed"
