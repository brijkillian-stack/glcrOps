#!/usr/bin/env bash
# tools/migrate.sh — Finish the monorepo restructure.
#
# Idempotent. Run from the project root (or anywhere — uses absolute paths).
# Performs:
#   1. Flatten  apps/zds/glcr_zone_app/  →  apps/zds/
#   2. Move shared code  apps/glcr/{db,ai,state/auth,state/base,state/grok,components/{sidebar,grok_panel,capture,palette,ui}}.py  →  shared/
#   3. Rewrite imports across apps/glcr/* and apps/zds/*
#   4. Move assets (styles.css, manifest.json, sw.js, icons) from OneDrive → shared/styles/
#   5. Stub apps/glcr/glcr_dashboard.py (replaced by brijkillian_stack/brijkillian_stack.py)
#   6. Clean caches
#
# Verification at the end: greps for residual broken imports, prints any hits.

set -euo pipefail

ROOT="$HOME/dev/brijkillian-stack"
ONEDRIVE="$HOME/Library/CloudStorage/OneDrive-gunlakecasino.com/GLCR/glcr_memory/dashboard/reflex"

cd "$ROOT"
echo "════════════════════════════════════════════════════════════"
echo "  Monorepo restructure migration"
echo "  ROOT: $ROOT"
echo "════════════════════════════════════════════════════════════"

# ─── 1. Flatten apps/zds/glcr_zone_app/ ────────────────────────────────
ZDS_INNER="$ROOT/apps/zds/glcr_zone_app"
ZDS_OUTER="$ROOT/apps/zds"

if [ -d "$ZDS_INNER" ]; then
  echo
  echo "[1/6] Flattening apps/zds/glcr_zone_app/ → apps/zds/"

  # Top-level python files
  for f in glcr_zone_app.py state.py database.py types.py styles.py \
           schedule_parser.py engine_bridge.py print_renderer.py __init__.py; do
    if [ -f "$ZDS_INNER/$f" ]; then
      # Don't overwrite stubs that previous agent created — only copy if dest is missing/stub
      if [ ! -f "$ZDS_OUTER/$f" ] || head -2 "$ZDS_OUTER/$f" 2>/dev/null | grep -q "^# Moved\|^# Replaced"; then
        cp "$ZDS_INNER/$f" "$ZDS_OUTER/$f"
        echo "    ✓ $f"
      else
        # Real file already exists at outer level — agent already moved it. Skip.
        echo "    · $f (already at apps/zds/, keeping outer)"
      fi
    fi
  done

  # Subdirs: pages, components
  for sub in pages components; do
    if [ -d "$ZDS_INNER/$sub" ]; then
      mkdir -p "$ZDS_OUTER/$sub"
      cp -R "$ZDS_INNER/$sub/." "$ZDS_OUTER/$sub/"
      echo "    ✓ $sub/ (recursive)"
    fi
  done

  # Now nuke the inner dir
  rm -rf "$ZDS_INNER"
  echo "    ✓ removed apps/zds/glcr_zone_app/"
else
  echo "[1/6] apps/zds/glcr_zone_app/ already flattened"
fi

# Drop apps/zds/rxconfig.py (replaced by root rxconfig.py)
if [ -f "$ZDS_OUTER/rxconfig.py" ]; then
  rm "$ZDS_OUTER/rxconfig.py"
  echo "    ✓ removed apps/zds/rxconfig.py (replaced by root rxconfig.py)"
fi

# ─── 2. Hoist shared code from apps/glcr/ ──────────────────────────────
echo
echo "[2/6] Moving shared code from apps/glcr/ → shared/"

mkdir -p "$ROOT/shared/components"

declare -a SHARED_MOVES=(
  "apps/glcr/db.py:shared/db.py"
  "apps/glcr/ai.py:shared/ai.py"
  "apps/glcr/state/auth.py:shared/auth.py"
  "apps/glcr/state/base.py:shared/base.py"
  "apps/glcr/state/grok.py:shared/grok_state.py"
  "apps/glcr/components/sidebar.py:shared/components/sidebar.py"
  "apps/glcr/components/grok_panel.py:shared/components/grok_panel.py"
  "apps/glcr/components/capture.py:shared/components/capture.py"
  "apps/glcr/components/palette.py:shared/components/palette.py"
  "apps/glcr/components/ui.py:shared/components/ui.py"
)

for entry in "${SHARED_MOVES[@]}"; do
  IFS=':' read -r src dst <<< "$entry"
  if [ -f "$ROOT/$src" ] && ! head -2 "$ROOT/$src" 2>/dev/null | grep -q "^# Moved"; then
    cp "$ROOT/$src" "$ROOT/$dst"
    cat > "$ROOT/$src" <<EOF
