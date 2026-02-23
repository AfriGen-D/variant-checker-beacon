# Contributing to AfriGend Beacon v2 Tools

We welcome contributions to the AfriGend Beacon v2 Tools project! This document provides guidelines for contributing code, documentation, bug reports, and feature requests.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Setup](#development-setup)
3. [Contributing Code](#contributing-code)
4. [Testing](#testing)
5. [Documentation](#documentation)
6. [Bug Reports](#bug-reports)
7. [Feature Requests](#feature-requests)
8. [Code Style](#code-style)
9. [Review Process](#review-process)
10. [Community Guidelines](#community-guidelines)

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- MongoDB (for testing import/export functionality)
- Familiarity with genomics data formats (VCF, phenotypes)
- Understanding of Beacon v2 specification

### Ways to Contribute

- **Code contributions**: Bug fixes, new features, performance improvements
- **Documentation**: Improve existing docs, add examples, write tutorials
- **Testing**: Write tests, report bugs, test on different platforms
- **Community**: Help answer questions, review pull requests
- **Translation**: Translate documentation (future)

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR-USERNAME/afrigend-beacon2.git
cd afrigend-beacon2/afrigend-beacon2-tools

# Add upstream remote
git remote add upstream https://github.com/ORIGINAL-OWNER/afrigend-beacon2.git
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

### 3. Install Pre-commit Hooks

```bash
# Install pre-commit hooks
pre-commit install

# Run hooks on all files (optional)
pre-commit run --all-files
```

### 4. Verify Installation

```bash
# Run tests
python -m pytest tests/ -v

# Test basic functionality
python vcf_transform/vcf_to_beacon.py --help
python validation/validate_json.py --help
```

## Contributing Code

### Workflow

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**:
   - Write code following our style guidelines
   - Add tests for new functionality
   - Update documentation as needed

3. **Test your changes**:
   ```bash
   # Run all tests
   python -m pytest tests/ -v
   
   # Run specific tests
   python -m pytest tests/test_vcf_transform.py -v
   
   # Test with sample data
   python scripts/test_with_samples.py
   ```

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: add support for custom ontologies"
   ```

5. **Push and create pull request**:
   ```bash
   git push origin feature/your-feature-name
   ```

### Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples**:
```
feat(vcf): add support for multi-sample VCF files
fix(validation): handle edge case in schema validation
docs(readme): update installation instructions
test(phenotype): add tests for ontology mapping
```

### Code Organization

```
afrigend-beacon2-tools/
├── vcf_transform/          # VCF processing modules
├── phenotype_transform/    # Phenotype processing modules
├── validation/            # Data validation modules
├── data_import/           # MongoDB import modules
├── data_export/           # MongoDB export modules
├── config/                # Configuration files
├── examples/              # Workflow scripts
├── tests/                 # Test files
├── docs/                  # Documentation
└── scripts/               # Utility scripts
```

### Adding New Features

#### 1. VCF Processing Features

```python
# vcf_transform/vcf_to_beacon.py
class VCFTransformer:
    def add_custom_annotation(self, vcf_record):
        """Add custom annotation extraction logic."""
        # Implementation here
        pass
```

#### 2. Phenotype Processing Features

```python
# phenotype_transform/phenotype_to_beacon.py
class PhenotypeTransformer:
    def map_custom_ontology(self, term_id):
        """Add support for new ontology."""
        # Implementation here
        pass
```

#### 3. Validation Features

```python
# validation/validate_json.py
class BeaconValidator:
    def validate_custom_schema(self, data, schema):
        """Add custom validation rules."""
        # Implementation here
        pass
```

### Configuration Changes

When adding new configuration options:

1. **Update `config/settings.yaml`**:
   ```yaml
   new_feature:
     enabled: true
     parameter: "default_value"
   ```

2. **Update configuration documentation**:
   - Add to `docs/CONFIGURATION.md`
   - Include examples and explanations

3. **Add validation**:
   ```python
   def validate_config(config):
       # Add validation for new parameters
       pass
   ```

## Testing

### Test Structure

```
tests/
├── test_vcf_transform.py      # VCF processing tests
├── test_phenotype_transform.py # Phenotype processing tests
├── test_validation.py         # Validation tests
├── test_data_import.py        # Import tests
├── test_data_export.py        # Export tests
├── test_config.py             # Configuration tests
├── fixtures/                  # Test data files
└── conftest.py               # Test configuration
```

### Writing Tests

#### Unit Tests

```python
import pytest
from vcf_transform.vcf_to_beacon import VCFTransformer

class TestVCFTransformer:
    def test_process_variant_record(self):
        """Test variant record processing."""
        transformer = VCFTransformer()
        # Test implementation
        assert result == expected
    
    def test_quality_filtering(self):
        """Test quality filter application."""
        # Test implementation
        pass
```

#### Integration Tests

```python
def test_full_vcf_workflow(tmp_path):
    """Test complete VCF transformation workflow."""
    # Setup test data
    input_vcf = tmp_path / "test.vcf"
    output_dir = tmp_path / "output"
    
    # Run transformation
    transformer = VCFTransformer()
    results = transformer.transform_vcf(input_vcf, output_dir)
    
    # Verify results
    assert results['total_variants'] > 0
    assert (output_dir / "variants_batch.jsonl").exists()
```

#### Test Data

- Use small, representative test files
- Include edge cases and error conditions
- Anonymize any real genomic data
- Document test data sources

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_vcf_transform.py -v

# Run tests with coverage
python -m pytest tests/ --cov=. --cov-report=html

# Run tests in parallel
python -m pytest tests/ -n auto

# Run only failed tests
python -m pytest --lf
```

## Documentation

### Documentation Types

1. **Code documentation**: Docstrings, inline comments
2. **User documentation**: Guides, tutorials, examples
3. **API documentation**: Function and class references
4. **Configuration documentation**: Settings and options

### Writing Documentation

#### Docstrings

Use Google-style docstrings:

```python
def transform_vcf(self, vcf_path: str, output_dir: str, **kwargs) -> dict:
    """Transform VCF file to Beacon v2 format.
    
    Args:
        vcf_path: Path to input VCF file
        output_dir: Directory for output files
        **kwargs: Additional transformation options
        
    Returns:
        Dictionary containing transformation results and statistics
        
    Raises:
        ValueError: If VCF file format is invalid
        FileNotFoundError: If input file doesn't exist
        
    Example:
        >>> transformer = VCFTransformer()
        >>> results = transformer.transform_vcf("input.vcf", "./output")
        >>> print(f"Processed {results['total_variants']} variants")
    """
```

#### User Documentation

- Write clear, step-by-step instructions
- Include practical examples
- Cover common use cases and edge cases
- Use consistent formatting and terminology

#### Code Examples

```python
# Good: Complete, runnable example
from vcf_transform.vcf_to_beacon import VCFTransformer

transformer = VCFTransformer(assembly="GRCh38")
results = transformer.transform_vcf(
    vcf_path="sample.vcf",
    output_dir="./output",
    metadata_path="individuals.csv"
)
print(f"Transformed {results['total_variants']} variants")
```

### Documentation Updates

When making changes:

1. **Update relevant documentation files**
2. **Add examples for new features**
3. **Update API reference if needed**
4. **Check documentation builds correctly**

## Bug Reports

### Before Reporting

1. **Search existing issues** to avoid duplicates
2. **Test with latest version** to ensure bug still exists
3. **Gather system information** and error details
4. **Create minimal reproduction case** if possible

### Bug Report Template

```markdown
**Bug Description**
Clear description of the bug and expected behavior.

**Steps to Reproduce**
1. Step one
2. Step two
3. Step three

**Error Messages**
```
Paste complete error messages here
```

**System Information**
- OS: [e.g., Ubuntu 20.04]
- Python version: [e.g., 3.9.7]
- Package version: [e.g., 1.0.0]
- MongoDB version: [e.g., 5.0.3]

**Sample Data**
If possible, provide sample data that reproduces the issue.

**Additional Context**
Any other relevant information.
```

## Feature Requests

### Before Requesting

1. **Check existing issues and roadmap**
2. **Consider if feature fits project scope**
3. **Think about implementation complexity**
4. **Prepare use case and examples**

### Feature Request Template

```markdown
**Feature Description**
Clear description of the proposed feature.

**Use Case**
Explain why this feature would be useful and who would benefit.

**Proposed Implementation**
If you have ideas about how to implement this feature.

**Examples**
Code examples or mockups showing how the feature would work.

**Alternatives Considered**
Other approaches you've considered.
```

## Code Style

### Python Style

We follow [PEP 8](https://pep8.org/) with some modifications:

```python
# Line length: 88 characters (Black default)
# Use type hints
def process_data(input_file: str, options: dict) -> dict:
    """Process input data with given options."""
    pass

# Use descriptive variable names
vcf_file_path = "input.vcf"
transformation_results = {}

# Use f-strings for formatting
message = f"Processed {count} records in {duration:.2f} seconds"
```

### Tools

We use these tools for code formatting and linting:

```bash
# Format code
black .

# Sort imports
isort .

# Lint code
flake8 .

# Type checking
mypy .
```

### Configuration

```toml
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py38']

[tool.isort]
profile = "black"
line_length = 88

[tool.mypy]
python_version = "3.8"
warn_return_any = true
warn_unused_configs = true
```

## Review Process

### Pull Request Guidelines

1. **Clear title and description**
2. **Link to related issues**
3. **Include tests for new features**
4. **Update documentation**
5. **Follow code style guidelines**

### Review Criteria

Reviewers will check:

- **Functionality**: Does the code work as intended?
- **Tests**: Are there adequate tests?
- **Documentation**: Is documentation updated?
- **Style**: Does code follow style guidelines?
- **Performance**: Are there performance implications?
- **Security**: Are there security considerations?

### Addressing Review Comments

1. **Respond to all comments**
2. **Make requested changes**
3. **Ask for clarification if needed**
4. **Update tests and documentation**
5. **Request re-review when ready**

## Community Guidelines

### Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please:

- **Be respectful** in all interactions
- **Be constructive** when giving feedback
- **Be patient** with newcomers
- **Be collaborative** in problem-solving

### Communication

- **GitHub Issues**: Bug reports, feature requests
- **Pull Requests**: Code contributions, discussions
- **Discussions**: General questions, ideas
- **Email**: Security issues, private matters

### Recognition

Contributors will be recognized in:

- **CONTRIBUTORS.md** file
- **Release notes** for significant contributions
- **Documentation** for major features
- **Project website** (future)

## Getting Help

If you need help contributing:

1. **Check existing documentation**
2. **Search GitHub issues and discussions**
3. **Ask questions in GitHub discussions**
4. **Contact maintainers for complex issues**

## Resources

### External Resources

- [Beacon v2 Specification](https://beacon-project.io/)
- [VCF Specification](https://samtools.github.io/hts-specs/VCFv4.3.pdf)
- [Human Phenotype Ontology](https://hpo.jax.org/)
- [MongoDB Documentation](https://docs.mongodb.com/)

### Project Resources

- [User Guide](USER_GUIDE.md)
- [API Reference](API_REFERENCE.md)
- [Configuration Guide](CONFIGURATION.md)
- [Troubleshooting](TROUBLESHOOTING.md)

Thank you for contributing to AfriGend Beacon v2 Tools! 