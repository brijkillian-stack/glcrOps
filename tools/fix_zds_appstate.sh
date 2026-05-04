#!/usr/bin/env bash
# tools/fix_zds_appstate.sh — Rename ZDS's AppState class to ZdsState to avoid
# colliding with shared/base.py's AppState (GLCR's). Reflex registers state
# classes globally by class name; two classes named AppState breaks startup.
#
# Idempotent. Safe to re-run.

set -euo pipefail

ROOT="$HOME/dev/brijkillian-stack"
ZDS="$ROOT/apps/zds"
SED_BAK=".bak.$$"

cd "$ROOT"

echo "──────────────────────────────────────────────────────────"
echo "  Rename apps/zds/AppState → ZdsState"
echo "──────────────────────────────────────────────────────────"

# Find every .py under apps/zds/ (and the brijkillian_stack/ entry, in case it
# accidentally references zds AppState — it doesn't today, but defensive).
files=$(find "$ZDS" "$ROOT/brijkillian_stack" -name "*.py" \
        -not -path "*/__pycache__/*" -not -path "*/.web/*" 2>/dev/null)

n=0
for f in $files; do
  # Only touch files that actually reference AppState
  if ! grep -q "AppState" "$f" 2>/dev/null; then continue; fi

  # Whole-word replace: AppState → ZdsState. \b boundaries prevent matching
  # inside other identifiers (none in our codebase, but be safe).
  sed -i "$SED_BAK" \
    -e 's|\([^A-Za-z0-9_]\)AppState\([^A-Za-z0-9_]\)|\1ZdsState\2|g' \
    -e 's|^AppState\([^A-Za-z0-9_]\)|ZdsState\1|g' \
    -e 's|\([^A-Za-z0-9_]\)AppState$|\1ZdsState|g' \
    "$f"
  n=$((n+1))
done

# Cleanup .bak files
find "$ZDS" "$ROOT/brijkillian_stack" -name "*$SED_BAK" -delete 2>/dev/null

echo "    ✓ updated $n files"

# Stub the obsolete apps/zds/glcr_zone_app.py (was the old standalone Reflex
# entry; now replaced by brijkillian_stack/brijkillian_stack.py).
OLD_ENTRY="$ZDS/glcr_zone_app.py"
if [ -f "$OLD_ENTRY" ] && ! head -2 "$OLD_ENTRY" 2>/dev/null | grep -q "^# Replaced"; then
  cat > "$OLD_ENTRY" <<'EOF'
# Replaced by brijkillian_stack/brijkillian_stack.py at the project root.
# This file is kept temporarily for git history; safe to delete.
EOF
  echo "    ✓ stubbed apps/zds/glcr_zone_app.py"
fi

echo
echo "──────────────────────────────────────────────────────────"
echo "  Verification — should ALL return zero hits"
echo "──────────────────────────────────────────────────────────"

problems=0
hits=$(grep -rn "AppState" "$ZDS" --include="*.py" 2>/dev/null \
       | grep -v ":# Moved\|:# Replaced" || true)
if [ -n "$hits" ]; then
  echo "  ✗ AppState references still in apps/zds/:"
  echo "$hits" | sed 's/^/      /'
  problems=$((problems+1))
else
  echo "  ✓ no AppState refs in apps/zds/"
fi

# Sanity: ZdsState class is defined exactly once in apps/zds/state.py
def_count=$(grep -c "^class ZdsState" "$ZDS/state.py" 2>/dev/null || echo 0)
if [ "$def_count" = "1" ]; then
  echo "  ✓ class ZdsState defined in apps/zds/state.py"
else
  echo "  ✗ class ZdsState defined $def_count times in apps/zds/state.py (expected 1)"
  problems=$((problems+1))
fi

echo
if [ "$problems" -eq 0 ]; then
  echo "  ✅ AppState collision resolved"
else
  echo "  ⚠ $problems issues remain"
fi
