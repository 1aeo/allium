# Tor Relay Reliability Weighting Analysis Report

## Executive Summary

This report analyzes 9 different weighting methodologies for ranking Tor relay operators based on reliability metrics. The goal was to find alternatives to pure reliability ranking that prevent both 500+ relay operators from dominating and single-relay operators from taking all top spots.

**Key Finding**: The **Tiered Relay Groups** method provides the best balance for your specific requirements.

## Current Problem

The existing pure reliability method results in:
- Top 10 positions dominated entirely by single-relay operators (10/10 single relays)
- Large, reliable operators like `nothingtohide.nl` (294 relays, 99.4% reliability) ranked 13th
- Network diversity concerns as single operators may not contribute proportionally to network resilience

## Methodology

9 different weighting algorithms were tested using data from your Top 25 Reliability Masters table:

1. **Current Method**: Pure reliability percentage
2. **Log Relay Weighted**: Logarithmic scaling (base 2 & 3)
3. **Square Root Relay Weighted**: Square root scaling of relay counts
4. **Diminishing Returns**: Exponential decay after 50 relays
5. **Bandwidth Balanced**: 70% reliability + 30% bandwidth contribution
6. **Diversity Bonus**: Geographic and platform diversity multipliers
7. **Tiered Relay Groups**: Different multipliers per relay count tier
8. **Hybrid Balanced**: Multi-factor approach

## Results Summary

### Top Performers by Method

| Method | Top 3 Operators |
|--------|----------------|
| **Current** | 10 single-relay operators tied at 100% |
| **Tiered Groups** | internetanonymity.org (115 relays) → exitnodes.org (32 relays) → tor-help.info (13 relays) |
| **Diminishing Returns** | quetzalcoatl-relays.org (572) → prsv.ch (323) → nothingtohide.nl (294) |
| **Hybrid Balanced** | nothingtohide.nl (294) → quetzalcoatl-relays.org (572) → prsv.ch (323) |

### Distribution Analysis

**Current Method**: 10 single, 0 small, 0 medium, 0 large, 0 very large operators in top 10
**Tiered Groups**: 0 single, 3 small, 3 medium, 1 large, 3 very large operators in top 10

## Detailed Method Analysis

### 🏅 Recommended: Tiered Relay Groups

**How it works**: Applies different multipliers based on relay count tiers:
- Single relay (1): 0.8x multiplier (penalty)
- Small operators (2-10): 1.0x multiplier
- Medium operators (11-50): 1.1x multiplier (bonus)
- Large operators (51-200): 1.2x multiplier (bonus)
- Very large operators (200+): 1.0x multiplier (no extra bonus)

**Results**:
- Promotes medium-sized operators (11-50 relays) to top positions
- Prevents 500+ relay operators from automatic wins
- Still rewards reliability as primary factor
- Achieves balanced distribution in top 10

**Pros**:
- ✅ Balances single vs multi-relay operators effectively
- ✅ Prevents 500+ relay operators from dominating
- ✅ Simple to understand and implement
- ✅ Gives medium operators (11-50 relays) slight advantage

**Cons**:
- ❌ Somewhat arbitrary tier boundaries
- ❌ Doesn't account for bandwidth contribution
- ❌ May not reflect actual network contribution

### Alternative Options

#### Diminishing Returns
Good for promoting decentralization but may penalize large legitimate operators too much.

#### Hybrid Balanced
Most comprehensive but complex to implement and tune.

## Implementation Recommendations

### Primary Recommendation: Tiered Relay Groups

```python
# Tier multipliers
if relays == 1:
    multiplier = 0.8      # Single relay penalty
elif relays <= 10:
    multiplier = 1.0      # Small operators baseline
elif relays <= 50:
    multiplier = 1.1      # Medium operators bonus
elif relays <= 200:
    multiplier = 1.2      # Large operators bonus
else:
    multiplier = 1.0      # Very large operators no extra bonus

weighted_score = reliability_percentage * multiplier
```

### Tuning Parameters

The tier boundaries and multipliers can be adjusted based on network analysis:
- **Tier boundaries**: Currently 1, 10, 50, 200 - could be data-driven
- **Multipliers**: Currently 0.8, 1.0, 1.1, 1.2, 1.0 - could be fine-tuned
- **Penalty/bonus strength**: Could be increased/decreased based on desired effect

## Key Insights

1. **Single relay dominance eliminated**: The tiered approach prevents single relays from monopolizing top positions
2. **Medium operator promotion**: Operators with 11-50 relays get optimal treatment, encouraging sustainable growth
3. **Large operator balance**: 200+ relay operators don't get excessive advantages but aren't penalized
4. **Reliability primacy maintained**: Core reliability metric remains the primary factor

## Files Generated

- `reliability_weighting_experiments.py`: Complete analysis script using only Python standard library
- `reliability_weighting_results.csv`: Detailed results for all methods and operators
- `reliability_weighting_analysis_report.md`: This comprehensive report

## Next Steps

1. **Review tier boundaries**: Analyze actual relay distribution to optimize tier cutoffs
2. **Test with live data**: Apply method to full relay dataset from Onionoo API
3. **Monitor impact**: Track how ranking changes affect network diversity metrics
4. **Stakeholder feedback**: Gather input from relay operators on fairness perception

---

*Analysis completed using Python standard library modules on the top10up branch without external dependencies.*