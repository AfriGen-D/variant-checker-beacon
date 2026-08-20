# Deploying afrigen-beacon-v2 — Step-by-Step Tutorial

> **Scope and status.** This is the *operator* path: standing up a NEW production
> node on your own infrastructure — VM, tunnel, TLS, secrets, ingestion. If you
> only want to run the beacon locally to develop against it, use
> [docs/developers/tutorial-zero-to-beacon.md](developers/tutorial-zero-to-beacon.md)
> instead; it is a 12-step local path that was walked end to end on 2026-08-20.
>
> **Written 2026-05-04 from a real deployment, refreshed 2026-08-21.** The
> original "apply these patches first" step has been removed — both patches
> (issues #3 and #4) are merged and those issues are closed. The Cloudflare
> tunnel topology below is one valid shape and is what the API sidecar uses;
> the main production node instead terminates TLS with nginx and runs
> `docker-compose-boolean-ssl.yml` from its working-tree root. Read the compose
> and env sections as *an* example, not as the only supported layout.


A reproducible recipe for deploying this GA4GH Beacon v2 implementation as a public boolean-discovery service, end to end. Written from a real production deployment ([beacon.ardi.africa](https://beacon.ardi.africa), 2026-05-04) — every step, gotcha, and recovery is what actually happened.

> **Generic version.** Use `<placeholders>` to substitute your own values (zone, IPs, account IDs, sample counts). For the original ARDI deployment with concrete values, see commit history of issues #3–#8.

## What you'll have at the end

- A new VM hosting MongoDB 5 + Redis + Django/gunicorn + Cloudflared
- Public endpoint `<your-beacon>.<your-domain>` serving the GA4GH Beacon v2 boolean API
- Your dataset ingested into MongoDB
- ~30-45 min wall-clock if you avoid the gotchas (4+ hours first time if you don't — like we did)

## Prerequisites

- A virtualisation host with ≥16 GB RAM and ≥100 GB free storage. We used Proxmox; cloud equivalents work fine (specifically need to expose AVX — see Gotcha #3).
- A Cloudflare-managed domain (or any public DNS provider that supports CNAMEs to a tunnel).
- SSH keypair on your laptop.
- `bcftools`, `tabix`, `python3` locally for input prep.

## The "shape" of input data this beacon expects

GA4GH Beacon v2 expects per-variant JSON records with these fields (snake_case, **no `chr` prefix on chromosomes**):

```json
{
  "id": "1:69269:A:G",
  "assembly_id": "GRCh38",
  "reference_name": "1",
  "start": 69269,
  "end": 69270,
  "reference_bases": "A",
  "alternate_bases": "G",
  "variant_type": "SNV",
  "annotations": [],
  "dataset_ids": ["my_dataset_v1"]
}
```

If your source VCF uses `chr1`-style names, strip the prefix (see Step 9). If you don't, queries with `referenceName=1` will return `exists:false` even for variants that exist.

---

## Step 0 — Cloudflare side first (idempotent, parallel-safe)

### Create the tunnel

```bash
ACCT=<your-cloudflare-account-id>
CF_KEY=<your-global-api-key>      # or use a scoped API token with Bearer auth
CF_EMAIL=<your-cloudflare-email>

curl -sS -H "X-Auth-Email: $CF_EMAIL" -H "X-Auth-Key: $CF_KEY" \
  -H "Content-Type: application/json" \
  --data '{"name":"<TUNNEL NAME>","tunnel_secret":"'"$(openssl rand -base64 32)"'","config_src":"cloudflare"}' \
  "https://api.cloudflare.com/client/v4/accounts/$ACCT/cfd_tunnel"
```

Returns the tunnel ID. Then fetch the runtime token (180-char base64, used inside the cloudflared container):

```bash
curl -sS -H "X-Auth-Email: $CF_EMAIL" -H "X-Auth-Key: $CF_KEY" \
  "https://api.cloudflare.com/client/v4/accounts/$ACCT/cfd_tunnel/$TUNNEL_ID/token"
```

Save the token to your password manager immediately.

> **Gotcha #1**: a global API key uses `X-Auth-Email + X-Auth-Key` headers. Bearer auth fails with `6111: Invalid format for Authorization header`. Scoped API tokens use Bearer; global keys do not.

### DNS record + ingress rule

```bash
ZONE=<your-zone-id>
TUNNEL_ID=<from-step-above>

# DNS
curl -sS -H "X-Auth-Email: $CF_EMAIL" -H "X-Auth-Key: $CF_KEY" \
  -H "Content-Type: application/json" \
  --data "{\"type\":\"CNAME\",\"name\":\"<beacon-subdomain>\",\"content\":\"$TUNNEL_ID.cfargotunnel.com\",\"proxied\":true}" \
  "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records"

# Tunnel ingress
curl -sS -H "X-Auth-Email: $CF_EMAIL" -H "X-Auth-Key: $CF_KEY" \
  -H "Content-Type: application/json" -X PUT \
  --data '{"config":{"ingress":[{"hostname":"<your-beacon-fqdn>","service":"http://beacon-api:8000"},{"service":"http_status:404"}]}}' \
  "https://api.cloudflare.com/client/v4/accounts/$ACCT/cfd_tunnel/$TUNNEL_ID/configurations"
```

> **Gotcha #2**: `originRequest.connectTimeout` expects integer nanoseconds, not a string `"30s"`. Drop the field entirely if you don't need custom timeouts.

---

## Step 1 — VM provisioning (Proxmox example)

```bash
# Copy your SSH pubkey to the host
scp ~/.ssh/id_rsa.pub <pve-host>:/tmp/sshkey.pub

# On the Proxmox host
qm clone <ubuntu-template-id> <new-vmid> --name <hostname> --full --storage local-lvm
qm set <vmid> --memory 16384 --balloon 0 --cores 4 --net0 virtio,bridge=vmbr0
qm resize <vmid> scsi0 +80G
qm set <vmid> --ciuser ubuntu \
  --nameserver "1.1.1.1 8.8.8.8" \
  --ipconfig0 ip=<vm-ip>/24,gw=<gw-ip> \
  --sshkey /tmp/sshkey.pub \
  --cpu host                 # CRITICAL — see Gotcha #3
qm start <vmid>
```

> **Gotcha #3** — **MongoDB 5.0+ requires AVX**. Proxmox's default `cpu: kvm64` does not expose host AVX flags to the guest. Without `--cpu host`, the mongo container restart-loops with exit 132 (SIGILL). Verify after VM boot:
>
> ```bash
> ssh ubuntu@<vm-ip> 'grep -m1 -oE "avx2?|sse4_2" /proc/cpuinfo | sort -u'
> # Should print: avx, avx2, sse4_2
> ```
>
> Tradeoff: VM becomes non-portable across hosts with different CPU vendors. Use `--cpu Skylake-Server` or similar specific model for portability.

> **Gotcha #4** — **SSH port 22 opens before cloud-init's `package_upgrade: true` finishes**. The first `ssh` attempt fails with `Permission denied (publickey)` because cloud-init hasn't yet written `authorized_keys`. Wait until `sudo cloud-init status` returns `done`:
>
> ```bash
> until ssh -o ConnectTimeout=5 ubuntu@<vm-ip> "echo OK"; do sleep 10; done
> ```

---

## Step 2 — Disable IPv6 (the deepest rabbit hole)

If your VM has an IPv6 link-local address but no real IPv6 routing (typical on Proxmox), Docker pulls and `apt-get` inside container builds will resolve AAAA records first, time out, and retry — making each Debian apt package take 200+ seconds. The fix needs **three layers**:

```bash
ssh ubuntu@<vm-ip>

# Layer 1 — Kernel-level disable
sudo tee /etc/sysctl.d/99-disable-ipv6.conf <<EOF
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1
net.ipv6.conf.lo.disable_ipv6 = 1
EOF
sudo sysctl -p /etc/sysctl.d/99-disable-ipv6.conf

# Layer 2 — Docker daemon (still needed even with kernel disable)
sudo tee /etc/docker/daemon.json <<EOF
{"ipv6": false, "dns": ["1.1.1.1", "8.8.8.8"]}
EOF
sudo systemctl restart docker

# Layer 3 — for builds, use --network=host (BuildKit's namespace ignores the daemon setting)
```

Verify:

```bash
ip -6 addr | grep -c inet6   # should be 0
docker pull alpine:latest    # should complete in ~2 sec, not minutes
```

> **Gotcha #5**: Just `daemon.json {"ipv6": false}` is not enough. BuildKit's container network namespace doesn't honor it. Without all three layers, `docker compose build` hangs for 200 sec/package, making a 53-package install take 3+ hours.

---

## Step 3 — System packages

```bash
sudo cloud-init status --wait
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  docker.io docker-compose-v2 git \
  python3-venv python3-dev libhts-dev pkg-config
sudo usermod -aG docker ubuntu   # log back in to take effect
```

---

## Step 4 — Generate stack secrets

On your laptop or workstation:

```bash
DJANGO_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
MONGO_PW=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
REDIS_PW=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# Save these to your password manager NOW. We use macOS Keychain:
security add-generic-password -s <prefix>-django-secret -a django -w "$DJANGO_SECRET" -U
# ... etc
```

Why `secrets.token_urlsafe`: same entropy as `openssl rand`, but URL-safe charset has no `+`, `/`, `=` — no shell-escaping concerns when the secret lands in env files or YAML.

---

## Step 5 — Clone repo, write `.env.production`, override compose

> **What the repo actually ships.** There is no `.env.production` in the
> repository — it ships `.env.example` (the documented template) and
> `.env.boolean` is gitignored, so a fresh clone has neither populated. The
> `.env.production` below is a file *you create* for this deployment; start
> from `.env.example`, which is the authoritative list of variables the
> settings modules read.
>
> Likewise the compose override below is specific to the tunnel topology. The
> repo carries five compose files under `compose/`; production's own stack file
> (`docker-compose-boolean-ssl.yml`) lives at the working-tree root on the host,
> not under `compose/`. Do not assume a file you find under `compose/` is the
> one a given host runs — check the host.

```bash
ssh ubuntu@<vm-ip>
sudo mkdir -p /opt/beacon && sudo chown ubuntu:ubuntu /opt/beacon
git clone https://github.com/AfriGen-D/variant-checker-beacon.git /opt/beacon
cd /opt/beacon

# .env.production — referenced by env_file: ../.env.production in each service
umask 077
cat > .env.production <<EOF
DJANGO_SECRET_KEY=<from-secrets-store>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=<beacon-fqdn>,localhost,127.0.0.1
DJANGO_SETTINGS_MODULE=beacon_project.settings_boolean
SECURE_SSL_REDIRECT=False    # Cloudflared terminates TLS upstream

MONGODB_HOST=mongodb
MONGODB_PORT=27017
MONGODB_NAME=beacon_db
MONGODB_USERNAME=beacon
MONGODB_PASSWORD=<from-secrets-store>
MONGO_INITDB_ROOT_USERNAME=beacon
MONGO_INITDB_ROOT_PASSWORD=<from-secrets-store>

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=<from-secrets-store>
REDIS_CACHE_TIMEOUT=300

FEATURE_AUTHENTICATION_ENABLED=False
JWT_SECRET_KEY=<from-secrets-store>
JWT_ACCESS_TOKEN_LIFETIME=15
JWT_REFRESH_TOKEN_LIFETIME=7

FEATURE_RATE_LIMITING_ENABLED=True
RATELIMIT_DEFAULT=100/hour
RATELIMIT_QUERY_ENDPOINT=50/hour

CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOWED_ORIGINS=https://<beacon-fqdn>

API_PAGE_SIZE=100

BEACON_API_NAME=GA4GH Beacon v2 - <YOUR ORG>
BEACON_API_VERSION=2.0.0-boolean
BEACON_API_ID=<your.beacon.id>
BEACON_ORGANIZATION_ID=<your-org-id>
BEACON_ORGANIZATION_NAME=<Your Organization>

LOG_LEVEL=INFO
LOG_FORMAT=json

TUNNEL_TOKEN=<from-step-0>     # cloudflared CLI auto-reads this env var
EOF
chmod 600 .env.production
```

> **Gotcha #6**: cloudflared reads `TUNNEL_TOKEN` from env automatically. Don't try `command: tunnel run --token ${VAR}` in compose — that uses shell-expansion which fails because the var isn't in the compose-file's env scope. Just put `TUNNEL_TOKEN=...` in `.env.production` and reference via `env_file:` in the cloudflared service.

Write a compose override to drop services you don't want and add cloudflared:

```yaml
# /opt/beacon/docker-compose.override.yml
services:
  beacon-api:
    ports:
      - "127.0.0.1:8000:8000"   # localhost-only, accessed via cloudflared
  mongodb:
    ports:
      - "127.0.0.1:27017:27017" # for ingestion script; remove after data is loaded
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: beacon-cloudflared
    restart: unless-stopped
    networks:
      - beacon-network
    command: tunnel --no-autoupdate run
    env_file:
      - ../.env.production       # CRITICAL — relative to base compose's dir
    depends_on:
      beacon-api:
        condition: service_healthy
```

> **Gotcha #7**: with multiple compose files (`-f base.yml -f override.yml`), relative paths in the override file resolve relative to the BASE compose file's directory (here `compose/`). Use `../.env.production` to reach the project root. Same applies to `--env-file` CLI flag — drop the flag, rely on `env_file:` directives.

---

## Step 6 — Build the API image (legacy builder + host network)

```bash
cd /opt/beacon
sudo mkdir -p logs && sudo chmod 777 logs    # see Gotcha #10
sudo DOCKER_BUILDKIT=0 docker build --network=host \
  -f Dockerfile.boolean -t beacon-api:latest .
```

> **Gotcha #8**: BuildKit's container network namespace will revert to IPv6 even with kernel disable + daemon.json. The two flags `DOCKER_BUILDKIT=0` (legacy builder) and `--network=host` (skip the namespace) make builds work. Without these, expect 200s per Debian apt package during the build's `RUN apt-get install` step.

Build takes ~5-10 min on first run.

---

## Step 7 — Bring up the stack

```bash
cd /opt/beacon
sudo docker compose -f compose/docker-compose.prod.yml -f docker-compose.override.yml \
  up -d mongodb redis beacon-api cloudflared
```

> **Gotcha #9**: never `up -d` without an explicit service list. The base prod compose includes `traefik` (config dir doesn't exist by default) and `beacon-frontend` (a separate Next.js build). Always specify services explicitly.

> **Gotcha #10**: the API needs a writable `logs/` bind-mount. Create it on the host with `mkdir -p logs && chmod 777 logs` BEFORE first `up`, otherwise gunicorn workers crash with `ValueError: Unable to configure handler 'file'`.

Wait for healthchecks:

```bash
for i in $(seq 1 12); do
  m=$(sudo docker inspect -f "{{.State.Health.Status}}" beacon-mongodb 2>/dev/null)
  r=$(sudo docker inspect -f "{{.State.Health.Status}}" beacon-redis 2>/dev/null)
  a=$(sudo docker inspect -f "{{.State.Health.Status}}" beacon-api 2>/dev/null)
  echo "t+$((i*5))s: mongo=$m redis=$r api=$a"
  [ "$m" = healthy ] && [ "$r" = healthy ] && [ "$a" = healthy ] && break
  sleep 5
done
```

Smoke-test:

```bash
# Internal
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/

# External (from outside)
curl https://<your-beacon-fqdn>/api/health
```

If both 200, public infrastructure is live. Datasets still empty.

---

## Step 8 — Data ingestion

### Transfer your VCF

From your laptop:

```bash
scp <your-cohort>.vcf.gz <your-cohort>.vcf.gz.tbi <metadata>.xlsx \
    ubuntu@<vm-ip>:/opt/beacon/data/
```

### Set up Python venv

```bash
ssh ubuntu@<vm-ip>
cd /opt/beacon/afrigend-beacon2-tools
python3 -m venv .venv
.venv/bin/pip install --upgrade pip "setuptools<70" wheel
.venv/bin/pip install pyyaml pandas numpy tqdm pymongo jsonschema openpyxl cython pysam cyvcf2
```

> **Gotcha #11**: setuptools 70+ removed `pkg_resources`. Some build deps (cyvcf2 in particular) still rely on it. **Pin `setuptools<70`** in the venv before installing genomics libraries.

### Run the transform

```bash
source .venv/bin/activate
nohup python vcf_transform/vcf_to_beacon.py \
  /opt/beacon/data/<your-cohort>.vcf.gz \
  --output /opt/beacon/data/beacon_output \
  --assembly GRCh38 \
  --metadata /opt/beacon/data/<metadata>.xlsx \
  --verbose > /tmp/transform.log 2>&1 &
disown
```

Expect ~50K variants/sec on a 4-core VM. The DRC subset (28M variants) took ~12 min before OOM — see Gotcha #12 for what to do.

> **Gotcha #12** — **The transform script accumulates `variant_genotypes.json` in memory** (issue #6). RAM grows linearly with variant count × sample count. We OOM-killed at 13.6M variants on 8 GB, then again at 28.8M on 16 GB. **For now: bump VM RAM proportional to dataset size**. Or ingest only the streamed `variants_batch.jsonl` (which works for boolean discovery — see below).

### Recovery if OOM hits

The streamed `variants_batch.jsonl` is intact even after OOM (Python flushes complete lines). The buffered `individuals.json` and `variant_genotypes.json` won't be written, but for **boolean discovery only** that's fine — `/api/g_variants` only needs `variants_batch.jsonl`.

### Import variants — use mongoimport, not the bundled script

The bundled `import_to_mongo.py` ALSO loads the entire JSONL into memory before inserting (issue #6). Bypass it with mongoimport, which streams natively:

```bash
# Copy JSONL into the mongo container
sudo docker cp /opt/beacon/data/beacon_output/variants_batch.jsonl beacon-mongodb:/tmp/

# Stream-import directly
sudo docker exec beacon-mongodb mongoimport \
  --db beacon_db --collection variants \
  --type json --file /tmp/variants_batch.jsonl \
  --numInsertionWorkers 4 --batchSize 5000 --writeConcern '{w:1}'
```

~13 min for 28.8M records. Mongo memory stays below 1 GB throughout.

### Strip `chr` prefix if present

Beacon v2 spec uses no-prefix chromosome names. If your transform's output has `chr1`-style:

```bash
sudo docker exec beacon-mongodb mongo beacon_db --eval '
  db.variants.updateMany(
    {reference_name: /^chr/},
    [{$set: {reference_name: {$substr: ["$reference_name", 3, -1]}}}]
  )
'
```

Takes ~30 min for 28.8M records.

### Build query indexes

```bash
sudo docker exec beacon-mongodb mongo beacon_db --eval '
  db.variants.createIndex(
    {assembly_id: 1, reference_name: 1, start: 1, reference_bases: 1, alternate_bases: 1},
    {name: "variant_lookup"}
  );
  db.variants.createIndex({reference_name: 1, start: 1}, {name: "region_scan"});
'
```

Without indexes, queries take seconds (full collection scan). With them, queries return in <50 ms (index seek + 1 doc fetch).

### Register your dataset

```bash
sudo docker exec beacon-mongodb mongo beacon_db --eval '
  db.datasets.insertOne({
    _id: "<your-dataset-id>",
    name: "<Human-readable name>",
    description: "<...>",
    assembly_id: "GRCh38",
    dataset_type: "genomics",
    dataset_size: {variants: <count>, samples: <count>},
    contact_info: {organization: "<your-org>", url: "https://<your-beacon>/"},
    create_date: new Date(),
    update_date: new Date()
  })
'
```

> **Gotcha #13**: As of writing, `/api/datasets` endpoint has a serialization bug returning empty `resultSets` even when datasets exist (issue #8). The `/api/` (service info) endpoint correctly enumerates datasets — and that's the endpoint Beacon Network registries use, so it's not a real blocker.

---

## Step 9 — Verify

```bash
# Test a known existing variant
curl 'https://<your-beacon-fqdn>/api/g_variants?assemblyId=GRCh38&referenceName=1&start=69269&referenceBases=A&alternateBases=G'
# {"responseSummary":{"exists":true,"numTotalResults":1}, ...}

# Test a fake variant
curl 'https://<your-beacon-fqdn>/api/g_variants?assemblyId=GRCh38&referenceName=22&start=99999999&referenceBases=A&alternateBases=T'
# {"responseSummary":{"exists":false,"numTotalResults":0}, ...}

# Check service info exposes your dataset
curl 'https://<your-beacon-fqdn>/api/' | jq .response.datasets
```

Expected uncached latency: ~200 ms (3-hop laptop → CF edge → tunnel → indexed Mongo).

---

## Cleanup after go-live

- Remove the `127.0.0.1:27017:27017` mapping from `docker-compose.override.yml` once ingestion is done.
- Add Mongo auth properly (issue #5) — pick a password, `db.createUser`, update `.env.production`, rebuild API image.
- Push your env-specific changes (the `docker-compose.override.yml`) to your own ops repo, NOT this one.

---

## Going further

- **Federate** with [African Beacon Network](https://github.com/mamanambiya/african-beacon-network) so your beacon shows up in cross-beacon discovery.
- **Secure mode** alongside boolean for authenticated researchers wanting genotype-level access.
- **Backup**: nightly `mongodump` to off-host storage.
- **Monitoring**: hook node-exporter + Prometheus + your existing tunnel pattern.
- **Frontend**: deploy the bundled Next.js UI (`compose/docker-compose-frontend.yml`).

---

## Known limitations / open issues

Status verified 2026-08-21 against `main`, and live where the check was possible.

**Fixed since this tutorial was written — no longer anything to work around:**

- [#3](https://github.com/AfriGen-D/variant-checker-beacon/issues/3) — `QueryLogMiddleware` missing. Present and registered; production serves `/api/health` 200, which it could not do otherwise.
- [#4](https://github.com/AfriGen-D/variant-checker-beacon/issues/4) — `variant.format()` called without a tag. All three calls now pass one.
- [#8](https://github.com/AfriGen-D/variant-checker-beacon/issues/8) — `/api/datasets` empty. Live: one populated `resultSet`.

These three are why the old "Step 8 — apply known-required patches" is gone.

**Still open, and they affect this tutorial:**

- [#5](https://github.com/AfriGen-D/variant-checker-beacon/issues/5) — `compose/docker-compose.prod.yml` has no `MONGO_INITDB_ROOT_*`. Step 5 works without auth, but do not expose that Mongo.
- [#6](https://github.com/AfriGen-D/variant-checker-beacon/issues/6) — memory accumulation. **Partly fixed**: the VCF transform streams now, and the importer streams `.jsonl`. Still buffering: `.json` inputs in both the importer and the validator, and the validator's `.jsonl` accumulator. At production scale this is the step most likely to fail — see the issue for the four exact sites.
- [#50](https://github.com/AfriGen-D/variant-checker-beacon/issues/50) — `GRCh37` is selectable in the UI while the beacon holds only GRCh38 data, so it answers a confident "no". If you load GRCh37 data, this stops being a problem; if you do not, expect the question.

