#!/usr/bin/env bash
# Clone sebrad/M6 at the pinned commit into vendor/sebrad/upstream (ignored by git:
# the upstream repository declares no license, so its code is not redistributed here).
set -euo pipefail
cd "$(dirname "$0")"
COMMIT=0c7d0dd41dbd6721a570e9f1dccb5ab0f77e0a86
if [ ! -d upstream ]; then
  git clone --quiet https://github.com/sebrad/M6.git upstream
fi
git -C upstream fetch --quiet origin
git -C upstream checkout --quiet "$COMMIT"
echo "sebrad/M6 at $(git -C upstream rev-parse HEAD)"
