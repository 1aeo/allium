# Example Relay Data

**Audience**: Contributors  
**Scope**: Snapshot fixture data for offline development and testing

This directory contains example and mock data for development and testing.

## Files

### `1aeo_relays_data.json`
- **Size**: 7.9MB
- **Type**: Real Onionoo API response (anonymized)
- **Source**: Snapshot of actual Tor network data

**Use Cases**:
- **Unit Testing**: Mock data for tests without network access
- **Development**: Work on features without hitting live APIs
- **Documentation**: Examples of data structure
- **Performance Testing**: Realistic data set for benchmarking

## Usage in Tests

```python
import json
import pytest
from allium.lib.relays import Relays


@pytest.fixture
def mock_data(pytestconfig):
    example_data_path = (
        pytestconfig.rootpath / "docs/development/example-data/1aeo_relays_data.json"
    )
    with open(example_data_path, encoding="utf-8") as f:
        return json.load(f)


def test_relay_processing(tmp_path, mock_data):
    relay_set = Relays(
        output_dir=str(tmp_path),
        onionoo_url="https://onionoo.torproject.org/details",
        relay_data=mock_data,
    )
    assert len(relay_set.json["relays"]) > 0
```

## Data Structure

The JSON file contains a complete Onionoo details API response with:
- **relays**: Array of relay objects
- **bridges**: Array of bridge objects (if any)
- **version**: Onionoo API version
- **relays_published**: Timestamp of data collection

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

## Notes

- This data is **anonymized** and safe for public repositories
- Data is a static snapshot — use for structure and offline tests only, not live network state
- For **live testing**, use the actual Onionoo API
- Update this file periodically to reflect current API format

## How to Verify

```bash
python3 -c "import json; d = json.load(open('docs/development/example-data/1aeo_relays_data.json')); print(len(d['relays']), d.get('relays_published'))"
```
