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
- A loss limit in a simulator is exact; in real markets prices can gap past
  any limit.
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
papertrading/   config, costs, ledger (append-only log), data loaders, engine, report
scripts/        fetch_bhavcopy.py - cache one day's official archive file
decisions/      log.csv - the pre-registered decision record
tests/          stdlib unittest suite, offline, synthetic data
```

## Quickstart

```bash
python3 -m unittest discover -s tests      # run the test suite (offline)
python3 scripts/fetch_bhavcopy.py 2026-11-13   # cache one day's bhavcopy
```

No dependencies are needed for the core or the tests.
`pip install yfinance` only if you want the optional Yahoo loader.

## Status

v0.1.0 - tracker core built and unit-tested on synthetic data. No trading
rules are implemented yet; the strategy rules that will generate decisions
are the next milestone and will be documented here before use.
