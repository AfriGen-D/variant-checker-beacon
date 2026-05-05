# Deploy / Ops gotchas

Operational items that are **not** code or app-config — they're properties of the host environment and the way Docker/Compose interacts with this repo. Capturing them so each new deploy doesn't have to rediscover them.

## 1. MongoDB 5.0 needs AVX

MongoDB 5.0+ requires a CPU exposing AVX. On Proxmox, the default `cpu: kvm64` does **not** pass AVX through to the guest, and the mongo container restart-loops with exit 132 (SIGILL) and logs:

```
WARNING: MongoDB 5.0+ requires a CPU with AVX support
```

Fix on the Proxmox host:

```bash
qm set <vmid> --cpu host          # or 'Skylake-Server' if you need portability across hosts
```

Verify after VM boot:

```bash
grep -m1 -oE 'avx2?|sse4_2' /proc/cpuinfo | sort -u   # expect: avx, avx2, sse4_2
```

## 2. IPv6 cascade — three layers required

If the host has IPv6 link-local but no real IPv6 routing, container apt-mirror lookups time out on AAAA records, turning a 53-package install into a 3-hour hang. Just `{"ipv6": false}` in `/etc/docker/daemon.json` is **not** enough. All three of the following are needed for reliable Docker Hub + Debian apt connectivity:

| Layer | What | File |
|---|---|---|
| Kernel | Disable IPv6 system-wide | `/etc/sysctl.d/99-disable-ipv6.conf` with `net.ipv6.conf.{all,default,lo}.disable_ipv6 = 1` |
| Daemon | Tell Docker not to expose IPv6 to containers | `/etc/docker/daemon.json` `{"ipv6": false, "dns": ["1.1.1.1", "8.8.8.8"]}` |
| Build-time | Use legacy builder + host network for builds | `DOCKER_BUILDKIT=0 docker build --network=host …` |

The third layer is the trap: BuildKit's container network namespace ignores the daemon-level setting and re-exposes IPv6 anyway. Any `RUN apt-get …` step inside `Dockerfile.boolean` will time out. Build the API image with:

```bash
sudo DOCKER_BUILDKIT=0 docker build --network=host -f Dockerfile.boolean -t beacon-api:latest .
```

## 3. Compose path resolution (env_file, volume mounts)

When `docker compose -f compose/docker-compose.prod.yml -f docker-compose.override.yml …`, **all relative paths in the override file are resolved relative to the FIRST compose file's directory** — not CWD, not the override's directory. Since the base lives in `compose/`, an override at the repo root referencing `.env.production` and `nginx/nginx.conf` must use `../`:

```yaml
services:
  cloudflared:
    env_file: ../.env.production              # NOT .env.production (would resolve to compose/.env.production)
  nginx:
    volumes:
      - ../nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro   # NOT ./nginx/nginx.conf
```

Same applies to the `--env-file <path>` CLI flag (don't use it; rely on `env_file:` directives in service blocks instead).

## 4. `docker compose up -d` without service list will start Traefik

The base prod compose includes a `traefik` service whose config dir doesn't exist on most deploys. Plain `docker compose up -d` therefore fails or starts Traefik in a broken state. Always pass an explicit service list:

```bash
sudo docker compose -f compose/docker-compose.prod.yml -f docker-compose.override.yml \
  up -d mongodb redis beacon-api beacon-frontend nginx cloudflared
```

## 5. API logs/ bind-mount must be writable before first up

The API mounts `../logs:/app/logs`. If the host directory doesn't exist, the API container restart-loops on first start with `PermissionError: [Errno 13] Permission denied: '/app/logs/...'`. Create + chmod before first `up`:

```bash
sudo mkdir -p logs && sudo chmod 777 logs
```

## 6. cyvcf2 wheel install needs `setuptools<70`

setuptools 70 removed `pkg_resources`, which several genomics build deps still rely on. Pin in the venv first:

```bash
.venv/bin/pip install --upgrade pip "setuptools<70" wheel
.venv/bin/pip install cyvcf2 pysam pymongo openpyxl tqdm
```

Without the pin, `cyvcf2`'s build fails with `ModuleNotFoundError: No module named 'pkg_resources'`.

## 7. `--force-recreate` is unreliable for image swaps

When you've rebuilt the API image (`docker build -t beacon-api:latest .`) and want compose to pick up the new image, `docker compose up -d --force-recreate beacon-api` does **not** always pull/swap (it sometimes detects "no config change" and reuses the running container). Use the explicit hard path:

```bash
sudo docker stop beacon-api && sudo docker rm beacon-api
sudo docker compose -f compose/docker-compose.prod.yml -f docker-compose.override.yml up -d beacon-api
```
