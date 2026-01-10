# Pareto Frontier Analysis

## Summary

**Total Candidates Evaluated:** 17 (including baseline)

**Pareto Frontier Size:** 1 candidates

### Key Configurations

**Baseline:**
- Configuration: `R0-D0-B0-H0-SA-M4-AD0-APS-CO1`
- Coverage: 0.365
- Tokens: 273.0
- Cost: $0.0027 per case
- Score: 32.73

**Best (by score):**
- Configuration: `R1-D1-B1-H0-SB-M4-AD0-APS-CO0`
- Coverage: 0.417
- Tokens: 782.0
- Cost: $0.0078 per case
- Score: 29.85

**Cheapest Pareto-Optimal:**
- Configuration: `R1-D1-B1-H1-SB-M4-AD0-APS-CO0`
- Coverage: 0.417
- Tokens: 777.1
- Cost: $0.0078 per case
- Score: 24.90

## Trade-off Analysis

The Pareto frontier reveals the fundamental trade-off between coverage quality and computational cost. The baseline configuration achieves 36.5% coverage at just $0.0027 per case, making it the most cost-efficient option. However, upgrading to the best-scoring configuration improves coverage by 5.2% (to 41.7%), but increases token usage by 509 tokens (186% increase), raising the cost to $0.0078 per case—a 186% cost increase. For practitioners seeking a middle ground, the cheapest Pareto-optimal configuration (`R1-D1-B1-H1-SB-M4-AD0-APS-CO0`) offers 41.7% coverage at $0.0078 per case. The Pareto frontier contains 1 configurations, each representing a distinct efficiency point where no other configuration achieves both higher coverage and lower cost simultaneously. Organizations should select configurations based on their specific constraints: cost-sensitive deployments may prefer the baseline, while quality-critical applications may justify the premium for higher coverage.

## Pareto Frontier Members

| Rank | Configuration | Coverage | Tokens | Cost/Case | Score |
|------|---------------|----------|--------|-----------|-------|
| 1 | `R1-D1-B1-H1-SB-M4-AD0-APS-CO0` | 0.417 | 777.1 | $0.0078 | 24.90 |
