# Beacon Boolean Mode - Quick Start Guide

Welcome to the **AfriGen-D Beacon** Boolean mode! This guide will help you start querying genomic data using our privacy-preserving discovery API at [`beacon.afrigen-d.org`](https://beacon.afrigen-d.org/).

---

## What is Boolean Mode?

**Boolean Mode** is a privacy-preserving way to discover genomic variants. Instead of returning detailed variant information, the API returns only **YES** or **NO** to indicate whether a variant exists in the dataset.

### Why Boolean Mode?

✅ **Privacy-First**: No personally identifiable information exposed
✅ **Public Access**: No authentication required
✅ **Simple**: Just YES/NO responses
✅ **Fast**: Cached responses for quick queries
✅ **Compliant**: GA4GH Beacon v2 specification

### Boolean vs Secure Mode

| Feature | Boolean Mode | Secure Mode |
|---------|--------------|-------------|
| **Authentication** | None | JWT required |
| **Response** | YES/NO only | Full variant details |
| **Rate Limit** | 50 requests/hour | 1,000 requests/hour |
| **Use Case** | Discovery | Detailed analysis |
| **Access** | Public | Authorized users only |

---

## Getting Started

### Quick Example

Try this simple query in your terminal:

```bash
curl "https://beacon.afrigen-d.org/api/g_variants?\
assemblyId=GRCh38&\
referenceName=1&\
start=100000&\
referenceBases=A&\
alternateBases=T"
```

**Response**:
```json
{"exists": true}
```

That's it! You've just queried the Beacon.

---

## API Endpoint

**Production**: `https://beacon.afrigen-d.org/api/`

**Local Development**: `http://localhost:8000/api/`

---

## Query Examples

### Example 1: Check for Specific SNP

**Query**: Does the dataset contain a specific SNP at position 100,000 on chromosome 1?

```bash
curl "https://beacon.afrigen-d.org/api/g_variants?\
assemblyId=GRCh38&\
referenceName=1&\
start=100000&\
referenceBases=A&\
alternateBases=T"
```

**Response**:
```json
{"exists": true}
```

### Example 2: Check Multiple Variants

Check multiple positions sequentially:

```bash
# Variant 1
curl "https://beacon.afrigen-d.org/api/g_variants?assemblyId=GRCh38&referenceName=1&start=100000"
# Response: {"exists": true}

# Variant 2
curl "https://beacon.afrigen-d.org/api/g_variants?assemblyId=GRCh38&referenceName=1&start=200000"
# Response: {"exists": false}

# Variant 3
curl "https://beacon.afrigen-d.org/api/g_variants?assemblyId=GRCh38&referenceName=2&start=300000"
# Response: {"exists": true}
```

### Example 3: Query Chromosome X

```bash
curl "https://beacon.afrigen-d.org/api/g_variants?\
assemblyId=GRCh38&\
referenceName=X&\
start=12345678&\
referenceBases=G&\
alternateBases=C"
```

### Example 4: Query Mitochondrial DNA

```bash
curl "https://beacon.afrigen-d.org/api/g_variants?\
assemblyId=GRCh38&\
referenceName=MT&\
start=10000&\
referenceBases=A&\
alternateBases=G"
```

### Example 5: Indel Query

```bash
curl "https://beacon.afrigen-d.org/api/g_variants?\
assemblyId=GRCh38&\
referenceName=3&\
start=5000000&\
referenceBases=ATCG&\
alternateBases=A"
```

### Example 6: Check by Position Only

```bash
# Minimum query (position only)
curl "https://beacon.afrigen-d.org/api/g_variants?\
assemblyId=GRCh38&\
referenceName=1&\
start=100000"
```

---

## Query Parameters

### Required Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `assemblyId` | String | Reference genome assembly | `GRCh38`, `GRCh37` |
| `referenceName` | String | Chromosome | `1`-`22`, `X`, `Y`, `MT` |
| `start` | Integer | Start position (0-based, inclusive) | `100000` |

### Optional Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `referenceBases` | String | Reference allele | `A`, `AT`, `AGC` |
| `alternateBases` | String | Alternate allele | `T`, `G`, `ATCG` |
| `end` | Integer | End position (0-based, exclusive) | `100001` |

### Parameter Notes

**assemblyId**:
- `GRCh38` (recommended, latest)
- `GRCh37` (older, still supported)

**referenceName** (chromosome):
- Autosomes: `1`, `2`, ..., `22`
- Sex chromosomes: `X`, `Y`
- Mitochondrial: `MT`

**start** (position):
- 0-based coordinate system
- Inclusive (variant starts at this position)
- Must be ≥ 0

**referenceBases** and **alternateBases**:
- DNA sequence: `A`, `C`, `G`, `T`, `N`
- Can be single nucleotide or multiple (indels)

---

## Integration Examples

### Python

```python
import requests

def query_beacon(assembly, chrom, position, ref=None, alt=None):
    """Query Beacon Boolean mode"""
    url = "https://beacon.afrigen-d.org/api/g_variants"

    params = {
        "assemblyId": assembly,
        "referenceName": chrom,
        "start": position
    }

    if ref:
        params["referenceBases"] = ref
    if alt:
        params["alternateBases"] = alt

    response = requests.get(url, params=params)
    return response.json()["exists"]

# Example usage
if query_beacon("GRCh38", "1", 100000, "A", "T"):
    print("Variant found!")
else:
    print("Variant not found")

# Query multiple variants
variants = [
    ("1", 100000, "A", "T"),
    ("1", 200000, "G", "C"),
    ("2", 300000, "C", "A"),
]

for chrom, pos, ref, alt in variants:
    exists = query_beacon("GRCh38", chrom, pos, ref, alt)
    print(f"chr{chrom}:{pos} {ref}>{alt}: {exists}")
```

### JavaScript

```javascript
async function queryBeacon(assembly, chrom, position, ref, alt) {
    const params = new URLSearchParams({
        assemblyId: assembly,
        referenceName: chrom,
        start: position
    });

    if (ref) params.append('referenceBases', ref);
    if (alt) params.append('alternateBases', alt);

    const url = `https://beacon.afrigen-d.org/api/g_variants?${params}`;

    const response = await fetch(url);
    const data = await response.json();

    return data.exists;
}

