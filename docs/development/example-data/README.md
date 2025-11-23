# Example Relay Data

This directory contains example and mock data for development and testing.

## 📁 Files

### `1aeo_relays_data.json`
**Size**: 7.9MB  
**Type**: Real Onionoo API response (anonymized)  
**Source**: Snapshot of actual Tor network data

**Use Cases**:
- **Unit Testing**: Mock data for tests without network access
- **Development**: Work on features without hitting live APIs
- **Documentation**: Examples of data structure
- **Performance Testing**: Realistic data set for benchmarking

## 🔧 Usage in Tests

```python
import json
from pathlib import Path

# Load example data
example_data_path = Path(__file__).parent.parent / 'docs/development/example-data/1aeo_relays_data.json'
with open(example_data_path) as f:
    mock_data = json.load(f)

# Use in tests
def test_relay_processing():
    relay_set = Relays(output_dir='/tmp/test', relay_data=mock_data)
    assert len(relay_set.json['relays']) > 0
```

## 📊 Data Structure

The JSON file contains a complete Onionoo details API response with:
- **Relays**: Array of relay objects
- **Bridges**: Array of bridge objects (if any)
- **Version**: Onionoo API version
- **RelaysPublished**: Timestamp of data collection

### Example Relay Object
```json
{
  "fingerprint": "...",
  "nickname": "...",
  "running": true,
  "flags": ["Fast", "Guard", "HSDir", "Running", "Stable", "V2Dir", "Valid"],
  "country": "us",
  "observed_bandwidth": 1234567,
  "consensus_weight": 100,
  "or_addresses": ["1.2.3.4:9001"],
  "platform": "Tor 0.4.8.7 on Linux"
}
```

## ⚠️ Notes

- This data is **anonymized** and safe for public repositories
- Data may be **outdated** - use for structure/testing only, not production
- For **live testing**, use the actual Onionoo API
- Update this file periodically to reflect current API format

---

**Last Updated**: 2025-11-23  
**Data Snapshot Date**: Check file modification date
