# GA4GH AAI Implementation Plan

## Executive Summary

This document outlines the implementation plan for migrating the Afrigen Beacon v2 from JWT-based authentication to **GA4GH Authentication and Authorization Infrastructure (AAI)**, enabling federated authentication and fine-grained authorization through the Passport and Visa system.

**Current State**: JWT token-based authentication (Secure mode only)
**Target State**: GA4GH AAI with ELIXIR AAI integration, Passport & Visa support
**Timeline**: 6+ months (phased approach)
**Status**: Planning phase

---

## Table of Contents

1. [Introduction](#introduction)
2. [GA4GH AAI Overview](#ga4gh-aai-overview)
3. [Current Authentication Limitations](#current-authentication-limitations)
4. [Implementation Phases](#implementation-phases)
5. [Technical Architecture](#technical-architecture)
6. [Migration Strategy](#migration-strategy)
7. [Testing Plan](#testing-plan)
8. [Timeline and Milestones](#timeline-and-milestones)
9. [Success Criteria](#success-criteria)
10. [References](#references)

---

## Introduction

### Why GA4GH AAI?

**GA4GH AAI** (Authentication and Authorization Infrastructure) is a federated identity and authorization standard designed for genomics data sharing. It provides:

1. **Federated Authentication**: Users authenticate with their home institution
2. **Fine-Grained Authorization**: Visa-based access control
3. **Standardization**: Compatible with other GA4GH services
4. **Privacy**: Minimal information disclosure
5. **Scalability**: Supports multi-institutional collaborations

### Current vs Target State

| Feature | Current (JWT) | Target (GA4GH AAI) |
|---------|---------------|---------------------|
| **Authentication** | Local username/password | Federated (ELIXIR, eduGAIN, Google, ORCID) |
| **User Management** | Local database | External IdPs |
| **Authorization** | Simple RBAC | Visa-based permissions |
| **Federation** | Not supported | Full federation support |
| **Standards** | Custom JWT | GA4GH AAI v1.1 |

---

## GA4GH AAI Overview

### Components

**1. Passports**
- Container for user identity claims and visas
- Issued by trusted Passport Brokers
- JWT format signed by broker
- Short-lived (5-15 minutes)

**2. Visas**
- Authorization claims embedded in passports
- Define what user can access
- Types: ControlledAccessGrants, ResearcherStatus, AcceptedTermsAndPolicies, AffiliationAndRole

**3. Passport Brokers**
- Issue and validate passports
- Aggregate visas from multiple sources
- Examples: ELIXIR AAI, NIH RAS

**4. Visa Issuers**
- Organizations that issue visas
- Data Access Committees (DACs)
- Institutions

**5. Visa Asserters**
- Verify visa claims
- Can be same as issuer or third-party

### Passport Structure

```json
{
  "header": {
    "typ": "JWT",
    "alg": "RS256",
    "kid": "key-1"
  },
  "payload": {
    "iss": "https://login.elixir-czech.org/oidc/",
    "sub": "user@example.org",
    "exp": 1706270700,
    "iat": 1706270400,
    "jti": "abc123",
    "ga4gh_visa_v1": [
      {
        "type": "ControlledAccessGrants",
        "asserted": 1706270400,
        "value": "https://dac.example.org/datasets/dataset_001",
        "source": "https://dac.example.org",
        "by": "dac"
      },
      {
        "type": "ResearcherStatus",
        "asserted": 1706270400,
        "value": "https://doi.org/10.1038/s41431-018-0219-y",
        "source": "https://institution.edu",
        "by": "system"
      }
    ]
  },
  "signature": "..."
}
```

### Visa Types

**ControlledAccessGrants**: Permission to access specific dataset
```json
{
  "type": "ControlledAccessGrants",
  "value": "https://dac.example.org/datasets/dataset_001",
  "source": "https://dac.example.org",
  "by": "dac"
}
```

**ResearcherStatus**: Verified researcher status
```json
{
  "type": "ResearcherStatus",
  "value": "https://doi.org/10.1038/s41431-018-0219-y",
  "source": "https://institution.edu",
  "by": "peer"
}
```

**AcceptedTermsAndPolicies**: Accepted data use terms
```json
{
  "type": "AcceptedTermsAndPolicies",
  "value": "https://beacon.example.org/terms/v1.0",
  "source": "https://beacon.example.org",
  "by": "self"
}
```

**AffiliationAndRole**: Institutional affiliation
```json
{
  "type": "AffiliationAndRole",
  "value": "faculty@institution.edu",
  "source": "https://institution.edu",
  "by": "so"
}
```

---

## Access Levels and Response Granularity

The GA4GH Beacon v2 specification defines a two-dimensional access model where **access levels** (who can query) and **response granularity** (what they see) are configured independently. Our beacon's full access × granularity matrix, endpoint access policies, data sensitivity classification, and visa mapping are documented in:

**[Security Implementation — GA4GH Beacon v2 Access and Granularity Model](SECURITY_IMPLEMENTATION.md#ga4gh-beacon-v2-access-and-granularity-model)**

Key points relevant to AAI implementation:
- **PUBLIC** access requires no authentication (current Boolean mode)
- **REGISTERED** access requires a GA4GH Passport with `ResearcherStatus` visa
- **CONTROLLED** access requires `ControlledAccessGrants` + `AcceptedTermsAndPolicies` visas
- Population allele frequencies are classified as PUBLIC-safe (aggregate data)
- Individual/biosample/analysis data requires CONTROLLED access

---

## Current Authentication Limitations

### JWT Limitations

1. **No Federation**: Users must create separate accounts
2. **Manual Access Control**: Admins must manually grant permissions
3. **No Standards**: Custom JWT implementation
4. **Scaling Issues**: Managing users across institutions
5. **Limited Interoperability**: Not compatible with other GA4GH services

### Current JWT Flow

```
User → Login Page → Django Auth → JWT Token → API Requests
```

**Pain Points**:
- New users must register
- Password management burden
- No single sign-on (SSO)
- Manual permission grants
- Not compatible with GA4GH ecosystem

---

## Implementation Phases

### Phase 1: ELIXIR AAI Integration (Months 1-2)

**Goal**: Enable authentication via ELIXIR AAI

**Deliverables**:
- OAuth2/OIDC client registration with ELIXIR AAI
- OIDC authentication flow implementation
- User profile synchronization
- Backward compatibility with existing JWT

**Tasks**:
1. Register application with ELIXIR AAI
2. Implement OIDC authentication flow
3. Create user mapping (ELIXIR ID → local user)
4. Test with ELIXIR AAI sandbox
5. Deploy to production

**Success Criteria**:
- Users can log in with ELIXIR AAI
- User profiles synchronized
- Existing JWT users unaffected

---

### Phase 2: Passport Validation (Months 3-4)

**Goal**: Validate and extract visas from GA4GH Passports

**Deliverables**:
- Passport JWT validation
- Visa extraction and parsing
- Visa claim verification
- Trusted broker registry

**Tasks**:
1. Implement passport JWT validation
2. Extract and parse visa claims
3. Verify visa signatures
4. Implement trusted broker list
5. Test with sample passports

**Success Criteria**:
- Passports validated correctly
- Visas extracted and parsed
- Signature verification working

---

### Phase 3: Visa-Based Authorization (Months 5-6)

**Goal**: Implement fine-grained authorization based on visas

**Deliverables**:
- Visa-to-permission mapping
- Dataset access control via ControlledAccessGrants visas
- ResearcherStatus verification
- AcceptedTermsAndPolicies checking

**Tasks**:
1. Design visa-to-permission mapping
2. Implement access control checks
3. Create permission evaluation engine
4. Test with sample visas
5. Document visa requirements per dataset

**Success Criteria**:
- Users with valid visas can access datasets
- Users without visas are denied access
- Visa expiration enforced
- Audit logging of visa usage

---

### Phase 4: Multi-IdP Support (Months 7-9)

**Goal**: Support multiple identity providers beyond ELIXIR

**Deliverables**:
- NIH RAS integration
- eduGAIN support
- Google OAuth integration
- ORCID support

**Tasks**:
1. Implement multi-IdP discovery
2. Add NIH RAS OIDC client
3. Test with multiple IdPs
4. Update documentation
5. User account linking

**Success Criteria**:
- Users can choose from multiple IdPs
- Seamless authentication across IdPs
- Account linking works

---

### Phase 5: Advanced Features (Months 10+)

**Goal**: Advanced GA4GH AAI features

**Deliverables**:
- Visa refreshing
- Visa caching
- Passport refresh tokens
- Beacon as Visa Issuer (for internal permissions)

**Tasks**:
1. Implement visa refresh mechanism
2. Cache visas with appropriate TTL
3. Implement refresh token handling
4. Design Beacon visa issuance
5. Test end-to-end

---

## Technical Architecture

### Authentication Flow (with GA4GH AAI)

```
┌──────────┐
│  User    │
└────┬─────┘
     │ 1. Click "Login with ELIXIR"
     ▼
┌─────────────────────┐
│  Beacon Frontend    │
└────┬────────────────┘
     │ 2. Redirect to ELIXIR AAI
     ▼
┌─────────────────────────────────┐
│  ELIXIR AAI (IdP)               │
│  - User authenticates           │
│  - Fetches visas from DACs      │
│  - Creates passport with visas  │
└────┬────────────────────────────┘
     │ 3. Redirect back with authorization code
     ▼
┌──────────────────────────────────┐
│  Beacon Backend                  │
│  4. Exchange code for passport   │
│  5. Validate passport signature  │
│  6. Extract visas                │
│  7. Map visas to permissions     │
│  8. Create session               │
└────┬─────────────────────────────┘
     │ 9. Return session token
     ▼
┌──────────────────────────────────┐
│  Beacon Frontend                 │
│  10. Store session token         │
│  11. Include in API requests     │
└──────────────────────────────────┘
```

### Authorization Flow (Visa-Based)

```
User makes API request with passport
     │
     ▼
Beacon extracts visas from passport
     │
     ▼
Check dataset requires ControlledAccessGrants visa
     │
     ▼
Find matching visa: value="https://dac.org/datasets/dataset_001"
     │
     ├─ Visa found & valid → Allow access
     │
     └─ No visa or expired → Deny access (403)
```

### Database Schema Changes

**New Collections**:

```python
class TrustedBroker(Document):
    """Trusted Passport Brokers"""
    issuer_url = StringField(required=True, unique=True)
    name = StringField(required=True)
    public_key_url = StringField(required=True)
    active = BooleanField(default=True)

class VisaCache(Document):
    """Cached visa claims"""
    user_id = StringField(required=True)
    visa_type = StringField(required=True)
    visa_value = StringField(required=True)
    visa_source = StringField(required=True)
    asserted_timestamp = IntField(required=True)
    expires_at = DateTimeField(required=True)

class DatasetAccessRequirement(Document):
    """Dataset access requirements"""
    dataset_id = StringField(required=True)
    required_visa_type = StringField(required=True)
    required_visa_value = StringField()
```

### Code Architecture

**New Modules**:

```
beacon_api/
├── ga4gh_aai/
│   ├── __init__.py
│   ├── passport.py       # Passport validation
│   ├── visa.py           # Visa extraction and verification
│   ├── brokers.py        # Trusted broker management
│   ├── authorization.py  # Visa-based access control
│   └── oidc.py           # OIDC authentication flow
```

**passport.py** (example):

```python
import jwt
import requests
from typing import List, Dict

class PassportValidator:
    """Validate GA4GH Passports"""

    def __init__(self, trusted_brokers: List[str]):
        self.trusted_brokers = trusted_brokers
        self.public_keys = {}

    def validate(self, passport_jwt: str) -> Dict:
        """Validate passport and extract visas"""
        # Decode header without verification to get issuer
        unverified = jwt.decode(passport_jwt, options={"verify_signature": False})
        issuer = unverified['iss']

        # Check if issuer is trusted
        if issuer not in self.trusted_brokers:
            raise ValueError(f"Untrusted issuer: {issuer}")

        # Get public key for issuer
        public_key = self._get_public_key(issuer)

        # Validate signature
        payload = jwt.decode(
            passport_jwt,
            public_key,
            algorithms=['RS256'],
            audience='beacon.example.org'
        )

        # Extract visas
        visas = payload.get('ga4gh_visa_v1', [])

        return {
            'subject': payload['sub'],
            'issuer': issuer,
            'visas': visas,
            'expires_at': payload['exp']
        }

    def _get_public_key(self, issuer: str) -> str:
        """Fetch public key from issuer's JWKS endpoint"""
        if issuer not in self.public_keys:
            jwks_url = f"{issuer}/.well-known/jwks.json"
            response = requests.get(jwks_url)
            jwks = response.json()
            # Extract and cache public key
            self.public_keys[issuer] = jwks['keys'][0]

        return self.public_keys[issuer]
```

**authorization.py** (example):

```python
class VisaAuthorizer:
    """Visa-based authorization"""

    def can_access_dataset(self, visas: List[Dict], dataset_id: str) -> bool:
        """Check if user has required visa for dataset"""
        # Get dataset requirements
        requirement = DatasetAccessRequirement.objects(
            dataset_id=dataset_id
        ).first()

        if not requirement:
            # No specific requirement, allow if researcher
            return self._has_researcher_status(visas)

        # Check for matching ControlledAccessGrants visa
        required_value = f"https://dac.example.org/datasets/{dataset_id}"

        for visa in visas:
            if visa['type'] == 'ControlledAccessGrants' and \
               visa['value'] == required_value:
                # Check visa not expired
                if self._is_visa_valid(visa):
                    return True

        return False

    def _has_researcher_status(self, visas: List[Dict]) -> bool:
        """Check if user has verified researcher status"""
        for visa in visas:
            if visa['type'] == 'ResearcherStatus' and \
               self._is_visa_valid(visa):
                return True
        return False

    def _is_visa_valid(self, visa: Dict) -> bool:
        """Check if visa is still valid"""
        # Visas typically valid for 6 months
        asserted = visa['asserted']
        now = int(time.time())
        return (now - asserted) < (6 * 30 * 24 * 60 * 60)
```

---

## Migration Strategy

### Backward Compatibility

**Dual Authentication Support**:

```python
# settings_secure.py
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'beacon_api.ga4gh_aai.authentication.GA4GHPassportAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',  # Fallback
    ],
}
```

### User Migration Path

**Phase 1**: Existing JWT users continue unchanged
**Phase 2**: New users can choose JWT or ELIXIR AAI
**Phase 3**: Encourage migration to ELIXIR AAI
**Phase 4**: Deprecate JWT (6-month notice)
**Phase 5**: Remove JWT support

### Configuration

```python
# GA4GH AAI settings
GA4GH_AAI_ENABLED = True
GA4GH_TRUSTED_BROKERS = [
    'https://login.elixir-czech.org/oidc/',
    'https://stsstg.nih.gov',
]
GA4GH_VISA_TYPES = [
    'ControlledAccessGrants',
    'ResearcherStatus',
    'AcceptedTermsAndPolicies',
]

# ELIXIR AAI OIDC
ELIXIR_AAI_CLIENT_ID = os.getenv('ELIXIR_AAI_CLIENT_ID')
ELIXIR_AAI_CLIENT_SECRET = os.getenv('ELIXIR_AAI_CLIENT_SECRET')
ELIXIR_AAI_REDIRECT_URI = 'https://beacon.example.org/auth/callback'
```

---

## Testing Plan

### Unit Tests

```python
class PassportValidationTestCase(TestCase):
    def test_validate_elixir_passport(self):
        """Test ELIXIR AAI passport validation"""
        passport = create_test_passport(issuer='https://login.elixir-czech.org/oidc/')
        validator = PassportValidator(trusted_brokers=[...])

        result = validator.validate(passport)

        self.assertEqual(result['subject'], 'user@example.org')
        self.assertEqual(len(result['visas']), 2)

    def test_reject_untrusted_broker(self):
        """Test rejection of untrusted broker"""
        passport = create_test_passport(issuer='https://untrusted.org')
        validator = PassportValidator(trusted_brokers=[...])

        with self.assertRaises(ValueError):
            validator.validate(passport)

class VisaAuthorizationTestCase(TestCase):
    def test_dataset_access_with_valid_visa(self):
        """Test dataset access with valid ControlledAccessGrants visa"""
        visas = [{
            'type': 'ControlledAccessGrants',
            'value': 'https://dac.example.org/datasets/dataset_001',
            'asserted': int(time.time())
        }]

        authorizer = VisaAuthorizer()
        can_access = authorizer.can_access_dataset(visas, 'dataset_001')

        self.assertTrue(can_access)
```

### Integration Tests

- Test full OIDC authentication flow with ELIXIR AAI sandbox
- Test visa extraction from real passports
- Test access control with various visa combinations
- Test backward compatibility with JWT

### User Acceptance Testing

- Pilot with 10-20 users from partner institutions
- Gather feedback on authentication flow
- Measure authentication success rates
- Document common issues

---

## Timeline and Milestones

### Detailed Timeline

**Month 1-2: ELIXIR AAI Integration**
- Week 1-2: OIDC client registration and setup
- Week 3-4: Authentication flow implementation
- Week 5-6: User profile synchronization
- Week 7-8: Testing and documentation

**Month 3-4: Passport Validation**
- Week 9-10: Passport JWT validation
- Week 11-12: Visa extraction
- Week 13-14: Signature verification
- Week 15-16: Testing

**Month 5-6: Visa-Based Authorization**
- Week 17-18: Permission mapping design
- Week 19-20: Access control implementation
- Week 21-22: Testing with sample data
- Week 23-24: Documentation and training

**Month 7-9: Multi-IdP Support**
- Week 25-28: NIH RAS integration
- Week 29-32: eduGAIN support
- Week 33-36: Testing and refinement

**Month 10+: Advanced Features**
- Visa caching and refreshing
- Beacon as visa issuer
- Performance optimization

### Key Milestones

| Milestone | Target Date | Status |
|-----------|-------------|--------|
| ELIXIR AAI integration complete | Month 2 | Not Started |
| Passport validation working | Month 4 | Not Started |
| Visa-based authorization live | Month 6 | Not Started |
| Multi-IdP support | Month 9 | Not Started |
| JWT deprecation notice | Month 12 | Not Started |
| JWT removal | Month 18 | Not Started |

---

## Success Criteria

### Functional Requirements

- ✅ Users can authenticate with ELIXIR AAI
- ✅ Passports validated correctly
- ✅ Visas extracted and parsed
- ✅ Access control based on visas works
- ✅ Backward compatibility with JWT
- ✅ Multiple IdPs supported

### Non-Functional Requirements

- ✅ Authentication latency < 2 seconds
- ✅ 99.9% authentication success rate
- ✅ Zero data breaches during migration
- ✅ Comprehensive documentation
- ✅ User satisfaction > 80%

### Adoption Metrics

- **Target**: 50% of users migrated to GA4GH AAI by Month 12
- **Target**: 90% of users migrated by Month 18
- **Target**: JWT fully deprecated by Month 24

---

## References

### GA4GH AAI Specification

- [GA4GH AAI Specification v1.1](https://github.com/ga4gh-duri/ga4gh-duri.github.io/blob/master/researcher_ids/ga4gh_passport_v1.md)
- [GA4GH AAI OpenID Connect Profile](https://github.com/ga4gh-duri/ga4gh-duri.github.io/blob/master/researcher_ids/oidc_profile.md)
- [Visa Specification](https://github.com/ga4gh-duri/ga4gh-duri.github.io/blob/master/researcher_ids/ga4gh_passport_v1.md#ga4gh-visa)

### ELIXIR AAI

- [ELIXIR AAI Documentation](https://elixir-europe.org/services/compute/aai)
- [ELIXIR AAI Developer Guide](https://elixir-europe.org/platforms/compute/aai)
- [ELIXIR AAI Service Registry](https://login.elixir-czech.org/oidc/)

### Implementation Examples

- [Beacon Reference Implementation](https://github.com/EGA-archive/beacon2-ri-api)
- [REMS (Resource Entitlement Management System)](https://github.com/CSCfi/rems)
- [GA4GH Passport Broker Reference](https://github.com/GoogleCloudPlatform/ga4gh-passport-broker)

### Internal Documentation

- [Security Implementation](SECURITY_IMPLEMENTATION.md)
- [API Reference](API_REFERENCE.md)
- [Project Overview](PROJECT_OVERVIEW.md)

---

**Document Version**: 1.0
**Last Updated**: 2025-01-26
**Status**: Planning Phase
**Next Review**: 2025-04-01
