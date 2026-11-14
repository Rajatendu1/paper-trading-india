# Experiment register (append-only)

Every run and every rule change is recorded here with its result, good or
bad. Entries are never edited or deleted; corrections are new entries.

(EXP-001 pending first run.)

## EXP-001 run 2026-11-14 - sma-cross-20-60, NIFTY 50 universe (2026-11-14 snapshot), 2023-11-14..2026-11-14
- period: 2023-11-15 -> 2026-11-13
- starting_capital_inr: 100000.0
- final_equity_inr: 111150.78
- total_return_pct: 11.15
- max_drawdown_inr: 14627.16
- loss_limit_inr: 40000.0
- loss_limit_hit: None
- cost_model: configurable assumption, see costs.py (not necessarily the user's broker)
- skipped_decisions: 86
- note: Paper simulation. Not a promise of profit or reliable income.
- trades_executed: 96
- symbols_failed_download: []
- open_positions_at_end: {'ADANIPORTS': 14, 'TECHM': 14, 'BSE': 7, 'DRREDDY': 21}
- benchmark_nifty50_return_pct: 27.8
- notes: adjusted Yahoo daily data; survivorship-biased universe; delivery cost assumption of 2026-11-14 applied to whole period; benchmark is price return. Historical simulation only - no future-performance claim.

### EXP-001 follow-up analysis (same run, same rules - observation, not a rule change)
- All 86 skipped decisions were buy orders rejected for insufficient cash. Cause: sizing at 25% of equity per position with max 4 positions sums to 100% of equity, leaving no room for transaction costs, so the 4th concurrent buy almost always failed. Effective concurrency was therefore ~3 positions. Recorded so the skip count is not misread as a data problem.
- Candidate EXP-002 change (NOT yet run, must be pre-registered first): size at a fraction that reserves costs, or cap at 3 positions.
