#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VM_DIR="${MOBILE_REMOTE_VM_DIR:-$ROOT_DIR/.vm/win7}"
DISK_PATH="$VM_DIR/win7.qcow2"
SHARE_DIR="$VM_DIR/share"
ISO_PATH=""
RAM_MB="${WIN7_VM_RAM_MB:-4096}"
CPU_COUNT="${WIN7_VM_CPUS:-2}"
RDP_PORT="${WIN7_VM_RDP_PORT:-33897}"
QEMU_BIN="${QEMU_BIN:-qemu-system-x86_64}"

print_usage() {
  cat <<'EOF'
Usage: scripts/run_win7_vm.sh [options]

Options:
  --iso /path/to/windows7.iso   Attach a Windows 7 ISO for install or repair.
  --disk /path/to/win7.qcow2    Override the VM disk path.
  --share /path/to/share        Override the host<->guest shared folder.
  --ram 4096                    Guest RAM in MiB. Default: 4096.
  --cpus 2                      Guest vCPU count. Default: 2.
  --rdp-port 33897              Host port forwarded to guest 3389. Default: 33897.
  -h, --help                    Show this help text.

Environment:
  MOBILE_REMOTE_VM_DIR  Base directory for VM assets. Default: ./.vm/win7
  WIN7_VM_RAM_MB        Default RAM when --ram is omitted.
  WIN7_VM_CPUS          Default CPU count when --cpus is omitted.
  WIN7_VM_RDP_PORT      Default RDP forward port when --rdp-port is omitted.
  QEMU_BIN              Override the qemu-system binary name/path.

Notes:
  - Create the disk first with scripts/create_win7_vm.sh
  - Put files you want available inside the guest in the shared folder.
  - The shared folder is mounted as a FAT disk image, not a live network share.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --iso)
      ISO_PATH="$2"
      shift 2
      ;;
    --disk)
      DISK_PATH="$2"
      shift 2
      ;;
    --share)
      SHARE_DIR="$2"
      shift 2
      ;;
    --ram)
      RAM_MB="$2"
      shift 2
      ;;
    --cpus)
      CPU_COUNT="$2"
      shift 2
      ;;
    --rdp-port)
      RDP_PORT="$2"
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

if ! command -v "$QEMU_BIN" >/dev/null 2>&1; then
  echo "$QEMU_BIN is not installed. Install qemu-system-x86 first." >&2
  exit 1
fi

mkdir -p "$(dirname "$DISK_PATH")" "$SHARE_DIR"

if [[ ! -f "$DISK_PATH" ]]; then
  echo "Missing VM disk: $DISK_PATH" >&2
  echo "Create it first with scripts/create_win7_vm.sh" >&2
  exit 1
fi

if [[ -n "$ISO_PATH" && ! -f "$ISO_PATH" ]]; then
  echo "Windows 7 ISO not found: $ISO_PATH" >&2
  exit 1
fi

ACCEL="tcg"
CPU_MODEL="qemu64"
if [[ -e /dev/kvm ]] && id -nG "$USER" | grep -qw kvm; then
  ACCEL="kvm"
  CPU_MODEL="host"
fi

QEMU_ARGS=(
  -name "mobile-remote-win7"
  -machine "pc,accel=$ACCEL"
  -cpu "$CPU_MODEL"
  -smp "$CPU_COUNT"
  -m "$RAM_MB"
  -boot "menu=on"
  -rtc "base=localtime"
  -usb
  -device usb-tablet
  -vga std
  -drive "file=$DISK_PATH,if=ide,media=disk,format=qcow2"
  -drive "file=fat:rw:$SHARE_DIR,if=ide,media=disk,format=raw"
  -netdev "user,id=net0,hostfwd=tcp:127.0.0.1:$RDP_PORT-:3389"
  -device "e1000,netdev=net0"
)

if [[ -n "$ISO_PATH" ]]; then
  QEMU_ARGS+=(-drive "file=$ISO_PATH,media=cdrom,if=ide")
fi

cat <<EOF
Launching Windows 7 VM
  Accelerator: $ACCEL
  Disk:        $DISK_PATH
  Share:       $SHARE_DIR
  RDP port:    127.0.0.1:$RDP_PORT -> guest:3389
EOF

exec "$QEMU_BIN" "${QEMU_ARGS[@]}"
