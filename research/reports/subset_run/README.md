# Subset run (run_type = SUBSET_104_JOBS)

Real MIT Supercloud data, random subset of 104 labelled jobs (4 per label, single-file jobs of 2-40 MB), chronological job split 73/16/15. LSTMs: 2 seeds, max 10 epochs (full design: 5 seeds, 20 epochs). Not the full 3,430-job experiment.

The files in research/reports/ (results.json, results_table.csv, audit_summary.json, split_report.json, e2_results.json) come from this run and carry the field `run_type`. When the full Colab run finishes, its files replace them.
