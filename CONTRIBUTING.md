# Contributing to Allium

Thank you for your interest in contributing to Allium! This guide explains how to set up your development environment and contribute to the project.

## 🚀 Quick Developer Setup

For contributors who want to run tests and use development tools:

```bash
# Clone the repository
git clone https://github.com/1aeo/allium.git
cd allium

# Developer setup with testing dependencies
curl -sSL https://raw.githubusercontent.com/1aeo/allium/master/setup.sh | bash -s -- --dev
```

**Or manually:**

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install development dependencies (includes all testing tools)
python -m pip install -r config/requirements-dev.txt

# Run allium
python3 allium/allium.py --progress
```

## 📦 Dependency Structure

### Production Dependencies (`config/requirements.txt`)
- **Jinja2 ≥2.11.2** - Template engine

### Development Dependencies (`config/requirements-dev.txt`)
- **pytest ≥6.0.0** - Unit testing framework
- **pytest-cov ≥2.10.0** - Coverage reporting
- **flake8 ≥3.8.0** - Code style checker
- **bandit ≥1.7.0** - Security vulnerability scanner
- **safety ≥1.10.0** - Dependency vulnerability checker
- **djlint ≥1.0.0** - HTML/template linter
- **memory-profiler ≥0.60.0** - Memory usage profiling

## 🧪 Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_utils.py

# Run linting
flake8 .

# Run security scan
bandit -r .

# Check for vulnerable dependencies
safety check
```

## 🏗️ Development vs Production

### For Production Users (Default)
- Use `curl -sSL https://raw.githubusercontent.com/1aeo/allium/master/setup.sh | bash`
- Only installs Jinja2 (minimal dependencies)
- Optimized for deployment and running the site generator

### For Contributors/Developers
- Use `curl -sSL https://raw.githubusercontent.com/1aeo/allium/master/setup.sh | bash -s -- --dev`
- Installs all testing and development tools
- Includes linting, security scanning, and testing frameworks

## 🛠️ Development Workflow

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Create a feature branch**: `git checkout -b feature/your-feature`
4. **Set up development environment**: Use the developer setup above
5. **Make your changes** and add tests if applicable
6. **Run tests**: `pytest` and `flake8 .`
7. **Commit your changes**: `git commit -am "Add your feature"`
8. **Push to your fork**: `git push origin feature/your-feature`
9. **Create a Pull Request** on GitHub

## 📝 Code Style

- Follow PEP 8 guidelines
- Use `flake8` for linting
- Keep lines under 127 characters
- Add docstrings for new functions and classes
- Use type hints where appropriate

## 🔒 Security

- Run `bandit -r .` to check for security issues
- Use `safety check` to verify dependencies are secure
- Follow secure coding practices
- Sanitize all user inputs in templates

## 📋 Pull Request Guidelines

- Include tests for new features
- Update documentation if needed
- Ensure all CI checks pass
- Write clear commit messages
- Reference related issues in your PR description

## 🐛 Reporting Issues

When reporting bugs, please include:
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages and logs

## 💡 Feature Requests

- Check existing issues first
- Explain the use case
- Provide implementation ideas if possible
- Consider backward compatibility

## 🤝 Getting Help

- Open an issue for questions
- Check the documentation in `docs/`
- Review existing code for patterns and examples