# Moved to $dst — this stub stays for git history; safe to delete.
EOF
    echo "    ✓ $src → $dst"
  else
    echo "    · $src → $dst (already moved or stubbed)"
  fi
done

# ─── 3. Rewrite imports across apps/glcr/ and apps/zds/ ────────────────
echo
echo "[3/6] Rewriting imports"

# Use sed -i with portable backup syntax (works on both BSD and GNU sed).
SED_BAK=".bak.$$"
SED_OPTS=(-i "$SED_BAK")

# Find all .py files under apps/ + brijkillian_stack/ (portable, works on macOS bash 3.2).
TARGETS=""
while IFS= read -r f; do
  TARGETS="$TARGETS|$f"
done < <(
  find "$ROOT/apps" "$ROOT/brijkillian_stack" -name "*.py" \
    -not -path "*/__pycache__/*" \
    -not -path "*/.web/*" \
    -not -path "*/.states/*" \
    2>/dev/null
)

target_count=0
# Apply substitutions. Order matters: longer patterns first so we don't
# rewrite a prefix and miss the rest.
echo "$TARGETS" | tr '|' '\n' | while IFS= read -r f; do
  [ -z "$f" ] && continue
  [ ! -f "$f" ] && continue
  # apps/glcr/ rewrites: relative → shared.*
  sed "${SED_OPTS[@]}" \
    -e 's|from \.\.state\.auth import|from shared.auth import|g' \
    -e 's|from \.state\.auth import|from shared.auth import|g' \
    -e 's|from \.\.state\.base import|from shared.base import|g' \
    -e 's|from \.state\.base import|from shared.base import|g' \
    -e 's|from \.\.state\.grok import|from shared.grok_state import|g' \
    -e 's|from \.state\.grok import|from shared.grok_state import|g' \
    -e 's|from \.\.components\.sidebar import|from shared.components.sidebar import|g' \
    -e 's|from \.components\.sidebar import|from shared.components.sidebar import|g' \
    -e 's|from \.\.components\.grok_panel import|from shared.components.grok_panel import|g' \
    -e 's|from \.components\.grok_panel import|from shared.components.grok_panel import|g' \
    -e 's|from \.\.components\.capture import|from shared.components.capture import|g' \
    -e 's|from \.components\.capture import|from shared.components.capture import|g' \
    -e 's|from \.\.components\.palette import|from shared.components.palette import|g' \
    -e 's|from \.components\.palette import|from shared.components.palette import|g' \
    -e 's|from \.\.components\.ui import|from shared.components.ui import|g' \
    -e 's|from \.components\.ui import|from shared.components.ui import|g' \
    -e 's|from \.\.db import|from shared.db import|g' \
    -e 's|from \.db import|from shared.db import|g' \
    -e 's|from \.\.ai import|from shared.ai import|g' \
    -e 's|from \.ai import|from shared.ai import|g' \
    "$f"

  # apps/zds/ rewrites: glcr_zone_app.X → apps.zds.X
  sed "${SED_OPTS[@]}" \
    -e 's|from glcr_zone_app\.components\.|from apps.zds.components.|g' \
    -e 's|from glcr_zone_app\.pages\.|from apps.zds.pages.|g' \
    -e 's|from glcr_zone_app\.state import|from apps.zds.state import|g' \
    -e 's|from glcr_zone_app\.database import|from apps.zds.database import|g' \
    -e 's|from glcr_zone_app\.types import|from apps.zds.types import|g' \
    -e 's|from glcr_zone_app\.styles import|from apps.zds.styles import|g' \
    -e 's|from glcr_zone_app\.schedule_parser import|from apps.zds.schedule_parser import|g' \
    -e 's|from glcr_zone_app\.engine_bridge import|from apps.zds.engine_bridge import|g' \
    -e 's|from glcr_zone_app\.print_renderer import|from apps.zds.print_renderer import|g' \
    -e 's|^import glcr_zone_app|import apps.zds|g' \
    "$f"
done

# Clean up the .bak files sed created
find "$ROOT/apps" "$ROOT/brijkillian_stack" -name "*$SED_BAK" -delete 2>/dev/null
n_targets=$(find "$ROOT/apps" "$ROOT/brijkillian_stack" -name "*.py" \
  -not -path "*/__pycache__/*" -not -path "*/.web/*" -not -path "*/.states/*" 2>/dev/null | wc -l | tr -d ' ')
echo "    ✓ rewrote imports across $n_targets files"

# ─── 4. Move assets to shared/styles/ ──────────────────────────────────
echo
echo "[4/6] Moving assets from OneDrive → shared/styles/"
mkdir -p "$ROOT/shared/styles/icons"

