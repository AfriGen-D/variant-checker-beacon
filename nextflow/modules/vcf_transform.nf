process VCF_TRANSFORM {
    tag "$dataset_name"
    label 'bigmem'

    publishDir "${params.outdir}/${dataset_name}/transformed", mode: 'copy'

    input:
    tuple val(dataset_name), path(vcf_file), path(metadata_file)

    output:
    tuple val(dataset_name), path("variants_batch.jsonl"),         emit: variants
    tuple val(dataset_name), path("individuals.json"),             emit: individuals
    tuple val(dataset_name), path("variant_genotypes.json"),       emit: genotypes
    tuple val(dataset_name), path("transformation_summary.json"),  emit: summary

    script:
    def metadata_arg = metadata_file.name != 'NO_METADATA' ? "--metadata ${metadata_file}" : ''
    def verbose_arg  = params.verbose ? '--verbose' : ''
    def config_arg   = params.tools_config ? "--config ${params.tools_config}" : ''
    """
    python ${params.tools_base}/vcf_transform/vcf_to_beacon.py \\
        ${vcf_file} \\
        --output . \\
        --assembly ${params.assembly} \\
        ${metadata_arg} \\
        ${config_arg} \\
        ${verbose_arg}
    """
}
