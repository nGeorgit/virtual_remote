#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VM_DIR="${MOBILE_REMOTE_VM_DIR:-$ROOT_DIR/.vm/win7}"
DISK_PATH="$VM_DIR/win7.qcow2"
DISK_SIZE="${WIN7_VM_DISK_SIZE:-64G}"
SHARE_DIR="$VM_DIR/share"

print_usage() {
  cat <<'EOF'
Usage: scripts/create_win7_vm.sh [--disk /path/to/win7.qcow2] [--size 64G]

Creates the qcow2 disk and shared-folder structure for the Windows 7 VM.

Environment:
  MOBILE_REMOTE_VM_DIR  Base directory for VM assets. Default: ./.vm/win7
  WIN7_VM_DISK_SIZE     Disk size when --size is omitted. Default: 64G
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --disk)
      DISK_PATH="$2"
      shift 2
      ;;
    --size)
      DISK_SIZE="$2"
      shift 2
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      print_usage >&2
      exit 1
      ;;
  esac
done

if ! command -v qemu-img >/dev/null 2>&1; then
  echo "qemu-img is not installed. Install qemu-utils first." >&2
  exit 1
fi

mkdir -p "$(dirname "$DISK_PATH")" "$SHARE_DIR"

if [[ -e "$DISK_PATH" ]]; then
  echo "Disk already exists: $DISK_PATH"
else
  qemu-img create -f qcow2 "$DISK_PATH" "$DISK_SIZE"
  echo "Created VM disk: $DISK_PATH"
fi

cat <<EOF
Shared folder:
  $SHARE_DIR

Next step:
  scripts/run_win7_vm.sh --iso /path/to/windows7.iso
EOF
