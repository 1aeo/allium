# Allium Documentation

Welcome to the complete documentation for Allium, an advanced Tor relay analytics platform.

## 📚 Documentation Sections

### 👥 For Users
Start here if you want to **generate and deploy** Allium sites:

- **[User Guide](user-guide/README.md)** - Installation, configuration, and usage
  - [Quick Start](user-guide/quick-start.md) - Get running in 5 minutes
  - [Configuration](user-guide/configuration.md) - Customize behavior
  - [Updating](user-guide/updating.md) - Keep data fresh
  - [Features](user-guide/features.md) - Understanding generated content

### 👨‍💻 For Developers
Start here if you want to **contribute code** or customize Allium:

- **[Development Guide](development/README.md)** - Contributing and development setup
  - [Testing Guide](development/testing.md) - Test standards and practices
  - [Performance](development/performance.md) - Current status and optimization
  - [Security](development/security.md) - Security practices and guidelines
  - [Example Data](development/example-data/) - Mock data for testing

### 🏗️ Architecture
Understand how Allium works internally:

- **[Architecture Overview](architecture/README.md)** - System design and data flow
  - [Data Pipeline](architecture/data-pipeline.md) - How data flows through the system
  - [Template Optimization](architecture/template-optimization.md) - Rendering performance

### 🔌 API Documentation
Understanding data sources:

- **[API Guide](api/README.md)** - Onionoo API integration
  - Details API - Core relay information
  - Uptime API - Historical uptime data
  - Bandwidth API - Historical bandwidth data

### 🗺️ Features & Roadmap
Current and planned functionality:

- **[Features](features/README.md)** - Feature documentation
  - [Implemented Features](features/implemented/) - Working features
  - [Planned Features](features/planned/) - Future enhancements

### 📦 Archive
Historical documentation preserved for reference:

- **[Archive](archive/README.md)** - Completed work and historical reports
  - [Implementation Reports](archive/implementation-reports/) - Past implementations
  - [Performance Details](archive/performance-details/) - Optimization history
  - [Security Details](archive/security-details/) - Security audit history

---

## 🎯 Quick Start Paths

### Path 1: I want to **use** Allium
1. Read [User Guide: Quick Start](user-guide/quick-start.md)
2. Install and generate your first site
3. Explore [Features](user-guide/features.md) to understand output

### Path 2: I want to **develop** Allium
1. Read [Development Guide](development/README.md)
2. Set up development environment
3. Review [Testing Standards](development/testing.md)
4. Check [Architecture Overview](architecture/README.md)

### Path 3: I want to **understand** Allium
1. Read main [README](../README.md) for overview
2. Explore [Features Guide](user-guide/features.md)
3. Dive into [Architecture](architecture/README.md)
4. Review [API Documentation](api/README.md)

---

## 📖 Documentation Organization

This documentation is organized by **audience** and **purpose**:

| Section | Audience | Purpose |
|---------|----------|---------|
| **User Guide** | End users | Installation, configuration, usage |
| **Development** | Contributors | Code guidelines, testing, optimization |
| **Architecture** | Technical readers | System design, data flow |
| **API** | Integrators | Data source specifications |
| **Features** | All | Current and planned functionality |
| **Archive** | Reference | Historical context |

---

## 🔍 Finding Information

### Common Questions

**"How do I install Allium?"**  
→ [User Guide: Quick Start](user-guide/quick-start.md)

**"How do I configure automated updates?"**  
→ [User Guide: Configuration](user-guide/configuration.md#-automated-updates-cron)

**"What are AROI leaderboards?"**  
→ [User Guide: Features](user-guide/features.md#-aroi-leaderboards-miscaroi-leaderboardshtml)

**"How do I run tests?"**  
→ [Development: Testing](development/testing.md)

**"What's the current performance status?"**  
→ [Development: Performance](development/performance.md)

**"How secure is Allium?"**  
→ [Development: Security](development/security.md)

**"How does the data pipeline work?"**  
→ [Architecture: Data Pipeline](architecture/data-pipeline.md)

**"What optimizations have been done?"**  
→ [Archive: Performance Details](archive/performance-details/)

---

## 📝 Contributing to Documentation

Documentation contributions are welcome! When adding or updating docs:

1. **User-facing docs** → `user-guide/`
2. **Developer docs** → `development/`
3. **Architecture docs** → `architecture/`
4. **API specs** → `api/`
5. **Feature docs** → `features/implemented/` or `features/planned/`
6. **Historical reports** → `archive/[appropriate-subdir]/`

### Documentation Standards
- Use clear, concise language
- Include code examples where appropriate
- Link to related documentation
- Keep formatting consistent
- Update relevant READMEs

---

## 🔗 External Resources

- **[Main Project README](../README.md)** - Project overview
- **[GitHub Repository](https://github.com/1aeo/allium)** - Source code
- **[Onionoo API](https://onionoo.torproject.org/)** - Data source
- **[Tor Metrics](https://metrics.torproject.org/)** - Official Tor metrics

---

## 📅 Documentation Updates

This documentation structure was established on **2025-11-23** to improve organization and accessibility.

**Previous documentation** has been archived in `archive/` with proper indexing for reference.

**Ongoing updates** focus on keeping user and developer guides current while preserving historical context.

---

**Questions?** Open an issue on GitHub or check the relevant guide section above.
