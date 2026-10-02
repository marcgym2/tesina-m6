# Minimal stand-in for a participant's model (tests only): quintile 5 for assets whose
# price rose over the history it receives, quintile 1 otherwise. It also reports the
# last date it saw so tests can check the harness never passes future prices.
args <- commandArgs(trailingOnly = TRUE)
prices <- read.csv(args[1], check.names = FALSE)
syms <- setdiff(names(prices), "index")
up <- sapply(syms, function(s) prices[[s]][nrow(prices)] > prices[[s]][1])
out <- data.frame(
  ID = syms,
  Rank1 = ifelse(up, 0, 1), Rank2 = 0, Rank3 = 0, Rank4 = 0, Rank5 = ifelse(up, 1, 0),
  last_date = prices$index[nrow(prices)], origin = args[2]
)
drop <- Sys.getenv("FAKE_DROP")  # tests: omit one asset from the output
if (nzchar(drop)) out <- out[out$ID != drop, ]
write.csv(out, args[3], row.names = FALSE)
