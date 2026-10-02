"""Fake external model: uniform probabilities and a long-short Decision column."""

import csv
import sys

prices, origin, out, *extra = sys.argv[1:]
gross = float(extra[extra.index("--gross") + 1]) if "--gross" in extra else 1.0
with open(prices) as f:
    symbols = next(csv.reader(f))[1:]
n = len(symbols)
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["ID", "Rank1", "Rank2", "Rank3", "Rank4", "Rank5", "Decision"])
    for i, s in enumerate(symbols):
        w.writerow([s, 0.2, 0.2, 0.2, 0.2, 0.2, gross * (1 if i % 2 else -1) / n])
