#!/bin/bash
# Makes the Hyimg skills (skills/ in this repository) visible to the agent CLIs on this Mac by symlinking them, so they stay in
# the repository and every update reaches all agents at once: ~/.agents/skills (Gemini CLI and other agents that read the shared
# folder), ~/.gemini/config/skills (Antigravity agy), ~/.claude/skills (Claude Code), ~/.codex/skills (Codex). An existing folder of the same name that is not our link is
# left alone and reported. Run again after adding a skill; --remove takes our links away.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
TARGETS=("$HOME/.agents/skills" "$HOME/.gemini/config/skills" "$HOME/.claude/skills" "$HOME/.codex/skills")
for dir in "${TARGETS[@]}"; do
  mkdir -p "$dir"
  for skill in "$ROOT"/skills/*/; do
    name="$(basename "$skill")"; link="$dir/$name"; src="${skill%/}"
    if [ "${1:-}" = "--remove" ]; then
      [ -L "$link" ] && [ "$(readlink "$link")" = "$src" ] && rm "$link" && echo "убрал $link"
      continue
    fi
    if [ -L "$link" ]; then
      [ "$(readlink "$link")" = "$src" ] && { echo "есть  $link"; continue; }
      echo "занято другой ссылкой, не трогаю: $link -> $(readlink "$link")"; continue
    fi
    [ -e "$link" ] && { echo "занято папкой, не трогаю: $link"; continue; }
    ln -s "$src" "$link" && echo "новая $link"
  done
done
