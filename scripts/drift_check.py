"""
Report which beacon instances are running which release.

Exists because on 2026-08-19 all three deployments were behind `main` and
nothing could say so: `/api/health` reported only the GA4GH spec version, a
constant, so production and a deployment three months older returned the
identical string. See docs/superpowers/specs/2026-08-19-*.

``classify`` does no I/O so it can be tested without a network.

    python3 scripts/drift_check.py --latest v1.1.7
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

CURRENT = "current"
STALE = "stale"
UNKNOWN = "unknown"
THROTTLED = "throttled"
PREDATES_MARKER = "predates-marker"

# Statuses that mean "up but declining to serve", not "down". A peer's rate
# limit must not be reported as an outage — the aggregator's own health checker
# makes the same distinction, and conflating them once took the whole
# federation offline.
THROTTLE_STATUSES = (429,)


def classify(probe, latest_tag):
    """
    Turn one probe result into a drift verdict.

    ``probe`` is ``{"ok": bool, "status": int, "release": str}``. A probe that
    failed is never ``CURRENT`` — "I could not reach it" and "it is up to date"
    are different sentences, and only one of them is safe to report.
    """
    if not probe.get("ok"):
        if probe.get("status") in THROTTLE_STATUSES:
            return THROTTLED
        return UNKNOWN

    release = (probe.get("release") or "").strip()
    if not release or release == "unknown":
        # Either the image predates the release marker, or it was built
        # without the build-arg. Both are unmeasurable, neither is current.
        return PREDATES_MARKER

    return CURRENT if release == latest_tag else STALE


# Cloudflare 403s python-urllib's default User-Agent. Without this header every
# Cloudflare-fronted instance reports UNKNOWN forever — a check that always says
# "cannot tell" while appearing to work. Verified: default UA -> 403, this UA ->
# 200, same URL, same second.
USER_AGENT = "afrigen-d-drift-check/1.0"


def probe(url, timeout=20):
    """Fetch /api/health. Never raises: a failure is a result, not an error."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return {"ok": True, "status": resp.status, "release": body.get("release")}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code}
    except Exception:
        return {"ok": False, "status": 0}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", required=True, help="the newest tag in the repo")
    ap.add_argument("--instances", default="scripts/instances.json")
    args = ap.parse_args(argv)

    instances = json.load(open(args.instances))
    rows, drifted = [], 0
    for inst in instances:
        result = probe(inst["health_url"])
        verdict = classify(result, args.latest)
        if verdict != CURRENT:
            drifted += 1
        rows.append((verdict, inst["name"], result.get("release") or "-", inst["health_url"]))

    width = max(len(r[0]) for r in rows)
    print(f"latest tag: {args.latest}\n")
    for verdict, name, release, url in sorted(rows):
        print(f"  {verdict:<{width}}  {release:<10}  {name}  ({url})")

    print(f"\n{drifted} of {len(rows)} instance(s) not on {args.latest}.")

    # An identical answer for inputs that should differ is a broken instrument,
    # not a finding. If NOTHING could be read, the likeliest cause is this
    # checker, not a simultaneous outage of every beacon — say so rather than
    # letting a wall of UNKNOWN read as a survey.
    if rows and all(r[0] == UNKNOWN for r in rows):
        print(
            "\nWARNING: every instance returned UNKNOWN. That is far more likely "
            "to be this checker than a simultaneous outage — check egress, TLS "
            "and the User-Agent before believing it.",
            file=sys.stderr,
        )
    # Deliberately exit 0: this reports, it does not gate. A drift check that
    # fails the build teaches people to ignore it.
    return 0


if __name__ == "__main__":
    sys.exit(main())
