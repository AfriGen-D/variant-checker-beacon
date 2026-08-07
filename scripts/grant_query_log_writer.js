// Restore the beacon's audit trail with least privilege.
//
// WHY THIS EXISTS
// ---------------
// QueryLogMiddleware records every data-discovery query into `query_logs`, but
// on afrigend-beacon-prod that collection is EMPTY — not stale, never written.
// The API authenticates as `beacon_api`, which holds only the `read` role on
// `beacon_db`, so every insert fails. The middleware wraps its writes in
// try/except so a logging failure never blocks a beacon response — correct
// design, and exactly what kept this invisible.
//
// WHY NOT `readWrite`
// -------------------
// Granting `readWrite` on beacon_db would also let the public, unauthenticated
// API modify `variants` — 42M records of genomic data. The read-only account is
// documented as deliberate, and it should stay that way. This grants write on
// the audit-trail collection ONLY; the API remains read-only on everything else.
//
// USAGE (needs the beacon_admin root credential, not the app's)
//
//   PW=$(security find-generic-password -s "afrigend-beacon-prod-mongo-admin" -w)
//   scp scripts/grant_query_log_writer.js afrigend-beacon-prod:/tmp/
//   ssh afrigend-beacon-prod \
//     "docker cp /tmp/grant_query_log_writer.js beacon-mongodb:/tmp/ && \
//      docker exec beacon-mongodb mongo -u beacon_admin -p '\$PW' \
//        --authenticationDatabase admin --quiet /tmp/grant_query_log_writer.js"
//
// Then restart the API so it reconnects with the new privileges:
//   ssh afrigend-beacon-prod "cd ~/afrigend-beacon2 && \
//     docker compose -f docker-compose-boolean-ssl.yml restart beacon-api && \
//     docker exec beacon-nginx nginx -s reload"
//
// (nginx caches upstream container IPs at startup; reload it after any
// recreate or the stack 502s even though the API is healthy.)
//
// TO REVERSE
//   db.getSiblingDB("beacon_db").revokeRolesFromUser(
//     "beacon_api", [{ role: "beaconQueryLogWriter", db: "beacon_db" }]);
//   db.getSiblingDB("beacon_db").dropRole("beaconQueryLogWriter");

var target = db.getSiblingDB("beacon_db");

if (!target.getRole("beaconQueryLogWriter")) {
    target.createRole({
        role: "beaconQueryLogWriter",
        privileges: [{
            // Collection-scoped: query_logs only.
            resource: { db: "beacon_db", collection: "query_logs" },
            // createIndex/listIndexes are needed for the TTL index that bounds
            // retention — without them the logs would accumulate forever, which
            // is its own problem given they pair a client IP with a genomic
            // locus.
            actions: ["insert", "find", "createIndex", "listIndexes"]
        }],
        roles: []
    });
    print("created role: beaconQueryLogWriter");
} else {
    print("role already exists: beaconQueryLogWriter");
}

target.grantRolesToUser("beacon_api", [
    { role: "beaconQueryLogWriter", db: "beacon_db" }
]);

print("beacon_api roles now: " + JSON.stringify(target.getUser("beacon_api").roles));
print("");
print("Next: restart beacon-api, then confirm with");
print("  db.getSiblingDB('beacon_db').query_logs.countDocuments({})");
print("after issuing a query against https://beacon.afrigen-d.org/api/g_variants");
