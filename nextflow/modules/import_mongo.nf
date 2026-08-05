process CLEAR_COLLECTIONS {
    tag "clear:${collections}"
    label 'local_only'

    input:
    val collections  // comma-separated collection names

    output:
    val true

    script:
    """
    python3 -c "
from pymongo import MongoClient
client = MongoClient('${params.mongo_uri}')
db = client['${params.mongo_db}']
for coll in '${collections}'.split(','):
    coll = coll.strip()
    count = db[coll].count_documents({})
    if count > 0:
        db[coll].drop()
        print(f'Dropped {coll} ({count} documents)')
    else:
        print(f'Collection {coll} already empty')
client.close()
"
    """
}

process IMPORT_TO_MONGO {
    tag "${dataset_name}:${collection}"
    label 'local_only'

    input:
    tuple val(dataset_name), path(json_file), val(collection)

    // Completion signal — main.nf collects these to gate FLUSH_REDIS_CACHE.
    // Without a declared output that channel never resolves and the post-load
    // cache flush silently never runs.
    output:
    tuple val(dataset_name), val(collection)

    script:
    def verbose_arg = params.verbose ? '--verbose' : ''
    def batch_arg   = params.import_batch_size ? "--batch-size ${params.import_batch_size}" : ''
    """
    python ${params.tools_base}/data_import/import_to_mongo.py \\
        ${json_file} \\
        --db ${params.mongo_db} \\
        --collection ${collection} \\
        --mongo-uri ${params.mongo_uri} \\
        ${batch_arg} \\
        ${verbose_arg}
    """
}

process FLUSH_REDIS_CACHE {
    tag "redis"
    label 'local_only'

    input:
    val ready  // Collect signal from all imports

    script:
    if (params.beacon_host)
        """
        echo "Flushing Redis cache on ${params.beacon_host}..."
        ssh ${params.beacon_host} "docker exec beacon-redis redis-cli FLUSHDB" 2>/dev/null || true
        echo "Redis cache flushed"
        """
    else if (params.redis_host)
        """
        echo "Flushing Redis cache on ${params.redis_host}:${params.redis_port}..."
        redis-cli -h ${params.redis_host} -p ${params.redis_port} FLUSHDB 2>/dev/null || true
        echo "Redis cache flushed"
        """
    else
        """
        echo "No Redis host configured — skipping cache flush"
        """
}
