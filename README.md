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

Install the required tooling before attempting a build.  Debian/Ubuntu hosts
can use the following package set as a starting point:

```
sudo apt-get install build-essential git u-boot-tools gcc-arm-linux-gnueabi \
    binutils-arm-linux-gnueabi debootstrap qemu-user-static dosfstools \
    e2fsprogs util-linux
```

The final image assembly (`image` stage) requires root privileges because it
creates loop devices, partitions them, and mounts the resulting filesystems.
