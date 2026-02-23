process PHENOTYPE_TRANSFORM {
    tag "$dataset_name"
    label 'medium'

    publishDir "${params.outdir}/${dataset_name}/transformed", mode: 'copy'

    input:
    tuple val(dataset_name), path(phenotype_file), path(individuals_json)

    output:
    tuple val(dataset_name), path("phenotypes.json"),                        emit: phenotypes
    tuple val(dataset_name), path("diseases.json"),              optional: true, emit: diseases
    tuple val(dataset_name), path("individuals_with_phenotypes.json"), optional: true, emit: individuals_updated

    script:
    def individuals_arg = individuals_json.name != 'NO_INDIVIDUALS' ? "--individuals ${individuals_json}" : ''
    def verbose_arg     = params.verbose ? '--verbose' : ''
    def config_arg      = params.tools_config ? "--config ${params.tools_config}" : ''
    """
    python /opt/beacon-tools/phenotype_transform/phenotype_to_beacon.py \\
        ${phenotype_file} \\
        --output . \\
        ${individuals_arg} \\
        ${config_arg} \\
        ${verbose_arg}
    """
}
