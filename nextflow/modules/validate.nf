process VALIDATE_VARIANTS {
    tag "$dataset_name"
    label 'small'

    input:
    tuple val(dataset_name), path(json_file)

    output:
    tuple val(dataset_name), path(json_file), emit: validated

    script:
    def strict_arg  = params.strict_validation ? '--strict' : ''
    def verbose_arg = params.verbose ? '--verbose' : ''
    """
    python ${params.tools_base}/validation/validate_json.py \\
        ${json_file} \\
        --schema-type variant \\
        ${strict_arg} \\
        ${verbose_arg}
    """
}

process VALIDATE_INDIVIDUALS {
    tag "$dataset_name"
    label 'small'

    input:
    tuple val(dataset_name), path(json_file)

    output:
    tuple val(dataset_name), path(json_file), emit: validated

    script:
    def strict_arg  = params.strict_validation ? '--strict' : ''
    def verbose_arg = params.verbose ? '--verbose' : ''
    """
    python ${params.tools_base}/validation/validate_json.py \\
        ${json_file} \\
        --schema-type individual \\
        ${strict_arg} \\
        ${verbose_arg}
    """
}

process VALIDATE_PHENOTYPES {
    tag "$dataset_name"
    label 'small'

    input:
    tuple val(dataset_name), path(json_file)

    output:
    tuple val(dataset_name), path(json_file), emit: validated

    script:
    def strict_arg  = params.strict_validation ? '--strict' : ''
    def verbose_arg = params.verbose ? '--verbose' : ''
    """
    python ${params.tools_base}/validation/validate_json.py \\
        ${json_file} \\
        --schema-type phenotype \\
        ${strict_arg} \\
        ${verbose_arg}
    """
}