if [ -d "$ONEDRIVE/assets" ]; then
  for f in styles.css manifest.json sw.js; do
    if [ -f "$ONEDRIVE/assets/$f" ]; then
      cp "$ONEDRIVE/assets/$f" "$ROOT/shared/styles/$f"
      echo "    ✓ $f"
    fi
  done
  if [ -d "$ONEDRIVE/assets/icons" ]; then
    cp "$ONEDRIVE/assets/icons/"*.png "$ROOT/shared/styles/icons/" 2>/dev/null && \
      echo "    ✓ icons/ ($(ls "$ROOT/shared/styles/icons/" | wc -l | tr -d ' ') files)"
  fi
else
  echo "    ⚠ OneDrive assets not found at $ONEDRIVE/assets — manual copy needed"
fi

# ─── 5. Stub apps/glcr/glcr_dashboard.py ───────────────────────────────
echo
echo "[5/6] Stubbing apps/glcr/glcr_dashboard.py"
GLCR_OLD_ENTRY="$ROOT/apps/glcr/glcr_dashboard.py"
if [ -f "$GLCR_OLD_ENTRY" ] && ! head -2 "$GLCR_OLD_ENTRY" | grep -q "^# Replaced"; then
  cat > "$GLCR_OLD_ENTRY" <<'EOF'
# Replaced by brijkillian_stack/brijkillian_stack.py at the project root.
# This file is kept temporarily for git history; safe to delete.
EOF
  echo "    ✓ stubbed"
else
  echo "    · already stubbed"
fi

# ─── 6. Clean caches ───────────────────────────────────────────────────
echo
echo "[6/6] Cleaning caches"
find "$ROOT" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
find "$ROOT" -type d -name .web        -prune -exec rm -rf {} + 2>/dev/null || true
find "$ROOT" -type d -name .states     -prune -exec rm -rf {} + 2>/dev/null || true
echo "    ✓ removed __pycache__, .web, .states"

# ─── Verification ──────────────────────────────────────────────────────
echo
echo "════════════════════════════════════════════════════════════"
echo "  Verification — these greps should ALL return zero hits"
echo "════════════════════════════════════════════════════════════"

problems=0
check() {
  local label="$1" pattern="$2"
  local hits
  hits=$(grep -rnE "$pattern" "$ROOT/apps" "$ROOT/brijkillian_stack" \
         --include="*.py" 2>/dev/null \
         | grep -v ":# Moved\|:# Replaced" || true)
  if [ -n "$hits" ]; then
    echo "  ✗ $label:"
    echo "$hits" | sed 's/^/      /'
    problems=$((problems+1))
  else
    echo "  ✓ $label"
  fi
}

check "no .db relative imports"         "from \.\.?db import"
check "no .ai relative imports"         "from \.\.?ai import"
check "no .state.auth relative"         "from \.\.?state\.auth import"
check "no .state.base relative"         "from \.\.?state\.base import"
check "no .state.grok relative"         "from \.\.?state\.grok import"
check "no .components.sidebar relative" "from \.\.?components\.sidebar import"
check "no .components.grok_panel rel"   "from \.\.?components\.grok_panel import"
check "no .components.capture relative" "from \.\.?components\.capture import"
check "no .components.palette relative" "from \.\.?components\.palette import"
check "no .components.ui relative"      "from \.\.?components\.ui import"
check "no glcr_zone_app.X imports"      "from glcr_zone_app\."

echo
if [ "$problems" -eq 0 ]; then
  echo "════════════════════════════════════════════════════════════"
  echo "  ✅ MIGRATION SUCCESSFUL"
  echo "════════════════════════════════════════════════════════════"
  echo
  echo "  Next:"
  echo "    cd $ROOT"
  echo "    python3 -m venv .venv && source .venv/bin/activate"
  echo "    pip install -r requirements.txt"
  echo "    export API_URL=\"https://glcrops.onrender.com\""
  echo "    export DEPLOY_URL=\"https://glcrops.onrender.com\""
  echo "    export SUPABASE_URL=\"https://iazgrcainbokkdqunkok.supabase.co\""
  echo "    export SUPABASE_SERVICE_KEY=\"\$(grep SUPABASE_SERVICE_KEY \\"
  echo "        ~/glcr_memory/.env | cut -d= -f2-)\""
  echo "    reflex export --frontend-only --no-zip"
  echo
  echo "  If export succeeds: commit + push to a new GitHub repo, point Render at it."
else
  echo "════════════════════════════════════════════════════════════"
  echo "  ⚠ $problems CHECKS FAILED — review the hits above"
  echo "════════════════════════════════════════════════════════════"
fi
