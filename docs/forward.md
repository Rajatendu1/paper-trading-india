# Gap-labelled forward continuation

`papertrading.forward` prepares candidate autonomous paper decisions without
executing them and without changing the append-only decision log.

## Boundary

- The only verified portfolio state is the EXP-001 terminal state marked on
  2026-11-13.
- The 2026-11-16 forward checkpoint is missing and remains missing.
- Preparation may start from the verified 2026-11-13 state and later complete
  bars, but that is a gap-labelled continuation, not a repaired checkpoint or
  a contemporaneous mark.
- A prepared decision is not a trade. It must be appended to
  `decisions/log.csv` before the next execution window by a separate forward
  runner before it counts as the forward record.

## Current preparation rule

The first forward rule is `autonomous-sma-cross-20-60-v1`:

1. Use only raw daily bars through `data_through`.
2. Require `decision_date` to be after `data_through`.
3. Evaluate the existing SMA 20/60 crossover at the latest close.
4. Initialize stops for positions migrated from EXP-001 using policy v1.
5. Apply the policy caps: no-trade allowed, at most 2 buys/day, 20% new daily
   exposure, 10% per position, 4 open positions, 1% virtual equity risk per
   position, and cash after estimated delivery charges.
6. Emit a manifest labelled `prepared_not_executed`.

The manifest records the source state, missing-checkpoint label, reconstructed
planning equity, initialized stops, candidate decisions, no-trade notes and
the actions explicitly not done.

## Local command

```sh
python3 scripts/prepare_forward_run.py \
  --data-through 2026-11-16 \
  --decision-date 2026-11-17 \
  --output /tmp/forward-prep.json
```

This command may fetch uncached Yahoo daily bars for local preparation. It
does not place orders, append decisions, call a model, or publish results.
The missing 2026-11-16 checkpoint remains a visible gap.
