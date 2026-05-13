#!/usr/bin/env bash
# gcm — safe git commit wrapper that clears stale lock files before every run.
# Usage: ./scripts/gcm.sh "your commit message"
#        ./scripts/gcm.sh "your commit message" --no-push   (skip push)
#
# Add a shell alias so you can call it from anywhere in the repo:
#   echo 'alias gcm="$(git rev-parse --show-toplevel)/scripts/gcm.sh"' >> ~/.zshrc
#   source ~/.zshrc

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: gcm \"commit message\" [--no-push]" >&2
  exit 1
fi

MSG="$1"
PUSH=true
if [[ "${2:-}" == "--no-push" ]]; then
  PUSH=false
fi

REPO="$(git rev-parse --show-toplevel)"

# Clear any stale lock files
for LOCK in "$REPO/.git/index.lock" "$REPO/.git/HEAD.lock" "$REPO/.git/MERGE_HEAD.lock"; do
  if [[ -f "$LOCK" ]]; then
    echo "Removing stale lock: $LOCK"
    rm -f "$LOCK"
  fi
done

git add -A
git commit -m "$MSG"

if $PUSH; then
  git push
fi