// Example usage
queryBeacon('GRCh38', '1', 100000, 'A', 'T')
    .then(exists => {
        console.log(exists ? 'Variant found!' : 'Variant not found');
    });

// Query multiple variants
const variants = [
    {chrom: '1', pos: 100000, ref: 'A', alt: 'T'},
    {chrom: '1', pos: 200000, ref: 'G', alt: 'C'},
];

Promise.all(
    variants.map(v => queryBeacon('GRCh38', v.chrom, v.pos, v.ref, v.alt))
).then(results => {
    results.forEach((exists, i) => {
        const v = variants[i];
        console.log(`chr${v.chrom}:${v.pos} ${v.ref}>${v.alt}: ${exists}`);
    });
});
```

### R

```r
library(httr)
library(jsonlite)

query_beacon <- function(assembly, chrom, position, ref = NULL, alt = NULL) {
  url <- "https://beacon.afrigen-d.org/api/g_variants"

  query_params <- list(
    assemblyId = assembly,
    referenceName = chrom,
    start = position
  )

  if (!is.null(ref)) query_params$referenceBases <- ref
  if (!is.null(alt)) query_params$alternateBases <- alt

  response <- GET(url, query = query_params)
  content <- content(response, as = "parsed")

  return(content$exists)
}

# Example usage
exists <- query_beacon("GRCh38", "1", 100000, "A", "T")
if (exists) {
  print("Variant found!")
} else {
  print("Variant not found")
}

# Query multiple variants
variants <- data.frame(
  chrom = c("1", "1", "2"),
  position = c(100000, 200000, 300000),
  ref = c("A", "G", "C"),
  alt = c("T", "C", "A")
)

variants$exists <- mapply(
  query_beacon,
  assembly = "GRCh38",
  chrom = variants$chrom,
  position = variants$position,
  ref = variants$ref,
  alt = variants$alt
)

print(variants)
```

### cURL Script

```bash
#!/bin/bash
# beacon_query.sh

BEACON_URL="https://beacon.afrigen-d.org/api/g_variants"
ASSEMBLY="GRCh38"

query_variant() {
  local chrom=$1
  local pos=$2
  local ref=$3
  local alt=$4

  response=$(curl -s "${BEACON_URL}?\
assemblyId=${ASSEMBLY}&\
referenceName=${chrom}&\
start=${pos}&\
referenceBases=${ref}&\
alternateBases=${alt}")

  exists=$(echo "$response" | jq -r '.exists')

  if [ "$exists" == "true" ]; then
    echo "chr${chrom}:${pos} ${ref}>${alt}: FOUND"
  else
    echo "chr${chrom}:${pos} ${ref}>${alt}: NOT FOUND"
  fi
}

