#!/usr/bin/env bash
# Install the standalone blender-modeling skill for non-DSH hosts.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/sfw222/blend-asset-forge/main/skills/blender-modeling/install.sh | bash
# Installs into ~/.dsh/skills/blender-modeling.
set -euo pipefail

REPO_RAW="https://raw.githubusercontent.com/sfw222/blend-asset-forge/main"
ROOT="$HOME/.dsh/skills"
DEST="$ROOT/blender-modeling"

mkdir -p "$DEST/references"

fetch() {
  local src="$1"
  local dst="$2"
  curl -fsSL "$REPO_RAW/skills/blender-modeling/$src" -o "$dst"
}

fetch "SKILL.md" "$DEST/SKILL.md"
fetch "README.md" "$DEST/README.md"
fetch "NOTICE.md" "$DEST/NOTICE.md"
for f in LICENSE LICENSE.cc-blender-skill LICENSE.arjun988-blender-skills LICENSE.dream-loop; do
  fetch "$f" "$DEST/$f"
done
for f in modeling-overview.md multiview-calibration.md 参考图通用还原SOP.md 验收清单.md 曲面算法.md reference-review-and-unreal.md production-recipes.md; do
  fetch "references/$f" "$DEST/references/$f"
done

printf 'Installed blender-modeling skill to %s\n' "$DEST"
printf 'Restart your agent or reload skills, then invoke "blender-modeling".\n'
