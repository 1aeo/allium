# Stable Flag Threshold Analysis

## Study Date: 2025-12-28

## Summary

Analysis of 10,000+ relays across 9 directory authorities reveals a significant discrepancy between the published `stable-mtbf` threshold in `flag-thresholds` and the actual minimum MTBF values for relays that receive the Stable flag.

## Findings

### Published Thresholds vs Actual Minimums

| Authority    | stable-mtbf threshold | Actual min MTBF (Stable relays) |
|--------------|----------------------|--------------------------------|
| dannenberg   | 37.3 days            | ~5.0 days                      |
| bastet       | 48.9 days            | ~5.0 days                      |
| tor26        | 54.5 days            | ~5.0 days                      |
| faravahar    | 42.5 days            | ~5.0 days                      |
| moria1       | 339.0 days           | ~5.0 days                      |

### Key Observations

1. **Consistent actual minimum**: All authorities assign Stable flag to relays with MTBF as low as ~5 days
2. **Threshold mismatch**: The `stable-mtbf` value in flag-thresholds is NOT the minimum threshold
3. **Below spec minimum**: 5 days is below the Tor spec's stated 7-day minimum

### Example Relays with Low MTBF but Stable Flag (from tor26)

| Relay         | MTBF   | WFU    | Time Known |
|---------------|--------|--------|------------|
| TorNode04     | 5.4d   | 0.9908 | 13.4d      |
| klaxhex       | 5.4d   | 0.9949 | 18.5d      |
| cozybeardev   | 5.1d   | 0.9663 | 12.5d      |
| lolaiur       | 5.3d   | 1.0000 | 5.3d       |
| prsv          | 5.2d   | 0.9960 | 17.1d      |

### Tor Spec Reference

According to [dir-spec](https://spec.torproject.org/dir-spec/assigning-flags-vote.html):
> "Stable" -- A router is 'Stable' if it is active, and either its Weighted MTBF is at least the median for known active routers or its Weighted MTBF corresponds to at least 7 days.

### Possible Explanations

1. **Weighted MTBF calculation differs**: The "weighted" calculation may produce different results than raw MTBF values shown in stats
2. **Grace period / hysteresis**: Flags may persist once assigned even if criteria temporarily not met
3. **Implementation variance**: Each authority may implement the spec slightly differently
4. **Spec interpretation**: The `stable-mtbf` in flag-thresholds may be the median value, not the minimum threshold

## Recommendations

1. **UI Display**: Show both published threshold AND actual flag presence from authority votes
2. **Warning Text**: Note that "Stable flag assignment may vary from published thresholds"
3. **Further Study**: Monitor this over time to see if thresholds change

## Reproduction Script

```bash
#!/bin/bash
# stable-flag-analysis.sh - Analyze Stable flag thresholds across authorities

AUTHORITIES=("0232AF90" "27102BC1" "2F3DF9CA" "70849B86" "F533C81C")

for auth in "${AUTHORITIES[@]}"; do
    VOTE_FILE=$(curl -s "https://collector.torproject.org/recent/relay-descriptors/votes/" | \
        grep -o "href=\"[0-9-]*vote-${auth}[^\"]*\"" | sed 's/href="//' | sed 's/"//' | head -1)
    
    if [ -n "$VOTE_FILE" ]; then
        AUTH_NAME=$(curl -s "https://collector.torproject.org/recent/relay-descriptors/votes/$VOTE_FILE" | \
            grep "^nickname" | awk '{print $2}')
        
        STABLE_MTBF=$(curl -s "https://collector.torproject.org/recent/relay-descriptors/votes/$VOTE_FILE" | \
            grep "flag-thresholds" | grep -o "stable-mtbf=[0-9]*" | cut -d= -f2)
        
        MIN_MTBF=$(curl -s "https://collector.torproject.org/recent/relay-descriptors/votes/$VOTE_FILE" | \
            awk '/^s / { has_stable = /Stable/ } 
                 /^stats / && has_stable { match($0, /mtbf=([0-9]+)/, arr); if (arr[1]) print arr[1] }' | \
            sort -n | head -1)
        
        echo "$AUTH_NAME: threshold=$(echo "scale=1; $STABLE_MTBF/86400" | bc)d, actual_min=$(echo "scale=2; $MIN_MTBF/86400" | bc)d"
    fi
done
```

## Data Sources
- CollecTor votes: https://collector.torproject.org/recent/relay-descriptors/votes/
- Tor Directory Specification: https://spec.torproject.org/dir-spec/

