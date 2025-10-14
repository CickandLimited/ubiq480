# Ubiq480 Build Toolkit

This repository ships build helpers for assembling the Ubiq480 software image.

## Root filesystem generation

The `build.py` helper exposes a small CLI:

```
./build.py rootfs
```

Running the `rootfs` command on a Linux host (as root) invokes `debootstrap`
to assemble a Debian Bookworm `armel` root filesystem.  The resulting tree is
staged inside `output/rootfs/`.  Configuration files such as `/etc/fstab`,
hostname, networking, and the serial console getty override are written
automatically during the build.  When `qemu-user-static` is available the
static `qemu-arm` binary is copied into the rootfs to assist with any follow-up
configuration inside the chroot.

Install the required tooling before running the command:

```
sudo apt-get install debootstrap qemu-user-static
```

All artifacts in the `output/` directory are ignored by Git and can be safely
removed when no longer needed.
