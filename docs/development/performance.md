# Performance Guide

This document outlines Allium's current performance status, optimization priorities, and guidelines for maintaining and improving performance.

---

## 📊 Current Performance Status

### Site Generation
- **Full Site Generation**: ~3.5 minutes for 10,000+ relays ✅ *Improved via multiprocessing*
- **Memory Usage**: Peak ~3.2GB during processing
- **Output Size**: ~21,700 HTML files
- **Page Generation Phase**: ~80 seconds (down from 140s with multiprocessing)
- **Contact Page Generation**: ~5 seconds (down from 54s - **10x faster**)

### Page Load Performance
- **Main Pages**: <2 seconds (target met)
- **AROI Leaderboards**: 712KB, fast load
- **Network Health Dashboard**: 95KB, fast load
- **Individual Relay Pages**: Optimized, instant load

### Template Rendering
- **Optimization Level**: High - logic moved from templates to Python
- **Pre-computation**: Extensive (bandwidth formatting, contact rankings, operator reliability)
- **Multiprocessing**: Parallel page generation for family, contact, AS, and first_seen pages
- **Jinja2 Performance**: 97-99% of render time (expected, optimized)

---

## 🎯 Active Performance Priorities

### Priority 1: Reduce Memory Usage
**Current**: 3.1GB peak  
**Target**: <2GB peak  
**Status**: 🔴 In Progress

**Strategies**:
- Implement lazy loading for relay data
- Use generators instead of list comprehensions
- Cache computed values efficiently
- Stream template rendering

### Priority 2: Faster Generation Time
**Current**: ~3.5 minutes  
**Target**: <3 minutes  
**Status**: ✅ Significantly Improved

**Implemented** (see [Multiprocessing Architecture](../architecture/multiprocessing.md)):
- ✅ Parallel page generation using fork() context
- ✅ Parallel contact data precomputation
- ✅ Streaming results with imap_unordered
- ✅ Chunked processing with progress reporting

### Priority 3: Maintain Page Load Speed
**Current**: <2 seconds  
**Target**: Maintain <2 seconds  
**Status**: ✅ Target Met

**Strategies**:
- Keep HTML files optimized
- Monitor file sizes
- Continue pre-computation approach
- Avoid client-side processing

---

## 🔍 Performance Testing

### Running Performance Tests

```bash
# Full generation with progress tracking
cd allium
time python3 allium.py --out /tmp/perf-test --progress

# Memory profiling
python3 -m memory_profiler allium.py --out /tmp/perf-test

# Check output size
du -sh /tmp/perf-test
find /tmp/perf-test -name "*.html" | wc -l
```

### Key Metrics to Monitor

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Generation Time | 3.5 min | <3 min | 🟡 |
| Page Generation | 80s | <90s | ✅ |
| Contact Pages | 5s | <10s | ✅ |
| Peak Memory | 3.2GB | <2GB | 🔴 |
| Page Load Time | <2s | <2s | ✅ |
| Output Size | 21.7k files | Stable | ✅ |
| Template Render % | 97-99% | Acceptable | ✅ |

---

## 🚀 Optimization Techniques

### Already Implemented
✅ **Template Pre-computation** - Moved logic from Jinja2 to Python  
✅ **Bandwidth Formatting** - Pre-computed for all relays  
✅ **HTML Escaping** - Centralized and optimized  
✅ **Parallel API Fetching** - Concurrent API calls  
✅ **Smart Caching** - API response caching  
✅ **Statistical Pre-calculation** - Network stats computed once  
✅ **Multiprocessing Page Generation** - Fork-based parallel rendering (~70% speedup)  
✅ **Contact Data Precomputation** - Parallel precompute with imap_unordered (~10x speedup)  
✅ **Streaming Results** - imap_unordered for lower peak memory  

### In Development
🔄 **Lazy Loading** - Load data on demand  
🔄 **Generator Patterns** - Reduce memory footprint  

### Planned
📋 **Incremental Updates** - Only regenerate changed pages  
📋 **Advanced Caching** - Redis/Memcached support  

---

## 📈 Performance Benchmarks

### Historical Progress
See [archive/performance-details/](../archive/performance-details/) for detailed optimization reports:

- **AROI Leaderboard Optimization**: 95% improvement in rare country calculations
- **Template Optimization**: Reduced Jinja2 logic by 50%+
- **Duplicate Merging**: Eliminated redundant data processing

### Recent Improvements (2024-2025)
- ✅ Rare country calculation: O(n²) → O(n) - 95% faster
- ✅ Template logic reduction: 50%+ decrease in complexity
- ✅ HTML escaping: Centralized, 3x fewer operations
- ✅ Uptime processing: Single-pass calculation
- ✅ **Multiprocessing**: Page generation parallelized - 40% faster overall
- ✅ **Contact Precomputation**: 10x faster contact pages (54s → 5s)

---

## 🔧 Developer Guidelines

### Writing Performance-Conscious Code

#### ✅ DO:
```python
# Use generators for large datasets
def process_relays(relays):
    for relay in relays:
        yield process_relay(relay)

# Cache expensive calculations
@cached_property
def network_totals(self):
    return self._calculate_totals()

# Pre-compute display data
relay['formatted_bandwidth'] = format_bandwidth(relay['bandwidth'])
```

#### ❌ DON'T:
```python
# Avoid list comprehensions on large datasets
all_relays = [process_relay(r) for r in relays]  # Creates full list in memory

# Don't recalculate in loops
for relay in relays:
    network_total = sum(r['bandwidth'] for r in relays)  # Recalculates every iteration

# Don't do formatting in templates
{{ relay.bandwidth / 1000000 }}  # Move to Python
```

### Performance Testing Checklist
- [ ] Profile memory usage with large datasets
- [ ] Time critical operations
- [ ] Check output file sizes
- [ ] Verify page load times
- [ ] Test with real Onionoo data
- [ ] Compare before/after benchmarks

---

## 📚 Resources

### Internal Documentation
- [Architecture Overview](../architecture/overview.md) - System design
- [Multiprocessing Architecture](../architecture/multiprocessing.md) - Parallel page generation
- [Data Pipeline](../architecture/data-pipeline.md) - Data flow optimization
- [Template Optimization](../architecture/template-optimization.md) - Rendering performance

### Historical Reports
See [archive/performance-details/](../archive/performance-details/) for:
- Detailed optimization reports
- Benchmarking results
- Historical performance data
- Optimization case studies

### Tools
- **memory_profiler**: Python memory profiling
- **cProfile**: Python performance profiling
- **time**: Basic timing measurements
- **pytest-benchmark**: Test suite benchmarking

---

## 🎯 Contributing Performance Improvements

1. **Identify bottleneck** - Profile first, optimize second
2. **Measure baseline** - Record current performance
3. **Implement improvement** - Make targeted changes
4. **Measure impact** - Compare before/after
5. **Document results** - Add to performance reports
6. **Submit PR** - Include benchmarks

---

**Last Updated**: 2025-12-05  
**Current Status**: Excellent performance with multiprocessing  
**Next Review**: Q2 2025
