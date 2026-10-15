#!/usr/bin/env bash
# Smoke test for the tools image (nextflow/docker/Dockerfile.tools).
#
# Runs INSIDE the image, against the repository's own test fixtures, and walks the
# same path the ILIFU guide does: transform a VCF, validate the output with
# --strict, transform phenotypes, validate those, and check the importer starts.
# Every validate_json.py call exits non-zero on invalid input, so a regression in
# the image or in the transformers fails this script.
#
# It then runs the example data in examples/ (the data the guide's step-by-step
# uses) and checks the exact numbers examples/README.md promises, so the guide's
# example cannot silently stop working.
#
# From a checkout, after building the image as beacon-tools:ci:
#
#   docker run --rm \
#     -v "$PWD/scripts/smoke_tools_image.sh:/smoke.sh:ro" \
#     -v "$PWD/afrigend-beacon2-tools/tests/fixtures:/fixtures:ro" \
#     -v "$PWD/examples:/examples:ro" \
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

echo "--- the example data: the dataset file, then the numbers in examples/README.md"
EX=/examples
[ -f "$EX/1000G_chr22_subset.vcf.gz" ] || { echo "FAIL: $EX is not mounted (see the usage above)"; exit 1; }
test "$(python "$TOOLS/data_import/dataset_file.py" "$EX/dataset.yaml" --get id)" = "EXAMPLE_1000G_CHR22"
python "$TOOLS/vcf_transform/vcf_to_beacon.py" "$EX/1000G_chr22_subset.vcf.gz" \
    --output "$OUT/example/vcf" --assembly GRCh38 --dataset-id EXAMPLE_1000G_CHR22 \
    --config "$TOOLS/config/settings.yaml" > /dev/null
python "$TOOLS/validation/validate_json.py" "$OUT/example/vcf/variants_batch.jsonl" \
    --schema-type variant --strict
python "$TOOLS/validation/validate_json.py" "$OUT/example/vcf/individuals.json" \
    --schema-type individual --strict
python "$TOOLS/phenotype_transform/phenotype_to_beacon.py" "$EX/phenotypes_example.csv" \
    --output "$OUT/example/pheno" --individuals "$OUT/example/vcf/individuals.json" \
    --config "$TOOLS/config/settings.yaml" > /dev/null
python "$TOOLS/validation/validate_json.py" "$OUT/example/pheno/phenotypes.json" \
    --schema-type phenotype --strict
python - "$OUT/example" <<'PYEOF'
import json, sys
d = sys.argv[1]
variants = [json.loads(l) for l in open(d + "/vcf/variants_batch.jsonl")]
individuals = json.load(open(d + "/vcf/individuals.json"))
phenotypes = json.load(open(d + "/pheno/phenotypes.json"))
diseases = json.load(open(d + "/pheno/diseases.json"))
got = (len(variants), len(individuals), len(phenotypes), len(diseases))
assert got == (4231, 9, 9, 3), f"example data counts changed: {got}, expected (4231, 9, 9, 3)"
assert all(v["dataset_ids"] == ["EXAMPLE_1000G_CHR22"] for v in variants), "dataset id not on every variant"
print("example data: 4231 variants, 9 individuals, 9 phenotypes, 3 diseases, dataset id on every variant")
PYEOF

echo "--- the importer starts"
python "$TOOLS/data_import/import_to_mongo.py" --help > /dev/null

echo "smoke test passed"
