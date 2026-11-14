# decisions/log.csv - provenance

Rows with decision_id of the form `exp001-NNNN` (no date suffix) are a
BACKFILL, not contemporaneous records: the first EXP-001 run (2026-11-14)
did not log its decisions at the time; they were deterministically
regenerated from the same code path and the same cached bars later that day
(the regeneration reproduces every recorded run number exactly - see
experiments/log.md and scripts/verify_exp001.py) and then written here.

Rows with run-date-suffixed ids (e.g. `exp001-2026-11-15-0001`) are logged
at generation time by scripts/run_experiment.py and are contemporaneous.
