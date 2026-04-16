# Windows 7 VM Workflow

This is the practical maintainer workflow for validating the `win7-spike` branch from Linux.

## Why this document exists

Use the VM when you want a Windows 7 environment for maintainer work:

- to build the Windows 7 package if you do not want to use a Windows 10 machine
- to validate that the produced installer still works on Windows 7
- to troubleshoot old-platform behavior in a safer, repeatable setup

Do not point normal end users to this document. It is for maintainers.

## Relationship to the normal user path

The normal user path is still simple:

1. A maintainer builds the package on Windows 10 or in this Windows 7 VM.
2. The maintainer produces `mobile-typer-win7-setup.exe`.
3. The Windows 7 end user runs that installer.

The VM exists to help the maintainer create and validate that installer, not to give end users more manual steps.

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

Use that folder for maintainer work such as:

- the repository checkout itself, if you want to build inside the VM
- the vendored offline toolchain under [`vendor/windows/`](../vendor/windows/)
- the full `dist/windows/` directory when you want to inspect the staged outputs
- the final `mobile-typer-win7-setup.exe` when you want to verify the exact user installer
- test notes and logs

## Recommended trust model

For the strongest Windows 7 confidence:

1. populate [`vendor/windows/`](../vendor/windows/) on the host
2. copy the repository into the VM share
3. build from inside the Windows 7 VM with [`scripts/build_windows.ps1`](../scripts/build_windows.ps1)
4. confirm that the build produced `dist/windows/mobile-typer-win7-setup.exe`
5. run that installer inside the VM exactly the way an end user would

That path keeps both the build and the validation on an actual Windows 7 environment.

## Alternative maintainer path

If you already have a trusted Windows 10 machine, you can build there instead and use the VM only for validation.

That is also a supported maintainer flow:

1. populate [`vendor/windows/`](../vendor/windows/)
2. build on Windows 10 with [`scripts/build_windows.ps1`](../scripts/build_windows.ps1)
3. copy `mobile-typer-win7-setup.exe` into the VM
4. run the installer in the VM to confirm the final user experience

## What this actually proves

From Linux, this VM lets you validate:

- whether the vendored toolchain starts on Windows 7
- whether the built installer launches on Windows 7
- whether the installed app launches on Windows 7
- whether the Tk window opens correctly
- whether the HTTP UI loads in the guest browser
- whether Win32 key injection works against a real Windows 7 guest app

GitHub Actions and modern Windows builders are useful for scaffolding checks, but they are not a replacement for this trust path when Windows 7 behavior matters.

## KB2533623 note

The goal is still to hand users one normal installer. But some very old Windows 7 systems may be missing update `KB2533623`, which the bundled Python 3.8 runtime may need.

Use the VM to help separate installer problems from that underlying platform limit.
