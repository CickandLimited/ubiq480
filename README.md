# Ubiq480 Build Toolkit

This repository ships build helpers for assembling the Ubiq480 software image.

## Build pipeline

All build stages are coordinated by `build.py`.  The helper includes dedicated
subcommands for each component as well as an `all` meta target that produces a
fully populated microSD image in a single invocation.

Running `./build.py` without arguments opens an interactive menu that lists the
available build stages.  Select one or more entries to queue up tasks for the
current session or press `q`/`Ctrl+C` to abort.  This is especially convenient
for exploratory workflows where you want to run a subset of stages without
remembering every subcommand name.

```
./build.py             # interactive picker
./build.py deps        # headless mode via argparse
./build.py --yes all   # build bootloader, kernel, rootfs and ubiq480.img
```

Before any stage runs, the helper prints a summary of the artefacts that will be
downloaded or created along with their estimated sizes.  Confirm the prompt to
continue or abort with the default `N` response.  Supply `--yes` for
non-interactive or automated environments to skip the confirmation while still
emitting the summary.

The following artefacts are written to `output/`:

* `u-boot.bin` – U-Boot bootloader binary.
* `zImage` – Linux kernel image.
* `imx31-ubiq480-g070vw01.dtb` – platform device tree blob.
* `boot.scr` – compiled boot script.
* `rootfs/` – Debian Bookworm ARMEL root filesystem.
* `ubiq480.img` – bootable microSD card image.

Source checkouts are cached under `output/cache/` so subsequent runs only need
to rebuild changed artefacts.  All of these files remain ignored by Git via the
repository `.gitignore` rules.  Console output is mirrored to a tracked
`build.log` file at the repository root for post-run inspection.

### Root filesystem generation

The `rootfs` stage internally runs `debootstrap` with QEMU user-mode emulation
support when available.  The resulting filesystem tree includes essential
configuration files (e.g. `/etc/fstab`, hostname, and serial console service
overrides) and is staged to `output/rootfs/`.

Running `./build.py deps` now attempts to bootstrap the environment when
possible.  Missing commands are installed via `apt-get` or `dnf` and Python
dependencies declared in `requirements.txt` are placed inside a reusable
virtual environment at `output/venv/`.  If the helper cannot obtain elevated
privileges or a supported package manager is unavailable it falls back to
reporting the missing tools so they can be installed manually.

Supply `--no-bootstrap` to skip any automated installation attempts and only
perform validation:

```
./build.py --no-bootstrap deps
```

Manual package installation remains an option.  Debian/Ubuntu hosts can use the
following package set as a starting point:

```
sudo apt-get install build-essential git u-boot-tools gcc-arm-linux-gnueabi \
    binutils-arm-linux-gnueabi debootstrap bison flex qemu-user-static \
    dosfstools e2fsprogs util-linux
```

The final image assembly (`image` stage) requires root privileges because it
creates loop devices, partitions them, and mounts the resulting filesystems.

## Boot assets helper

`generate_boot_assets.py` follows the same pattern.  Launch it without
arguments to receive a menu for ensuring dependencies or rebuilding `boot.scr`.
Individual actions remain available as subcommands for scripts or CI jobs:

```
./generate_boot_assets.py          # interactive menu
./generate_boot_assets.py deps     # ensure mkimage is installed
./generate_boot_assets.py boot     # rebuild boot.scr immediately
```
