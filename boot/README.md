# Boot Script Assets

This directory stores the plain-text U-Boot script source (`boot.cmd`). The
compiled script image (`boot.scr`) is **not** tracked in version control to keep
the repository free of binary artefacts.

To regenerate `boot.scr` after editing `boot.cmd`, run the helper located at the
repository root:

```bash
./generate_boot_assets.py boot
```

The script verifies that `mkimage` (from the `u-boot-tools` package) is
available, installs the dependency on Debian/Ubuntu hosts when necessary, and
then invokes `mkimage` with the expected load addresses for the kernel (`zImage`)
and device tree (`imx31-ubiq480-g070vw01.dtb`).

For legacy workflows the shell wrapper `scripts/mkimg.sh` remains available, but
it simply defers to the Python helper above.
