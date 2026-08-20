# Contributing to Afrigen Beacon v2

Thank you for your interest in contributing to the Afrigen Beacon v2 project! This document provides guidelines for contributing to the project.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [How to Contribute](#how-to-contribute)
3. [Development Workflow](#development-workflow)
4. [Code Standards](#code-standards)
5. [Testing Guidelines](#testing-guidelines)
6. [Documentation](#documentation)
7. [Pull Request Process](#pull-request-process)
8. [Community](#community)

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of background, experience level, gender identity, sexual orientation, disability, ethnicity, religion, or nationality.

### Expected Behavior

✅ Be respectful and considerate
✅ Welcome newcomers and help them learn
✅ Accept constructive criticism gracefully
✅ Focus on what is best for the community
✅ Show empathy towards other community members

### Unacceptable Behavior

❌ Harassment, discrimination, or offensive comments
❌ Personal attacks or trolling
❌ Publishing others' private information
❌ Inappropriate sexual attention or advances
❌ Other conduct that could reasonably be considered inappropriate

### Enforcement

Violations may result in temporary or permanent ban from the project. Report violations to: conduct@h3abionet.org

---

## How to Contribute

### Ways to Contribute

**1. Report Bugs**
- Search existing issues first
- Use the bug report template
- Provide detailed reproduction steps
- Include system information

**2. Suggest Features**
- Check if feature already requested
- Use the feature request template
- Explain use case and benefits
- Be open to feedback

**3. Improve Documentation**
- Fix typos and errors
- Add examples and clarifications
- Update outdated information
- Translate documentation

**4. Contribute Code**
- Fix bugs
- Implement features
- Improve performance
- Add tests

### Before You Start

1. **Check Issues**: Look for existing issues or create a new one
2. **Discuss First**: For major changes, discuss in an issue first
3. **Claim Issue**: Comment on the issue to claim it
4. **Get Approval**: Wait for maintainer approval before starting work

---

## Development Workflow

### 1. Fork and Clone

```bash
# Fork the repository on GitHub
# Then clone your fork
git clone https://github.com/YOUR_USERNAME/variant-checker-beacon.git
cd variant-checker-beacon

# Add upstream remote
git remote add upstream https://github.com/AfriGen-D/variant-checker-beacon.git
```

### 2. Create a Branch

```bash
# Update main branch
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/your-feature-name

# Or bug fix branch
git checkout -b fix/bug-description
```

**Branch Naming**:
- `feature/feature-name` - New features
- `fix/bug-description` - Bug fixes
- `docs/topic` - Documentation updates
- `refactor/component` - Code refactoring
- `test/component` - Test additions

### 3. Set Up Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Start development services
docker-compose up -d mongodb redis

# Load sample data
python scripts/load_mongo_data.py

# Run development server
./run.sh
```

### 4. Make Changes

- Write clean, readable code
- Follow code standards (see below)
- Add/update tests
- Update documentation
- Commit regularly with clear messages

### 5. Test Your Changes

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=beacon_api --cov-report=html

# Run linters
black beacon_api/
flake8 beacon_api/
mypy beacon_api/

# Run security tests
./scripts/run_security_tests.sh
```

### 6. Commit Changes

```bash
# Stage changes
git add .

# Commit with descriptive message
git commit -m "Add feature X that does Y

- Implement component A
- Update documentation for B
- Add tests for C

Fixes #123"
```

**Commit Message Format**:
```
<type>: <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code restructuring
- `test`: Tests
- `chore`: Maintenance

**Example**:
```
feat: Add GA4GH AAI authentication

- Implement passport validation
- Add visa extraction logic
- Update authentication middleware

Implements #234
```

### 7. Push and Create Pull Request

```bash
# Push to your fork
git push origin feature/your-feature-name

# Create Pull Request on GitHub
# Fill out the PR template completely
```

---

## Code Standards

### Python Style

**Follow PEP 8** with these specifics:

**Formatting**:
- Use **Black** for auto-formatting
- Line length: 88 characters (Black default)
- 4 spaces for indentation (no tabs)

**Naming Conventions**:
```python
# Functions and variables: snake_case
def calculate_frequency(allele_count):
    total_count = 1000
    return allele_count / total_count

# Classes: PascalCase
class GenomicVariant(Document):
    pass

# Constants: UPPER_CASE
MAX_VARIANTS = 1000000
DEFAULT_ASSEMBLY = 'GRCh38'

# Private: _leading_underscore
def _internal_helper():
    pass
```

**Type Hints**:
```python
from typing import List, Dict, Optional

def query_variants(
    assembly_id: str,
    reference_name: str,
    start: int,
    end: Optional[int] = None
) -> List[Dict]:
    """Query genomic variants

    Args:
        assembly_id: Reference genome assembly
        reference_name: Chromosome name
        start: Start position (0-based)
        end: End position (0-based, exclusive)

    Returns:
        List of variant dictionaries
    """
    pass
```

**Docstrings** (Google Style):
```python
def complex_function(param1: str, param2: int) -> bool:
    """Brief description of function

    Detailed description explaining what the function does,
    including any important notes or caveats.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: If param2 is negative
        KeyError: If required key not found

    Example:
        >>> complex_function("test", 42)
        True
    """
    pass
```

### Django Best Practices

**Models**:
```python
class GenomicVariant(Document):
    """GA4GH Beacon v2 Genomic Variant

    Represents a genomic variant conforming to the
    GA4GH Beacon v2 specification.
    """

    id = StringField(required=True, primary_key=True)
    assembly_id = StringField(required=True)

    def __str__(self):
        return f"{self.reference_name}:{self.start}"

    meta = {
        'collection': 'variants',
        'indexes': ['assembly_id', 'reference_name']
    }
```

**Views**:
```python
class BooleanVariantView(APIView):
    """Boolean mode variant query endpoint

    Returns YES/NO response indicating variant existence.
    """

    def get(self, request):
        # Validate inputs
        try:
            assembly_id = validate_assembly_id(
                request.GET.get('assemblyId')
            )
        except ValidationError as e:
            return Response(
                {'error': {'errorCode': 400, 'errorMessage': str(e)}},
                status=400
            )

        # Query database
        exists = GenomicVariant.objects(**query).count() > 0

        # Return response
        return Response({'exists': exists})
```

### Security Best Practices

✅ **Always validate user input**
✅ **Use parameterized queries (MongoEngine handles this)**
✅ **Never expose sensitive information in errors**
✅ **Log security events**
✅ **Check for OWASP Top 10 vulnerabilities**

**Example**:
```python
# Good: Validation
def validate_chromosome(value):
    valid = ['1', '2', ..., '22', 'X', 'Y', 'MT']
    if value not in valid:
        raise ValidationError(f"Invalid chromosome: {value}")
    return value

# Bad: No validation
def get_variants(chromosome):
    return GenomicVariant.objects(reference_name=chromosome)
```

---

## Testing Guidelines

### Test Structure

```
beacon_api/tests/
├── __init__.py
├── test_models.py
├── test_views.py
├── test_serializers.py
├── test_validators.py
└── test_security.py
```

### Writing Tests

**Test Class**:
```python
from django.test import TestCase
from beacon_api.models import GenomicVariant

class GenomicVariantTestCase(TestCase):
    """Test GenomicVariant model"""

    def setUp(self):
        """Set up test data"""
        self.variant = GenomicVariant(
            id='test_variant',
            assembly_id='GRCh38',
            reference_name='1',
            start=100000
        )
        self.variant.save()

    def test_variant_creation(self):
        """Test variant can be created"""
        self.assertEqual(self.variant.reference_name, '1')
        self.assertEqual(self.variant.start, 100000)

    def test_variant_str(self):
        """Test string representation"""
        self.assertEqual(str(self.variant), '1:100000')

    def tearDown(self):
        """Clean up test data"""
        GenomicVariant.objects.delete()
```

**API Test**:
```python
from rest_framework.test import APIClient

class BooleanAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_boolean_query_success(self):
        """Test successful Boolean query"""
        response = self.client.get(
            '/api/g_variants',
            {'referenceName': '1', 'start': 100000}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('exists', response.json())
        self.assertIsInstance(response.json()['exists'], bool)

    def test_invalid_chromosome(self):
        """Test invalid chromosome returns 400"""
        response = self.client.get(
            '/api/g_variants',
            {'referenceName': '999', 'start': 100000}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())
```

### Test Coverage

**Target**: 80%+ code coverage

```bash
# Run with coverage
pytest --cov=beacon_api --cov-report=html

# View report
open htmlcov/index.html
```

### Test Requirements

✅ **Unit tests** for all new functions
✅ **Integration tests** for API endpoints
✅ **Edge cases** (empty inputs, null values, etc.)
✅ **Error cases** (invalid inputs, exceptions)
✅ **Security tests** (input validation, rate limiting)

---

## Documentation

### Code Documentation

**Docstrings Required For**:
- All public functions
- All classes
- Complex logic

**Not Required For**:
- Simple getters/setters
- Obvious one-liners
- Test functions (but test names should be descriptive)

### Updating Documentation

When making changes, update:

- **README.md** - If changing installation or usage
- **API_REFERENCE.md** - If adding/changing endpoints
- **DATABASE_SCHEMA.md** - If changing models
- **SECURITY_IMPLEMENTATION.md** - If changing security
- **Inline comments** - For complex logic

### Documentation Style

- Use clear, simple language
- Provide examples
- Keep up-to-date with code
- Use proper markdown formatting

---

## Pull Request Process

### Before Submitting

✅ **Tests pass**: `pytest`
✅ **Linting passes**: `black beacon_api/ && flake8 beacon_api/`
✅ **Documentation updated**
✅ **Commits are clean** (squash if needed)
✅ **Branch is up-to-date**: `git pull upstream main`

### PR Checklist

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Checklist
- [ ] Tests added/updated
- [ ] Tests passing
- [ ] Documentation updated
- [ ] Code formatted (Black)
- [ ] Linting passing (Flake8)
- [ ] No merge conflicts
- [ ] Commit messages follow guidelines

## Related Issues
Fixes #123
Implements #456

## Testing
Describe how to test the changes

## Screenshots (if applicable)
Add screenshots for UI changes
```

### Review Process

1. **Automated Checks**: CI/CD runs tests and linting
2. **Code Review**: Maintainer reviews code
3. **Feedback**: Address review comments
4. **Approval**: Maintainer approves PR
5. **Merge**: Maintainer merges PR

### After Merge

- Delete your branch: `git branch -d feature/your-feature-name`
- Update your fork: `git pull upstream main`
- Thank the reviewers!

---

## Community

### Communication Channels

**GitHub Issues**: Bug reports, feature requests
**Email**: beacon-dev@h3abionet.org
**Meetings**: Monthly contributor calls (TBD)

### Getting Help

- **Documentation**: [docs/](docs/)
- **API Reference**: [docs/API_REFERENCE.md](docs/API_REFERENCE.md)
- **Project Overview**: [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)
- **Issues**: Ask in GitHub issues

### Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Acknowledged in release notes
- Invited to contributor calls

---

## Development Resources

### Project Structure

See [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md#core-components) for detailed component documentation.

### Key Technologies

- **Django 4.0**: Web framework
- **Django REST Framework**: API framework
- **MongoDB**: Database
- **MongoEngine**: ODM
- **Redis**: Caching
- **Docker**: Deployment

### External Resources

- [GA4GH Beacon v2 Spec](https://beacon-project.io/)
- [Django Documentation](https://docs.djangoproject.com/)
- [MongoDB Manual](https://docs.mongodb.com/)
- [DRF Documentation](https://www.django-rest-framework.org/)

---

## Questions?

**Not sure where to start?**
- Check "good first issue" label on GitHub
- Ask in an issue or email beacon-dev@h3abionet.org

**Have questions about the code?**
- Read [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)
- Check existing issues
- Ask maintainers

---

## Thank You!

Your contributions make this project better for the African genomics community. We appreciate your time and effort! 🧬

---

**Last Updated**: 2025-01-26
**Version**: 1.0
