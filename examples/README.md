# Example data

A small, public data set to try the
[ILIFU loading guide](../docs/ILIFU_DATA_LOADING_GUIDE.md) end to end before using
your own files. Everything here is tiny (the VCF is 67 KB), so a run takes
seconds.

| File | What it is |
| --- | --- |
| `1000G_chr22_subset.vcf.gz` | 4,231 variants, 9 people, GRCh38 |
| `phenotypes_example.csv` | **Synthetic** phenotypes and diseases |
| `dataset.yaml` | The dataset description (`EXAMPLE_1000G_CHR22`) |

## Where the data comes from

The `.tbi` file is the VCF's index. The VCF is a subset of the 1000 Genomes
Project phase 3 callset, GRCh38 (file name below, IGSR). 1000 Genomes data is
open: see the [IGSR data use
statement](https://www.internationalgenome.org/data) and cite *The 1000 Genomes
Project Consortium, "A global reference for human genetic variation", Nature
526:68-74 (2015)*.

Source file: `ALL.chr22.shapeit2_integrated_v1a.GRCh38.20181129.phased.vcf.gz`

It was cut with bcftools, and the command is recorded in the VCF header:

```bash
bcftools view -r chr22:16000000-17000000 -S samples.txt -c1 -Oz \
    -o 1000G_chr22_subset.vcf.gz \
    ALL.chr22.shapeit2_integrated_v1a.GRCh38.20181129.phased.vcf.gz
bcftools index -t 1000G_chr22_subset.vcf.gz
```

where `samples.txt` lists `NA18486 NA18488 NA18489 NA18499 NA19017 NA19019
NA19020 HG02922 HG02923`, and `-c1` keeps only sites that vary in those nine.

**`phenotypes_example.csv` is made up.** 1000 Genomes has no clinical data, so the
phenotype and disease rows were invented to exercise the phenotype transformer.
They describe no real person. Do not cite them or load them into a Beacon that
real users query.

## Use it

Run the whole pipeline, stopping before the database import:

```bash
./scripts/run_ilifu_pipeline.sh examples/1000G_chr22_subset.vcf.gz \
    --dataset-file examples/dataset.yaml \
    --phenotypes examples/phenotypes_example.csv \
    --container /cbio/users/$USER/beacon-tools.sif \
    --skip-import
```

Or follow the guide's step-by-step section, which uses these files.

## What a correct run gives

| Step | Expected |
| --- | --- |
| Transform VCF | 4,231 variants processed, 9 individuals, 0 errors |
| Transform phenotypes | 9 phenotypes, 3 diseases |
| Validate (`--strict`) | variants, individuals, phenotypes: PASS, 0 errors |
| Dataset id | `EXAMPLE_1000G_CHR22` on every variant |

CI runs this same data through the tools image on every change
(`scripts/smoke_tools_image.sh`), so it cannot silently stop working.
