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

### EXP-001 terminology + comparability clarification (added after review direction, no rerun)
- "Specified before the run" is the accurate description of docs/experiment.md: a local specification written before execution, preserved in git history. It is NOT an independent pre-registration with a timestamped external record.
- Cost model basis: an assumption modeled on one discount broker's published charges of 2026-11-14. "Realistic" is not claimed without further basis; the model's rates are itemized and auditable in papertrading/costs.py.
- Comparability gaps in the first run's benchmark line: strategy series uses Yahoo split/dividend-adjusted prices while the benchmark (^NSEI) is a PRICE-return index with no dividends and no costs - the treatments differ in both directions. Benchmark figure is +27.8% price return only.
- Result is local, preliminary and unverified as investment evidence.

### EXP-001 integrity and reproducibility review (2026-11-14, no rerun of the experiment)
- scripts/verify_exp001.py re-ran the experiment from the cached bars and reproduced every recorded number exactly (final equity Rs 1,11,150.78; max drawdown Rs 14,627.16; 96 fills; 86 skips; benchmark +27.8%; open positions ADANIPORTS 14, TECHM 14, BSE 7, DRREDDY 21). 449 checks, 0 failures.
- Execution timing verified for every fill: each executes one trading session after its decision, at that day's open +/- 10bps slippage.
- Terminal decomposition: cash Rs 3,264.68 + open positions at 2026-11-13 closes (ADANIPORTS Rs 26,646.20; BSE Rs 27,563.90; DRREDDY Rs 28,980.00; TECHM Rs 24,696.00) recomposes Rs 1,11,150.78 exactly.
- Independent fill replay (no engine code) matches engine equity to the paisa; every fill's charges match the cost model; cash never negative (minimum Rs 85.07); drawdown recomputed from the equity series matches.
- Data sanity: all 50 symbols have 740 bars each, sorted, no duplicate dates.
- Gap found and fixed: the first run did NOT write its decisions to decisions/log.csv (the runner never appended). The 182 decisions were regenerated deterministically (same code path, same cached bars; reproduction of every recorded number proves equivalence) and backfilled on 2026-11-14. run_experiment.py now logs every decision at generation time with run-date-suffixed ids.
- Benchmark comparability stands as stated in the clarification above: ^NSEI is price-return (no dividends, no costs); NSE's published Nifty 50 dividend yield on 13-11-2026 was 1.4% (nsearchives ind_close_all file), so a total-return benchmark would be HIGHER than +27.8% - the stated underperformance is, if anything, understated. Exact TRI history was not obtained from a free official source on 2026-11-14.
- Result remains: local, preliminary, single-run, not investment evidence.

### Correction + provenance hardening (2026-11-14, supersedes the directional TRI wording above)
- Earlier wording that a total-return benchmark "would be HIGHER" and that underperformance is "understated if anything" is retracted: the unmatched treatments (adjusted-price strategy series with modeled costs vs price-return index without either) are stated, and their net effect on the comparison is NOT quantified. A single-date dividend yield cannot quantify historical TRI. The +11.15% vs +27.8% comparison is an unmatched-treatments comparison, not a measured alpha gap.
- Fill timing one session after each decision does not by itself prove the absence of lookahead; remaining bias concerns explicitly open: current-constituent universe selection (survivorship) and position sizing on adjusted prices.
- decisions/log.csv rows with unsuffixed exp001-NNNN ids are a deterministic BACKFILL (see decisions/README.md), not contemporaneous records.
- Run artifacts hashed for reproducibility in experiments/exp001-manifest.sha256 (data CSVs) and exp001-manifest.meta (code commit + recorded outputs).

## AUTONOMY-POLICY-v1 2026-11-17 - prospective virtual risk controls (no run yet)
- policy_path: config/autonomy.json
- scope: virtual delivery paper trading only; no broker connection, account, payment or real orders.
- controls: no-trade days allowed; max 2 new buys/day; max 20% of virtual equity in new daily exposure; max 10% per position; max 4 open positions; max 1% virtual equity risked per position; ATR-bounded stops; overall halt at Rs 40,000 virtual loss.
- mode_status: delivery enabled; intraday, futures and options paused pending data, execution, leverage/margin and derivative-cost models.
- status: specified before any autonomous forward run. No autonomous decisions, trades or results exist yet. The unrecovered 2026-11-16 forward checkpoint remains a gap and is not repaired by this policy.
