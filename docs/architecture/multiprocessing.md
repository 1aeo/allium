# Multiprocessing Architecture

This document describes Allium's multiprocessing implementation for parallel page generation, providing ~40% overall speedup and ~10x faster contact page generation.

---

## Overview

Allium uses Python's `multiprocessing` module with `fork()` context to parallelize page generation. This approach leverages copy-on-write memory sharing for efficient data access across worker processes.

### Key Performance Improvements

| Page Type | Before | After | Speedup |
|-----------|--------|-------|---------|
| Contact pages | 54s | 5s | **10x** |
| Family pages | 45s | 39s | 1.2x |
| AS pages | 7s | 3s | 2x |
| First seen pages | 2s | 1.3s | 1.5x |
| **Page Generation Total** | 140s | 80s | **1.75x** |

---

## Architecture

### Two-Phase Approach

The multiprocessing implementation uses a two-phase approach for contact pages:

```
┌─────────────────────────────────────────────────────────────────┐
│                     DATA PROCESSING PHASE                        │
├─────────────────────────────────────────────────────────────────┤
│  1. Parallel Contact Precomputation                             │
│     ├── Worker Pool (fork context)                              │
│     ├── imap_unordered for streaming results                    │
│     └── Store directly on contact_data (flat storage)           │
│                                                                 │
│  Precomputed data:                                              │
│     • contact_rankings (AROI leaderboard positions)             │
│     • operator_reliability (uptime/bandwidth stats)             │
│     • contact_display_data (formatted display values)           │
│     • contact_validation_status (AROI validation)               │
│     • is_validated_aroi (for vanity URLs)                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PAGE GENERATION PHASE                        │
├─────────────────────────────────────────────────────────────────┤
│  2. Parallel Page Rendering                                     │
│     ├── Worker Pool (fork context)                              │
│     ├── Shared template and relay data via fork()               │
│     └── Each worker renders and writes pages independently      │
│                                                                 │
│  Applies to: family, contact, as, first_seen pages              │
│  (threshold: 100+ pages to trigger parallel processing)         │
└─────────────────────────────────────────────────────────────────┘
```

### Why Two Phases?

Contact pages require expensive calculations (rankings, reliability stats) that would be repeated in each worker. By precomputing this data once and storing it on `contact_data`, we:

1. **Avoid redundant computation** - Each worker doesn't recalculate rankings
2. **Enable parallel rendering** - Workers just read precomputed data
3. **Reduce peak memory** - imap_unordered streams results instead of buffering

---

## Implementation Details

### Worker Initialization

Workers are initialized with shared data via fork():

```python
# Global worker state (shared via fork copy-on-write)
_mp_relay_set = None
_mp_template = None

def _init_mp_worker(relay_set, template):
    """Initialize worker with shared data via fork"""
    global _mp_relay_set, _mp_template
    _mp_relay_set = relay_set
    _mp_template = template
```

### Precomputation Worker

The contact precomputation worker computes all expensive data for a single contact:

```python
def _precompute_contact_worker(args):
    """Precompute data for a single contact in worker process."""
    contact_hash, aroi_validation_timestamp, validated_aroi_domains = args
    
    # Get contact data and member relays
    contact_data = _precompute_relay_set.json["sorted"]["contact"][contact_hash]
    members = [_precompute_relay_set.json["relays"][idx] 
               for idx in contact_data.get("relays", [])]
    
    # Compute expensive operations
    contact_rankings = _precompute_relay_set._generate_contact_rankings(contact_hash)
    operator_reliability = _precompute_relay_set._calculate_operator_reliability(...)
    contact_display_data = _precompute_relay_set._compute_contact_display_data(...)
    
    # Return flat dict for direct storage
    return (contact_hash, {
        "contact_rankings": contact_rankings,
        "operator_reliability": operator_reliability,
        "contact_display_data": contact_display_data,
        # ... other fields
    })
```

### Streaming with imap_unordered

Uses `imap_unordered` for lower peak memory and progress reporting:

