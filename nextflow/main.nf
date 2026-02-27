#!/usr/bin/env nextflow
nextflow.enable.dsl = 2

// ──────────────────────────────────────────────────────────────────────────────
// AfriGend Beacon v2 — Data Loading Pipeline
// Transforms H3Africa VCF/phenotype data → validates → imports to MongoDB
// ──────────────────────────────────────────────────────────────────────────────

// -- Module imports --
include { VCF_TRANSFORM                          } from './modules/vcf_transform'
include { PHENOTYPE_TRANSFORM                    } from './modules/phenotype_transform'
include { VALIDATE_VARIANTS                      } from './modules/validate'
include { VALIDATE_INDIVIDUALS                   } from './modules/validate'
include { VALIDATE_PHENOTYPES                    } from './modules/validate'
include { IMPORT_TO_MONGO as IMPORT_VARIANTS     } from './modules/import_mongo'
include { IMPORT_TO_MONGO as IMPORT_INDIVIDUALS  } from './modules/import_mongo'
include { IMPORT_TO_MONGO as IMPORT_PHENOTYPES   } from './modules/import_mongo'
include { FLUSH_REDIS_CACHE                      } from './modules/import_mongo'

// ──────────────────────────────────────────────────────────────────────────────
// Sub-workflows
// ──────────────────────────────────────────────────────────────────────────────

workflow TRANSFORM_VALIDATE_VCF {
    take:
    vcf_input  // tuple(dataset_name, vcf_file, metadata_file)

    main:
    VCF_TRANSFORM(vcf_input)
    VALIDATE_VARIANTS(VCF_TRANSFORM.out.variants)
    VALIDATE_INDIVIDUALS(VCF_TRANSFORM.out.individuals)

    emit:
    variants    = VALIDATE_VARIANTS.out.validated
    individuals = VALIDATE_INDIVIDUALS.out.validated
    genotypes   = VCF_TRANSFORM.out.genotypes
    summary     = VCF_TRANSFORM.out.summary
}

workflow TRANSFORM_VALIDATE_PHENOTYPES {
    take:
    pheno_input  // tuple(dataset_name, phenotype_file, individuals_json)

    main:
    PHENOTYPE_TRANSFORM(pheno_input)
    VALIDATE_PHENOTYPES(PHENOTYPE_TRANSFORM.out.phenotypes)

    emit:
    phenotypes          = VALIDATE_PHENOTYPES.out.validated
    diseases            = PHENOTYPE_TRANSFORM.out.diseases
    individuals_updated = PHENOTYPE_TRANSFORM.out.individuals_updated
}

workflow IMPORT_DATA {
    take:
    variants_ch     // tuple(dataset_name, variants.jsonl)
    individuals_ch  // tuple(dataset_name, individuals.json)
    phenotypes_ch   // tuple(dataset_name, phenotypes.json) — may be empty

    main:
    // Add collection name to each channel
    variants_import    = variants_ch.map    { ds, f -> [ds, f, 'variants'] }
    individuals_import = individuals_ch.map { ds, f -> [ds, f, 'individuals'] }
    phenotypes_import  = phenotypes_ch.map  { ds, f -> [ds, f, 'phenotypes'] }

    IMPORT_VARIANTS(variants_import)
    IMPORT_INDIVIDUALS(individuals_import)
    IMPORT_PHENOTYPES(phenotypes_import)

    // Wait for all imports, then flush cache
    all_done = IMPORT_VARIANTS.out.mix(
        IMPORT_INDIVIDUALS.out,
        IMPORT_PHENOTYPES.out
    ).collect()

    FLUSH_REDIS_CACHE(all_done)
}

// ──────────────────────────────────────────────────────────────────────────────
// Main workflow
// ──────────────────────────────────────────────────────────────────────────────

workflow {
    log.info """
    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃  AfriGend Beacon v2 — Data Loading Pipeline      ┃
    ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

    Dataset   : ${params.dataset_name}
    VCF       : ${params.vcf_file}
    Phenotype : ${params.phenotype_file ?: 'none'}
    Assembly  : ${params.assembly}
    Output    : ${params.outdir}
    Import    : ${params.skip_import ? 'SKIPPED' : params.mongo_uri}
    """.stripIndent()

    // -- Build VCF input channel --
    vcf_file = file(params.vcf_file, checkIfExists: true)
    metadata_file = params.metadata_file
        ? file(params.metadata_file, checkIfExists: true)
        : file("${projectDir}/NO_METADATA")

    vcf_ch = Channel.of(
        [params.dataset_name, vcf_file, metadata_file]
    )

    // -- VCF transform + validate --
    TRANSFORM_VALIDATE_VCF(vcf_ch)

    // -- Phenotype transform + validate (conditional) --
    phenotypes_ch = Channel.empty()

    if (params.phenotype_file) {
        pheno_file = file(params.phenotype_file, checkIfExists: true)

        // Join phenotype with individuals from VCF transform
        pheno_input = TRANSFORM_VALIDATE_VCF.out.individuals.map { ds, ind ->
            [ds, pheno_file, ind]
        }

        TRANSFORM_VALIDATE_PHENOTYPES(pheno_input)
        phenotypes_ch = TRANSFORM_VALIDATE_PHENOTYPES.out.phenotypes
    }

    // -- Import to MongoDB (conditional) --
    if (!params.skip_import) {
        IMPORT_DATA(
            TRANSFORM_VALIDATE_VCF.out.variants,
            TRANSFORM_VALIDATE_VCF.out.individuals,
            phenotypes_ch
        )
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// Completion handler
// ──────────────────────────────────────────────────────────────────────────────

workflow.onComplete {
    def status = workflow.success ? 'COMPLETED' : 'FAILED'
    log.info """
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Pipeline ${status}
    Duration : ${workflow.duration}
    Results  : ${params.outdir}
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """.stripIndent()
}
