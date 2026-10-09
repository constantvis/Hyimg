#!/bin/bash
# A git pre-commit hook in each of Hyimg's four repositories that runs the fast check on what is being committed (scripts/check.sh
# --staged: the design and code validator on the staged .html/.js/.css, the repository's unit tests). A commit with a NEW violation
# stops; `git commit --no-verify` goes past it once. A hook of someone else's already there is kept: it runs first, then this check.
#
#   scripts/install_hooks.sh            install into the four repositories beside this one
#   scripts/install_hooks.sh --remove   take the hooks out again
set -eu
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOS_DIR="$(dirname "$(dirname "$HERE")")"
MARK="# hyimg-check-hook"
for r in hyimg hyimg-image-studio hyimg-3d-studio hyimg-dev-studio; do
  d="$REPOS_DIR/$r"; [ -d "$d/.git" ] || { echo "skip $r: no git repository at $d"; continue; }
  hooks="$(git -C "$d" rev-parse --git-path hooks)"; case "$hooks" in /*) ;; *) hooks="$d/$hooks" ;; esac
  mkdir -p "$hooks"; h="$hooks/pre-commit"
  if [ "${1:-}" = "--remove" ]; then
    if [ -f "$h" ] && grep -q "$MARK" "$h"; then
      if [ -f "$h.before-hyimg" ]; then mv "$h.before-hyimg" "$h"; else rm "$h"; fi; echo "removed from $r"
    fi
    continue
  fi
  if [ -f "$h" ] && ! grep -q "$MARK" "$h"; then mv "$h" "$h.before-hyimg"; fi
  cat > "$h" <<HOOK
#!/bin/bash
$MARK (installed by $HERE/install_hooks.sh)
set -e
[ -x "\$(dirname "\$0")/pre-commit.before-hyimg" ] && "\$(dirname "\$0")/pre-commit.before-hyimg"
exec "$HERE/check.sh" --staged
HOOK
  chmod +x "$h"; echo "installed in $r: $h"
done