```python
def _precompute_contacts_parallel(self, contact_hashes, ...):
    ctx = mp.get_context('fork')
    chunk_size = max(50, total_contacts // (self.mp_workers * 4))
    
    with ctx.Pool(self.mp_workers, _init_precompute_worker, (self,)) as pool:
        for contact_hash, precomputed_data in pool.imap_unordered(
            _precompute_contact_worker, worker_args, chunksize=chunk_size
        ):
            # Apply results as they complete (streaming)
            if precomputed_data:
                for key, value in precomputed_data.items():
                    contact_data[key] = value
            
            # Progress reporting every 500 contacts
            processed += 1
            if processed % 500 == 0:
                self._log_progress(f"Pre-computed {processed}/{total} contacts...")
```

### Flat Storage Pattern

Precomputed data is stored directly on `contact_data` for simple access:

```python
# Storing (in precomputation)
contact_data["contact_rankings"] = rankings
contact_data["operator_reliability"] = reliability
contact_data["is_validated_aroi"] = True

# Accessing (in template arg building)
if k == "contact":
    contact_rankings = i.get("contact_rankings", [])
    operator_reliability = i.get("operator_reliability")
    is_validated_aroi = i.get("is_validated_aroi", False)
```

---

## Configuration

### Command Line Options

```bash
# Default: 4 workers
python3 allium.py --out ./www --progress

# Custom worker count
python3 allium.py --out ./www --workers 8

# Disable multiprocessing
python3 allium.py --out ./www --workers 0
```

### Multiprocessing Thresholds

| Setting | Default | Description |
|---------|---------|-------------|
| `--workers` | 4 | Number of parallel workers |
| Page threshold | 100 | Minimum pages to trigger parallel processing |
| Chunk size | 50+ | Minimum chunk size for imap_unordered |

---

## Platform Compatibility

### Fork Context (Linux/macOS)

The implementation uses `fork()` context for efficient copy-on-write memory sharing:

```python
ctx = mp.get_context('fork')
with ctx.Pool(workers, initializer, initargs) as pool:
    pool.map(worker_func, args)
```

### Fallback Behavior

If multiprocessing fails or isn't available (Windows), the code falls back to sequential processing:

```python
use_mp = (self.mp_workers > 0 and len(sorted_values) >= 100 and 
          hasattr(mp, 'get_context'))

if use_mp:
    self._write_pages_parallel(...)
else:
    # Sequential fallback
    for v in sorted_values:
        self._render_page(...)
```

---

## Testing

### Regression Tests

Located in `tests/test_integration_contact_template.py`:

```python
class TestContactMultiprocessingRegression(unittest.TestCase):
    """Regression tests for contact page generation under multiprocessing."""
    
    def test_contact_precomputation_stores_required_metadata(self):
        """Test that precomputation stores all required metadata."""
        
    def test_contact_page_multiprocessing_preserves_metadata(self):
        """Regression test: metadata preserved under mp_workers=2."""
        
    def test_build_template_args_uses_flat_storage(self):
        """Test that template args use flat storage pattern."""
        
    def test_precomputation_stores_aroi_domain_for_vanity_urls(self):
        """Test aroi_domain stored for efficient vanity URL generation."""
```

### Running Tests

```bash
# Run multiprocessing regression tests
python3 -m pytest tests/test_integration_contact_template.py::TestContactMultiprocessingRegression -v

# Run all contact template tests
python3 -m pytest tests/test_integration_contact_template.py -v
```

---

## Troubleshooting

### Common Issues

**Issue**: `fork()` context not available on Windows

**Solution**: Multiprocessing is disabled on Windows; sequential processing is used instead.

---

**Issue**: OOM (Out of Memory) during parallel processing

**Solution**: Reduce worker count with `--workers 2` or disable with `--workers 0`.

---

**Issue**: Missing contact metadata after generation

**Solution**: Check that `_precompute_all_contact_page_data()` is called before page generation (handled by coordinator).

---

## Future Improvements

- [ ] Parallel relay info page generation (11,000+ pages)
- [ ] Adaptive worker count based on system resources
- [ ] Shared memory for large datasets (reduce fork overhead)
- [ ] Progress bars for individual page types

---

**Related**: [Architecture Overview](overview.md) | [Configuration](../user-guide/configuration.md)
