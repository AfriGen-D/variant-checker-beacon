"""
Privacy / statistical-disclosure-control helpers.

Standalone by design: imports nothing from Django, DRF or MongoEngine, so the
rules below can be unit-tested without a settings module or a database.
Callers read the tunables from settings and pass them in.
"""

# ── Query-log IP anonymisation ──────────────────────────────────────────────
#
# QueryLogMiddleware records the exact genomic locus a caller asked about. An
# IP address next to "did you ask about chr13:32,340,300 (BRCA2)?" supports a
# health inference about an identifiable person, which makes the pair personal
# data under GDPR/POPIA. The audit and dashboard value of the log is in the
# aggregate — request volume, latency, hit rate, how many distinct networks —
# not in who exactly made each request, so the address is truncated to its
# network prefix before it is ever written.
#
# /24 for IPv4 and /48 for IPv6 are the conventional anonymisation boundaries
# (the same ones used by GA's IP anonymisation and by most log-retention
# guidance): coarse enough that the record no longer identifies a subscriber
# line, specific enough to still name the network behind an abuse pattern and
# to count distinct clients approximately.

IPV4_KEEP_OCTETS = 3   # -> a.b.c.0/24
IPV6_KEEP_GROUPS = 3   # -> x:y:z::/48


def anonymize_client_ip(ip):
    """Reduce a client IP to its network prefix.

    Returns '' for anything unparseable rather than falling back to the raw
    value — a value we could not classify is exactly the one we must not store
    verbatim. The return is still a short string, so the ``client_ip`` column
    keeps its type and any consumer counting distinct values keeps working
    (it now counts distinct networks).
    """
    if not ip or not isinstance(ip, str):
        return ''
    ip = ip.strip()
    if not ip:
        return ''

    if ':' in ip:
        # IPv6 (possibly '::1' or a compressed form). Keep the leading groups
        # up to the first '::' only; if the prefix is already compressed away
        # there is nothing identifying left to keep.
        head = ip.split('::', 1)[0]
        groups = [g for g in head.split(':') if g]
        kept = groups[:IPV6_KEEP_GROUPS]
        if not kept:
            return '::/48'
        return ':'.join(kept) + '::/48'

    octets = ip.split('.')
    if len(octets) != 4 or not all(o.isdigit() and 0 <= int(o) <= 255 for o in octets):
        return ''
    return '.'.join(octets[:IPV4_KEEP_OCTETS] + ['0']) + '/24'


# ── Published allele frequency ──────────────────────────────────────────────
#
# An unrounded allele frequency is a carrier count in disguise: with 2N alleles
# in the panel, an AF of exactly k/2N inverts to k. That is the classic beacon
# re-identification primitive (Homer 2008; Shringarpure & Bustamante 2015) —
# given a target's genotypes, exact per-variant counts let an attacker test
# panel membership.
#
# Two controls, both applied before anything is published:
#
# 1. ROUNDING. The rounding step must be coarser than 1/2N so that a published
#    value maps to a *range* of possible counts rather than one. The AfriGen-D
#    V6HC-S_AFR panel is 1,895 samples => 2N = 3,790 alleles => 1/2N ~ 0.00026.
#    A 3-decimal grid (step 0.001) is ~4x coarser, so each published value is
#    consistent with roughly four different carrier counts.
#
# 2. SMALL-CELL SUPPRESSION. Rounding alone does not protect the rarest
#    variants, which are the most identifying ones: a true AF of 1/2N still
#    rounds to a distinguishable 0.000 vs 0.001. Anything below the minimum is
#    withheld entirely. At the default 0.01 that is ~38 alleles in the AFR
#    panel — comfortably above the "at least 5 in a cell" rule of thumb.
#
# The complement is disclosive too — an AF of 1 - 1/2N pins down a single
# NON-carrier. At this panel's 2N the rounding grid already collapses that into
# a flat 1.0 (0.00026 < 0.0005), so no separate upper control is applied. A
# materially smaller cohort would need the suppression made symmetric.
#
# Suppression omits the field rather than flooring the value up to the
# threshold: publishing 0.01 for a variant whose true frequency is 0.0001
# would be a factually wrong number in a scientific API. The caller's existing
# ``is not None`` guards already handle the omission.
#
# Neither control touches the boolean ``exists`` answer. That is the beacon's
# core contract; this is only about how precisely the frequency is published.

DEFAULT_AF_DECIMALS = 3
DEFAULT_AF_MIN_PUBLISHED = 0.01


def publish_allele_frequency(frequency,
                             decimals=DEFAULT_AF_DECIMALS,
                             min_frequency=DEFAULT_AF_MIN_PUBLISHED):
    """Round and small-cell-suppress an allele frequency for publication.

    Returns the rounded frequency, or ``None`` when it must not be published
    (absent, non-numeric, zero/negative, or below `min_frequency`).
    """
    if frequency is None or isinstance(frequency, bool):
        return None
    if not isinstance(frequency, (int, float)):
        return None
    if frequency <= 0:
        return None
    if frequency < min_frequency:
        return None
    return round(float(frequency), decimals)
