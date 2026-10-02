# Adapter: run the unmodified FinQBoost script (upstream/src) for one forecast origin.
#
#   Rscript run.R <prices.csv> <origin YYYY-MM-DD> <out.csv>
#
# <prices.csv>: wide adjusted closes, first column the date (YYYY-MM-DD), one column
# per symbol, only rows up to the origin (the Python harness writes it). The upstream
# script reads "../data/<single csv>" and writes "../outputs/template.csv" relative to
# its working directory, so it runs inside a temporary copy of that layout.
# MakeForecast.R logic (forecast origin, DRE frozen from 2022-09-01) is reproduced
# here because it only parses the command line before sourcing the main script.

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 3) stop("usage: Rscript run.R <prices.csv> <origin> <out.csv>")
prices_csv <- normalizePath(args[1])
start_date <- as.Date(args[2])
out_csv <- args[3]
upstream <- normalizePath(file.path(dirname(sub("--file=", "", grep("--file=", commandArgs(), value = TRUE))), "upstream", "src", "preprocess-and-forecast.R"))

work <- tempfile("finqboost_")
dir.create(file.path(work, "data"), recursive = TRUE)
dir.create(file.path(work, "outputs"))
dir.create(file.path(work, "src"))
file.copy(prices_csv, file.path(work, "data", "prices.csv"))

# As in upstream MakeForecast.R
end_date <- start_date + as.difftime(4 * 7, units = "days")
freeze_DRE <- start_date >= as.Date("2022-09-01")

old <- setwd(file.path(work, "src"))
on.exit(setwd(old), add = TRUE)
source(upstream)
setwd(old)
file.copy(file.path(work, "outputs", "template.csv"), out_csv, overwrite = TRUE)
unlink(work, recursive = TRUE)
