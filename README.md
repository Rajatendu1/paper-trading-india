# paper-trading-india

A paper-trading experiment for short-term Indian stocks. **Simulation only:
no real money, no broker connection, no real orders, ever.** Every trade in
this repo is virtual.

Nothing here is investment advice, and no result from this experiment is a
promise of profit or reliable income.

## Parameters

Set by the owner and public on purpose:

- **Virtual starting capital:** Rs 1,00,000
- **Loss limit:** Rs 40,000 (experiment halts if mark-to-market losses reach it)

## Assumptions (stated, not hidden)

- **"Short term" means days to weeks (swing), not same-day intraday.** This is
  a design assumption made at project start, not a settled preference; it
  exists because free end-of-day data cannot validate same-day entries/exits.
- **Execution rule:** a decision recorded after close on day D executes at the
  **open of the next trading day**, plus an assumed slippage (default 10 bps
  per side, configurable). No lookahead by construction.
- **Cost model:** a configurable assumption in `papertrading/costs.py`,
  modeled on one discount broker's published charges
  (https://zerodha.com/charges/, retrieved 2026-11-14). It is not necessarily
  the owner's broker. Brokerage, STT, transaction charge, SEBI charge, GST,
  stamp duty and DP charges are all itemized and auditable.
- **Prices are raw (unadjusted)** on the bhavcopy convention; yfinance is
  loaded with `auto_adjust=False` to match. Mixing adjusted and raw series
  creates fake gaps and is not done.
- **Short selling is not supported** (delivery segment).

## Honest limitations

- Paper fills are not live fills. Real orders face liquidity, partial fills
  and worse slippage; live results are often worse than paper results.
- Daily bars cannot say what happened inside a day, so intraday strategies
  are out of scope for this data.
- The Rs 40,000 loss limit is NOT a hard cap, even in simulation: the rule
  liquidates open positions at the NEXT trading day's open after a breach,
  and overnight gaps can take losses past the limit, in simulation and
  live.
- Past simulations, including any backtest run with this code, say nothing
  about future outcomes. The decision log is append-only and decisions are
  recorded before they execute, so future observations are never counted as
  historical success.

## How it works

1. Decisions are written to `decisions/log.csv` (append-only) with the rule
   that prompted them, before execution.
2. `PaperEngine` executes due decisions at the next trading day's open with
   slippage and itemized costs, then marks the portfolio to market at each
   close.
3. Equity, drawdown and the loss-limit status are recorded per day;
   `report.summarize` produces the summary.

## Data

- **Primary:** NSE's official bhavcopy archives (free, end-of-day, 15+ years).
  The cash-market format changed on 2024-07-08; both eras parse. Downloaded
  locally for computation only and **never redistributed** - `data/` is
  gitignored. Fetch one day at a time; NSE rate-limits heavy clients.
- **Optional:** yfinance (unofficial Yahoo Finance wrapper; `.NS` tickers,
  `^NSEI` for NIFTY 50). Not required for the core tracker.

## Layout

```
papertrading/   config, costs, ledger (append-only log), data loaders, engine, strategy, report, autonomy controls, forward preparation
config/         autonomy.json - prospective virtual risk policy
docs/           experiment.md - EXP-001 rules, specified before the first run; autonomy.md - autonomous paper-lab policy; forward.md - gap-labelled continuation boundary
experiments/    log.md - append-only register of every run and its result, good or bad
scripts/        fetch_bhavcopy.py, run_experiment.py, build_app_data.py, prepare_forward_run.py
app/            static dashboard generated from committed EXP-001 records and hosted with GitHub Pages
decisions/      log.csv - append-only decision record (written before execution)
tests/          stdlib unittest suite, offline, synthetic data
```

## Quickstart

```bash
python3 -m unittest discover -s tests      # run the test suite (offline)
python3 scripts/build_app_data.py           # rebuild app/data/exp001.json
python3 -m http.server 8000 --directory app # local-only dashboard preview
python3 scripts/fetch_bhavcopy.py 2026-11-13   # cache one day's bhavcopy
```

No dependencies are needed for the core or the tests.
`pip install yfinance` only if you want the optional Yahoo loader.

## Status

v0.2.0-dev (LOCAL and preliminary; not investment evidence). Tracker core and
dashboard data checks are unit-tested (51 tests, offline). The static app is
hosted with GitHub Pages at
https://rajatendu1.github.io/paper-trading-india/app/ as a viewer over
committed EXP-001 records; it is not a production trading system. The
unrecovered 16 Nov 2026 forward checkpoint is shown as a gap, not replaced
with invented current positions. Autonomy policy v1 is prospective only: it
permits virtual delivery trades, caps daily activity/exposure/risk, pauses
intraday and derivatives until their data and mechanics are modelled, and has
no autonomous trades recorded yet. Forward preparation now emits a gap-labelled
manifest without appending decisions, executing trades or repairing the missing
checkpoint. EXP-001 (SMA 20/60 crossover,
NIFTY 50 universe, 2023-11-15 to 2026-11-13) has run once under rules specified
before the run in docs/experiment.md (a local specification, not an
independent registration). In that single local simulation the strategy
returned +11.15% net of assumed costs while the NIFTY 50 price index
returned +27.8% over the same period - the strategy underperformed simply
holding the index, with a Rs 14,627 max drawdown and the loss limit never
hit. 86 of 182 generated decisions were skipped for insufficient cash (see
experiments/log.md). Comparability caveats (adjustment, dividends, costs,
survivorship bias) are listed in docs/experiment.md and experiments/log.md.
One local simulation says nothing about the future; no result here is a
promise of profit or reliable income.
