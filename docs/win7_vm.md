# Windows 7 VM Workflow

This is the practical workflow for validating the `win7-spike` branch from Linux.

## Host setup

Install the minimum QEMU packages on the Linux host:

```bash
sudo apt-get update
sudo apt-get install -y qemu-system-x86 qemu-utils
```

If you want hardware acceleration, add your user to the `kvm` group and log out/in:

```bash
sudo usermod -aG kvm "$USER"
```

## Guest assets

You must provide your own Windows 7 SP1 ISO and license.

Create the VM disk and shared folder:

```bash
scripts/create_win7_vm.sh
```

That creates:

- `.vm/win7/win7.qcow2`
- `.vm/win7/share/`

## First boot and install

Start the VM with the Windows 7 ISO attached:

```bash
scripts/run_win7_vm.sh --iso /absolute/path/to/windows7.iso
```

The VM uses:

- IDE disk for maximum guest compatibility
- `e1000` networking so Windows 7 does not need VirtIO drivers just to boot
- a FAT-backed shared disk at `.vm/win7/share`

## Moving files into the guest

Anything copied into `.vm/win7/share/` appears to the guest as an extra disk.

Use that folder for:

- the repository checkout itself, if you want to build inside the VM
- the vendored offline toolchain under `vendor/windows/`
- the whole built `dist/windows/` directory when you want to validate the exact handoff bundle
- installer scripts or the optional NSIS setup
- test notes and logs

## Recommended trust model

For the strongest Windows 7 confidence:

1. populate `vendor/windows/` on the host
2. copy the repository into the VM share
3. build from inside the Windows 7 VM with [`scripts/build_windows.ps1`](../scripts/build_windows.ps1)
4. install from the produced `dist/windows/` bundle inside that same VM

That path keeps both the build and the validation on an actual Windows 7 environment.

## What this actually proves

From Linux, this VM lets you validate:

- whether the vendored toolchain starts on Windows 7
- whether the built bundle launches on Windows 7
- whether the Tk window opens correctly
- whether the HTTP UI loads in the guest browser
- whether Win32 key injection works against a real Windows 7 guest app

GitHub Actions and modern Windows builders are useful for scaffolding checks, but they are not a replacement for this trust path when Windows 7 behavior matters.
