# Live-session virtual execution boundary

Prepared on 17 November 2026. The live-session path is **prepared, not
activated**. It does not poll a quote API, append decisions, publish raw
quotes, connect to a broker or place real orders.

## Grounded market window

NSE's market-timings page lists the normal/odd-lot equity market as 09:15 to
15:30 IST. Source:
https://www.nse.in/static/market-data/market-timings

The 2026 NSE holiday calendar is in circular CMTR71775, with an added
2026-01-15 trading holiday in CMTR72260:

- https://nsearchives.nseindia.com/content/circulars/CMTR71775.pdf
- https://nsearchives.nseindia.com/content/circulars/CMTR72260.pdf

`config/live-session.json` carries these dates. The 2026-11-08 Muhurat
session is not modelled because the circular says its timing would be
notified later.

## Quote rule

A quote can support a current-session virtual fill only when all checks pass:

1. It names the NSE exchange. BSE is not enabled for live-session fills.
2. Its timestamp is inside the modelled 09:15-15:30 IST normal session on a
   trading day.
3. The evaluation time is also inside that session.
4. Its effective age, including the source's declared delay, is no more than
   120 seconds.
5. Its retrieval timestamp is not before the quote timestamp or in the
   future.
6. The quote source and timestamp are recorded with the virtual fill.

Yahoo's help page says `.NS` quotes are real-time, `.BO` quotes are delayed
15 minutes, and all Yahoo Finance information is provided as is for
informational purposes only and must not be redistributed. Source:
https://help.yahoo.com/kb/finance/SLN2310.html

NSE's data policy treats real-time, snapshot, delayed, end-of-day and
historical prices as Market Data and restricts usage, display and
redistribution. Source:
https://www.nse.in/static/market-data/nse-data-policy

Therefore this project does not publish raw live quote snapshots. A future
public dashboard may show that a decision or virtual fill happened, after
checking what derived information the data source permits.

## Current implementation

`papertrading.live` implements:

- NSE 09:15-15:30 IST session and 2026 holiday guards;
- fail-closed timestamp/freshness checks;
- NSE-only exchange gating, with BSE's 15-minute delay recorded but not
  enabled;
- virtual delivery fill planning with the existing slippage and itemized
  cost model;
- simulated cash/position updates for a dry run;
- an explicit refusal to activate itself while the policy status is
  `prepared_not_activated`.

`scripts/prepare_live_session.py` combines a `prepared_not_executed` forward
manifest with local quote snapshots and writes a `session_plan_not_executed`
manifest. It is an offline preparation command, not a scheduler or quote
poller.

## Remaining decision before activation

Do not activate polling or autonomous session fills until the feed/cadence
choice is settled. The current evidence is not enough to claim a dependable
continuous free feed:

- One Yahoo `query2` chart request worked for RELIANCE.NS and RELIANCE.BO.
- One Yahoo `query1` chart request returned HTTP 429.
- One NSE public quote/API route returned HTTP 403.
- Yahoo forbids redistribution and calls its data informational only.
- NSE market-data redistribution/use is licensed and restricted.

A safe activation proposal must name the exact feed, polling interval, local
runtime owner, failure behavior, and what may be shown publicly. No such
activation is approved yet.
