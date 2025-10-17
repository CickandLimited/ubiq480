# Ubiq480 Build Toolkit

This repository ships build helpers for assembling the Ubiq480 software image.

## Build pipeline

All build stages are coordinated by `build.py`.  The helper includes dedicated
subcommands for each component as well as an `all` meta target that produces a
fully populated microSD image in a single invocation.

```
./build.py deps     # verify required host dependencies
./build.py all      # build bootloader, kernel, rootfs and ubiq480.img
```

Before any stage runs, the helper prints a summary of the artefacts that will be
downloaded or created along with their estimated sizes.  Confirm the prompt to
continue or abort with the default `N` response.  Supply `--yes` for
non-interactive or automated environments to skip the confirmation while still
emitting the summary, for example:

```
./build.py --yes all
```

The following artefacts are written to `output/`:

* `u-boot.bin` – U-Boot bootloader binary.
* `zImage` – Linux kernel image.
* `imx31-ubiq480-g070vw01.dtb` – platform device tree blob.
* `boot.scr` – compiled boot script.
* `rootfs/` – Debian Bookworm ARMEL root filesystem.
* `ubiq480.img` – bootable microSD card image.
* `build.log` – aggregated log output mirroring the console.

Source checkouts are cached under `output/cache/` so subsequent runs only need
to rebuild changed artefacts.  All of these files remain ignored by Git via the
repository `.gitignore` rules.

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
    binutils-arm-linux-gnueabi debootstrap qemu-user-static dosfstools \
    e2fsprogs util-linux
```

The final image assembly (`image` stage) requires root privileges because it
creates loop devices, partitions them, and mounts the resulting filesystems.
