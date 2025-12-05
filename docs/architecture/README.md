# Architecture & Design

This section contains high-level system architecture and design documentation for the Allium project.

## 📋 Documents

### [Multiprocessing Architecture](multiprocessing.md)
**Parallel page generation for 40% faster site building**

- **Purpose**: Technical documentation for Allium's multiprocessing implementation
- **Content**: Two-phase approach, fork() context, imap_unordered streaming, flat storage pattern
- **Audience**: Developers working on performance optimization or page generation
- **Impact**: 10x faster contact pages, 40% faster overall page generation

**Key Topics:**
- Parallel contact data precomputation
- Fork-based worker pools with copy-on-write memory sharing
- Streaming results with imap_unordered for lower peak memory
- Flat storage pattern for efficient data access
- Regression testing for multiprocessing correctness

### [Intelligence Engine Design](intelligence-engine-design.md)
**Comprehensive architecture for the smart context intelligence system**

- **Purpose**: Complete design specification for the intelligence engine that powers smart context links and analysis
- **Content**: Architecture patterns, data flow, processing layers, and integration points
- **Audience**: Architects, senior developers, and contributors working on intelligence features
- **Size**: ~26KB, comprehensive technical specification

**Key Topics:**
- Multi-tier intelligence processing architecture
- Data aggregation and analysis patterns  
- Template integration and context generation
- Performance optimization strategies
- Extensibility and maintenance considerations

## 🎯 Overview

The architecture documentation focuses on:

1. **System Design**: Overall architecture patterns and principles
2. **Component Integration**: How different system components interact
3. **Data Flow**: Information processing and transformation pipelines
4. **Performance**: Optimization strategies and efficiency considerations
5. **Extensibility**: Design for future enhancements and maintenance

## 🔗 Related Documentation

- **[Features](../features/)** - Specific feature implementations based on these designs
- **[Performance](../performance/)** - Optimization reports and performance analysis
- **[Implementation](../implementation/)** - Technical implementation details and reports