# Query multiple variants
query_variant 1 100000 A T
query_variant 1 200000 G C
query_variant 2 300000 C A
```

---

## Rate Limiting

### Limits

**Rate Limit**: 50 requests per hour per IP address

**Why Rate Limiting?**
- Prevents abuse
- Protects against re-identification attacks
- Ensures fair usage

### Checking Rate Limit

Response headers include rate limit information:

```bash
curl -i "https://beacon.afrigen-d.org/api/g_variants?assemblyId=GRCh38&referenceName=1&start=100000"
```

**Headers**:
```
X-RateLimit-Limit: 50
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1706270400
```

### Rate Limit Exceeded

After 50 requests in an hour:

```bash
curl "https://beacon.afrigen-d.org/api/g_variants?..."
```

**Response** (HTTP 429):
```json
{
  "error": {
    "errorCode": 429,
    "errorMessage": "Rate limit exceeded. Try again in 3456 seconds"
  }
}
```

### Best Practices

✅ **Cache Results**: Store responses locally
✅ **Batch Queries**: Plan queries in advance
✅ **Check Headers**: Monitor remaining requests
✅ **Implement Backoff**: Wait before retrying
✅ **Upgrade to Secure Mode**: 1,000 requests/hour with authentication

---

## Caching

**Cache Duration**: 5 minutes

**Why Caching?**
- Faster response times
- Reduced server load
- Consistent response times

**Cache Headers**:
```
X-Cache-Status: HIT
Cache-Control: public, max-age=300
```

**What This Means**:
- First query: ~200ms response time
- Cached query: ~10ms response time
- Cache expires after 5 minutes

---

## Error Handling

### Common Errors

**Invalid Chromosome (400)**:
```bash
curl "https://beacon.afrigen-d.org/api/g_variants?referenceName=999&start=100000"
```

```json
{
  "error": {
    "errorCode": 400,
    "errorMessage": "Invalid chromosome: 999. Must be 1-22, X, Y, or MT"
  }
}
```

**Negative Position (400)**:
```bash
curl "https://beacon.afrigen-d.org/api/g_variants?referenceName=1&start=-100"
```

```json
{
  "error": {
    "errorCode": 400,
    "errorMessage": "Position cannot be negative: -100"
  }
}
```

**Invalid DNA Bases (400)**:
```bash
curl "https://beacon.afrigen-d.org/api/g_variants?referenceName=1&start=100000&referenceBases=XYZ"
```

```json
{
  "error": {
    "errorCode": 400,
    "errorMessage": "Invalid referenceBases: XYZ. Must contain only A, C, G, T, or N"
  }
}
```

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Successful query |
| 400 | Bad Request | Invalid parameters |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Service temporarily down |

---

## FAQ

### Q: What data is available?

**A**: The Boolean mode provides access to genomic variant data from African populations. For dataset details, visit: https://beacon.afrigen-d.org/

### Q: Can I get detailed variant information?

**A**: Boolean mode returns only YES/NO. For full variant details, you'll need to upgrade to **Secure Mode** (authentication required).

### Q: How do I get more than 50 requests per hour?

**A**: Upgrade to [Secure Mode](docs/API_REFERENCE.md#authentication) for 1,000 requests/hour with authentication.

### Q: Why am I getting {"exists": false} for known variants?

**A**: Possible reasons:
- Variant not in this dataset
- Wrong assembly (try GRCh37 instead of GRCh38)
- Wrong chromosome name format (use "1" not "chr1")
- Position is 0-based (not 1-based)

### Q: What's the difference between start and end positions?

**A**:
- **start**: 0-based, inclusive (variant begins here)
- **end**: 0-based, exclusive (variant ends before this)
- For SNPs: end = start + 1

### Q: Can I query a genomic region?

**A**: In Boolean mode, you can only check specific positions. For region queries, use [Secure Mode](docs/API_REFERENCE.md#secure-mode-authenticated).

### Q: Is my query data stored?

**A**: Basic query logging for security and monitoring only. No personal information is collected in Boolean mode.

### Q: Can I use this API commercially?

**A**: The API is for research purposes. For commercial use, please contact: beacon-admin@h3abionet.org

---

## Upgrading to Secure Mode

Need more features? **Secure Mode** offers:

✅ **Full Variant Details**: Complete variant records, not just YES/NO
✅ **Higher Rate Limits**: 1,000 requests/hour (vs 50/hour)
✅ **Advanced Queries**: Filter by gene, disease, phenotype
✅ **Individual & Biosample Data**: Access to phenotype and sample information
✅ **Bulk Export**: Download datasets

**How to Upgrade**:
1. Register for an account
2. Request dataset access
3. Obtain JWT token
4. Use token in API requests

See [API Reference](docs/API_REFERENCE.md#authentication) for details.

---

## Additional Resources

- **Complete API Documentation**: [docs/API_REFERENCE.md](docs/API_REFERENCE.md)
- **Project Overview**: [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)
- **Security Details**: [docs/SECURITY_IMPLEMENTATION.md](docs/SECURITY_IMPLEMENTATION.md)
- **GA4GH Beacon Specification**: https://beacon-project.io/

---

## Support

**Questions?** Contact: beacon-support@h3abionet.org

**Issues?** Report: https://github.com/afrigen/afrigen-beacon-v2/issues

**H3ABioNet**: https://h3abionet.org/

---

## Quick Reference

**Base URL**: `https://beacon.afrigen-d.org/api/g_variants`

**Required Parameters**: `assemblyId`, `referenceName`, `start`

**Optional Parameters**: `referenceBases`, `alternateBases`, `end`

**Response**: `{"exists": true}` or `{"exists": false}`

**Rate Limit**: 50 requests/hour

**Cache**: 5 minutes

---

**Happy Querying! 🧬**

---

**Last Updated**: 2025-01-26
**Version**: 1.0
**Beacon Version**: v2.0
