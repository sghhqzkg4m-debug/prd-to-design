#!/usr/bin/env bash
set -euo pipefail

REPO_RAW="https://raw.githubusercontent.com/sghhqzkg4m-debug/prd-to-design/main"
SKILLS=(prd-to-design competitive-analysis user-journey sangfor-cloud-console beautiful-feishu-whiteboard)
SOURCE_DIR=""
FORCE=0
TARGET="codex"

usage() {
  cat <<'EOF'
Usage: bash install.sh [--target codex|trae] [--source-dir REPO_DIR] [--force]

Installs all five bundled skills. The default target is Codex.
TRAE CN global skills are installed into ~/.trae-cn/skills.
With --source-dir, reads packages from a local checkout instead of downloading.
If installed skills differ, asks before backing them up and replacing them.
Without an interactive terminal, stops unless --force is given.
EOF
}

while (($#)); do
  case "$1" in
    --target) TARGET="${2:?missing target after --target}"; shift 2 ;;
    --source-dir) SOURCE_DIR="${2:?missing directory after --source-dir}"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$TARGET" in
  codex) DEST="${CODEX_HOME:-$HOME/.codex}/skills" ;;
  trae) DEST="$HOME/.trae-cn/skills" ;;
  *) echo "Unsupported target: $TARGET (choose codex or trae)" >&2; exit 2 ;;
esac

if ! command -v tar >/dev/null || ! command -v curl >/dev/null; then
  echo "tar and curl are required." >&2
  exit 1
fi
if command -v shasum >/dev/null; then
  hash_file() { shasum -a 256 "$1" | awk '{print $1}'; }
elif command -v sha256sum >/dev/null; then
  hash_file() { sha256sum "$1" | awk '{print $1}'; }
else
  echo "shasum or sha256sum is required." >&2
  exit 1
fi

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
PACKAGES="$WORK_DIR/packages"
mkdir -p "$PACKAGES" "$WORK_DIR/extracted"

if [[ -n "$SOURCE_DIR" ]]; then
  SOURCE_DIR="$(cd "$SOURCE_DIR" && pwd)"
  cp "$SOURCE_DIR/packages/SHA256SUMS" "$PACKAGES/SHA256SUMS"
  for skill in "${SKILLS[@]}"; do
    cp "$SOURCE_DIR/packages/$skill.tar.gz" "$PACKAGES/"
  done
else
  curl -fsSL "$REPO_RAW/packages/SHA256SUMS" -o "$PACKAGES/SHA256SUMS"
  for skill in "${SKILLS[@]}"; do
    curl -fsSL "$REPO_RAW/packages/$skill.tar.gz" -o "$PACKAGES/$skill.tar.gz"
  done
fi

for skill in "${SKILLS[@]}"; do
  expected="$(awk -v file="$skill.tar.gz" '$2 == file {print $1}' "$PACKAGES/SHA256SUMS")"
  [[ -n "$expected" ]] || { echo "Missing checksum for $skill" >&2; exit 1; }
  actual="$(hash_file "$PACKAGES/$skill.tar.gz")"
  [[ "$actual" == "$expected" ]] || { echo "Checksum mismatch: $skill" >&2; exit 1; }
  tar -xzf "$PACKAGES/$skill.tar.gz" -C "$WORK_DIR/extracted"
  [[ -f "$WORK_DIR/extracted/$skill/SKILL.md" ]] || { echo "Missing SKILL.md: $skill" >&2; exit 1; }
done

mkdir -p "$DEST"
CONFLICTS=()
for skill in "${SKILLS[@]}"; do
  if [[ -e "$DEST/$skill" ]] && ! diff -qr "$WORK_DIR/extracted/$skill" "$DEST/$skill" >/dev/null; then
    CONFLICTS+=("$skill")
  fi
done

# The renamed skill is a migration conflict, even when the new name is absent.
LEGACY="prd-to-feishu-design"
if [[ -e "$DEST/$LEGACY" ]]; then
  CONFLICTS+=("$LEGACY")
fi

if ((${#CONFLICTS[@]} > 0)) && ((FORCE == 0)); then
  echo "These installed skills will be replaced or migrated:" >&2
  for skill in "${CONFLICTS[@]}"; do
    echo "  $DEST/$skill" >&2
  done
  if [[ ! -t 2 ]]; then
    echo "No interactive terminal is available; no skills were changed. Re-run with --force only after approving replacement." >&2
    exit 1
  fi
  printf 'Back up and replace all listed skills? [y/N] ' > /dev/tty
  answer=""
  read -r answer < /dev/tty || true
  case "$answer" in
    y|Y|yes|YES|Yes) ;;
    *) echo "Cancelled; no skills were changed." >&2; exit 1 ;;
  esac
fi

BACKUP=""
if [[ -e "$DEST/$LEGACY" ]]; then
  mkdir -p "$DEST/.backup"
  BACKUP="$(mktemp -d "$DEST/.backup/prd-analysis-XXXXXXXX")"
  mv "$DEST/$LEGACY" "$BACKUP/$LEGACY"
  echo "Migrated legacy name: $LEGACY -> prd-to-design"
fi
for skill in "${SKILLS[@]}"; do
  if [[ -e "$DEST/$skill" ]]; then
    if diff -qr "$WORK_DIR/extracted/$skill" "$DEST/$skill" >/dev/null; then
      echo "Already installed: $skill"
      continue
    fi
    if [[ -z "$BACKUP" ]]; then
      BACKUP="$DEST/.backup/prd-analysis-$(date +%Y%m%d-%H%M%S)"
      mkdir -p "$BACKUP"
    fi
    mv "$DEST/$skill" "$BACKUP/$skill"
  fi
  mv "$WORK_DIR/extracted/$skill" "$DEST/$skill"
  echo "Installed: $skill"
done
[[ -z "$BACKUP" ]] || echo "Previous versions: $BACKUP"
if [[ "$TARGET" == "trae" ]]; then
  echo 'Done. Restart TRAE, then ask it to use prd-to-design.'
else
  echo 'Done. Start a new Codex session and invoke $prd-to-design.'
fi
