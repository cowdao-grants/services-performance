# Contributing to CoW Performance Testing Suite

Thank you for your interest in contributing to the CoW Performance Testing Suite! This document provides guidelines for contributing to the project.

## Code of Conduct

Be respectful, inclusive, and professional in all interactions.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/cow-performance-testing-suite.git
   cd cow-performance-testing-suite
   ```
3. **Install Poetry** (if not installed):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```
4. **Install dependencies**:
   ```bash
   poetry install --with dev
   ```
5. **Install pre-commit hooks**:
   ```bash
   poetry run pre-commit install
   ```

## Development Workflow

### Creating a Branch

Create a descriptive branch name:
```bash
git checkout -b feature/add-burst-strategy
git checkout -b fix/order-signing-bug
git checkout -b docs/update-readme
```

### Making Changes

1. Write your code following our [coding standards](docs/development.md#coding-standards)
2. Add tests for new functionality
3. Update documentation if needed
4. Run tests and linting:
   ```bash
   poetry run pytest
   poetry run black src/ tests/
   poetry run ruff check src/ tests/
   poetry run mypy src/
   ```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): brief description

Longer description if needed.

- Details
- More details

Fixes #issue_number
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `test`: Tests
- `refactor`: Code refactoring
- `chore`: Maintenance
- `perf`: Performance improvement

**Examples:**
```
feat(cli): add scenario validation command

Add 'cow-perf scenarios validate' command to check scenario
configuration files for errors before execution.

- Implemented ScenarioValidator class
- Added comprehensive error messages
- Updated CLI documentation

Closes #42
```

### Submitting a Pull Request

1. **Push your branch**:
   ```bash
   git push origin feature/your-feature
   ```

2. **Create a Pull Request** on GitHub

3. **PR Checklist**:
   - [ ] Tests pass locally (`pytest`)
   - [ ] Code is formatted (`black --check`)
   - [ ] Linting passes (`ruff check`)
   - [ ] Type checking passes (`mypy src/`)
   - [ ] Tests added for new functionality
   - [ ] Documentation updated
   - [ ] Commit messages follow conventions
   - [ ] PR description explains the changes
   - [ ] Linked related issues

4. **Address review feedback**:
   - Make requested changes
   - Push additional commits
   - Respond to comments

5. **After approval**, a maintainer will merge your PR

## Testing Guidelines

### Writing Tests

- **Unit tests**: Test individual components in isolation
- **Integration tests**: Test component interactions
- **Use descriptive test names**: `test_order_factory_creates_valid_market_order`
- **Follow AAA pattern**: Arrange, Act, Assert
- **Use fixtures**: For common test setup

Example:
```python
def test_order_factory_creates_valid_market_order(trader_pool):
    """Test that OrderFactory creates a valid market order."""
    # Arrange
    factory = OrderFactory()
    trader = trader_pool.get_trader(0)

    # Act
    order = factory.create_market_order(
        sell_token="WETH",
        buy_token="DAI",
        sell_amount=1000000000000000000,
        trader=trader,
    )

    # Assert
    assert order.kind == "sell"
    assert order.sell_token == "WETH"
    assert order.buy_token == "DAI"
    assert order.sell_amount == 1000000000000000000
```

### Running Tests

```bash
# All tests
poetry run pytest

# With coverage
poetry run pytest --cov

# Specific test file
poetry run pytest tests/unit/test_order_factory.py

# Specific test
pytest tests/unit/test_order_factory.py::TestOrderFactory::test_create_market_order
```

## Code Quality

### Before Submitting

Run all quality checks:
```bash
# Format code
poetry run black src/ tests/

# Lint
poetry run ruff check --fix src/ tests/

# Type check
poetry run mypy src/

# Run tests
poetry run pytest

# Or use pre-commit
poetry run pre-commit run --all-files
```

### Code Style

- Follow PEP 8 (enforced by Black)
- Line length: 100 characters
- Use type hints for all functions
- Write Google-style docstrings
- Keep functions focused and small

## Documentation

### Docstrings

Use Google-style docstrings:
```python
def submit_order(order: Order, timeout: float = 30.0) -> OrderResponse:
    """Submit an order to the orderbook API.

    Args:
        order: The order to submit
        timeout: Request timeout in seconds

    Returns:
        Response from the API

    Raises:
        APIError: If submission fails
    """
    pass
```

### Documentation Updates

When adding features:
1. Update relevant documentation in `docs/`
2. Update README.md if needed
3. Add docstrings to new code
4. Update code examples

## Issue Reporting

### Bug Reports

Include:
- Description of the issue
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment (Python version, OS, etc.)
- Relevant logs or error messages

### Feature Requests

Include:
- Description of the feature
- Use case and motivation
- Proposed implementation (optional)
- Impact on existing functionality

## Review Process

Pull requests are reviewed by maintainers:
1. **Automated checks**: CI/CD runs tests and linting
2. **Code review**: Maintainers review the code
3. **Feedback**: You may be asked to make changes
4. **Approval**: After approval, the PR is merged

## Getting Help

- Check [documentation](docs/)
- Search existing [issues](https://github.com/cowprotocol/cow-performance-testing-suite/issues)
- Ask in [discussions](https://github.com/cowprotocol/cow-performance-testing-suite/discussions)
- Reach out to maintainers

## Development Resources

- [Architecture Documentation](docs/architecture.md)
- [Development Guide](docs/development.md)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [Pytest Documentation](https://docs.pytest.org/)
- [AsyncIO Guide](https://docs.python.org/3/library/asyncio.html)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Thank You!

Your contributions make this project better. Thank you for taking the time to contribute!
