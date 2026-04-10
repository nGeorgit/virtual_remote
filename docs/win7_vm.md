# Windows 7 VM Workflow

This is the practical workflow for testing the `win7-spike` branch from Linux.

## Host Setup

Install the minimum QEMU packages on the Linux host:

```bash
sudo apt-get update
sudo apt-get install -y qemu-system-x86 qemu-utils
```

If you want hardware acceleration, add your user to the `kvm` group and log out/in:

```bash
sudo usermod -aG kvm "$USER"
```

## Guest Assets

You must provide your own Windows 7 SP1 ISO and license.

Create the VM disk and shared folder:

```bash
scripts/create_win7_vm.sh
```

That creates:

- `.vm/win7/win7.qcow2`
- `.vm/win7/share/`

## First Boot / Install

Start the VM with the Windows 7 ISO attached:

```bash
scripts/run_win7_vm.sh --iso /absolute/path/to/windows7.iso
```

The VM uses:

- IDE disk for maximum guest compatibility
- `e1000` networking so Windows 7 does not need VirtIO drivers just to boot
- a FAT-backed shared disk at `.vm/win7/share`

## Moving Files Into the Guest

Anything copied into `.vm/win7/share/` appears to the guest as an extra disk.

Use that folder for:

- the built `mobile-typer.exe`
- installer scripts
- test notes or logs

## What This Actually Proves

From Linux, this VM lets you validate:

- whether a Windows build launches on Windows 7
- whether the Tk window opens correctly
- whether the HTTP UI loads in the guest browser
- whether Win32 key injection works against a real Windows 7 guest app

It does not magically solve cross-building. If you need a Windows 7-trustworthy build, the strongest route is to build inside the Windows 7 VM itself or at least run the produced build there.
