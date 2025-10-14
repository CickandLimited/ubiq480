# Advantech UbiQ-480-ENWPLE — System Rebuild Specification

## 1. Overview

This document defines all known **hardware specifications**, **software build requirements**, and the **build pipeline** needed to create a working Linux system image for the **Advantech UbiQ-480-ENWPLE** (part of the UbiQ-480 series).

The intended output is a **bootable microSD image** that can replace the original VIX ACIS firmware, boot a modern Debian-based Linux with a GUI, and support future application deployment (e.g. transit display or kiosk interface).

---

## 2. Hardware Specification

| Category | Detail |
|-----------|---------|
| **Manufacturer** | Advantech |
| **Model** | UbiQ-480-ENWPLE |
| **Form Factor** | 7" Embedded Panel PC |
| **Display** | AU Optronics **G070VW01 V0**, 7" TFT LCD |
| **Native Resolution** | 800 × 480 pixels (WVGA) |
| **Interface** | LVDS 18-bit |
| **Brightness** | ~450 cd/m² |
| **Backlight Type** | LED (PWM or GPIO control) |
| **Touch Controller** | 4-wire resistive (USB or serial interface) |
| **CPU / SoC** | Freescale / NXP **i.MX31** (ARM1136JF-S core) |
| **Architecture** | ARMv6, ARM1136JF-S with VFP |
| **Clock Speed** | 532 MHz (typical) |
| **GPU** | none (framebuffer output via mx3fb driver) |
| **RAM** | 64 MB DDR1 (SDRAM) |
| **Storage (factory)** | Removable microSD card (boot + rootfs) |
| **I/O Ports** | RJ-45 Ethernet (PoE-enabled), RS-232 (DB-9), Mini-USB (OTG), internal GPIO headers |
| **Power** | IEEE 802.3af PoE, 48 V DC input |
| **Boot Method** | microSD / NAND (DIP switch selectable) |
| **DIP Switches** | Boot source selection (ON = SD boot) |
| **Onboard Components (confirmed)** | - Freescale i.MX31 SoC<br>- Ethernet PHY (Micrel KSZ8041)<br>- SD slot<br>- RTC crystal (19.200 MHz)<br>- Touch controller (likely ADS7846 or compatible) |
| **Observed Board Label** | “UBIQ-480-ENWPLE / Rev. x.x” |
| **Special Hardware Notes** | - RS-232 can provide root console during U-Boot and Linux.<br>- Device uses a small mod (resistor bridge) likely for voltage level or boot-mode stability.<br>- DIP switch combinations affect boot source and serial console enablement.<br>- 800×480 framebuffer works with `mx3fb` driver. |

---

## 3. Software Requirements

| Component | Version / Notes |
|------------|----------------|
| **Base OS** | Debian 12 (Bookworm) or similar minimal ARMv6-compatible distribution |
| **Kernel Version** | 5.10 LTS or older 4.9.x BSP (NXP i.MX31 supported) |
| **Bootloader** | U-Boot v2016.09 or later (supports i.MX31ADS reference board) |
| **Device Tree** | Custom `imx31-ubiq480-g070vw01.dts` derived from `imx31.dtsi` |
| **Toolchain** | GCC 7.5.0 (Linaro ARM EABI) |
| **Display Driver** | `mx3fb` (Framebuffer) |
| **Filesystem** | ext4 (root) + FAT32 (boot) |
| **Networking** | `fec` Ethernet driver |
| **Input** | `ads7846` touchscreen driver or `evdev` generic input |
| **GUI** | Lightweight WM (Matchbox or LXDE) |
| **SSH Access** | Dropbear or OpenSSH |
| **Power / Backlight** | GPIO- or PWM-controlled via device tree |
| **Root Login** | Auto-login (root / toor) for setup convenience |

---

## 4. Build Host Requirements

| Item | Specification |
|------|----------------|
| **Host OS** | Debian 12 / Ubuntu 22.04 (x86_64) |
| **RAM** | ≥ 4 GB |
| **Disk Space** | ≥ 20 GB free |
| **Required Packages** | `git make gcc-arm-linux-gnueabi binutils-arm-linux-gnueabi libssl-dev bison flex swig python3-distutils libncurses-dev libgmp-dev libmpfr-dev libmpc-dev dtc` |

---

## 5. Source Trees

| Repository | Purpose | Notes |
|-------------|----------|-------|
| **U-Boot** | Bootloader | `https://source.denx.de/u-boot/u-boot.git` |
| **Linux Kernel** | Mainline or NXP BSP | `https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git` |
| **Toolchain** | Linaro GCC | `https://releases.linaro.org/components/toolchain/binaries/latest-7/arm-linux-gnueabi/` |

---

## 6. Build Workflow



Clone Repositories

mkdir -p ~/ubiq480 && cd ~/ubiq480
git clone https://source.denx.de/u-boot/u-boot.git
git clone https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git
wget https://releases.linaro.org/components/toolchain/binaries/latest-7/arm-linux-gnueabi/gcc-linaro-7.5.0-2019.12-x86_64_arm-linux-gnueabi.tar.xz
tar -xf gcc-linaro-7.5.0-2019.12-x86_64_arm-linux-gnueabi.tar.xz
export PATH=$PWD/gcc-linaro-7.5.0-2019.12-x86_64_arm-linux-gnueabi/bin:$PATH
export CROSS_COMPILE=arm-linux-gnueabi-
export ARCH=arm


Build U-Boot

cd u-boot
git checkout v2016.09
make mx31ads_config
make KCFLAGS=-march=armv5te -j$(nproc)


Output: u-boot.bin

Build Kernel

cd ../linux
git checkout v5.10.217
make imx_v6_v7_defconfig
make zImage KCFLAGS="-march=armv6 -mtune=arm1136jf-s -mfloat-abi=softfp -mfpu=vfp" -j$(nproc)


Add Custom Device Tree

Path: arch/arm/boot/dts/imx31-ubiq480-g070vw01.dts

Content defines display timings, memory size, GPIO backlight, and aliases.

Compile:

make arch/arm/boot/dts/imx31-ubiq480-g070vw01.dtb KCFLAGS="-march=armv6 -mtune=arm1136jf-s -mfloat-abi=softfp -mfpu=vfp"


Output: arch/arm/boot/dts/imx31-ubiq480-g070vw01.dtb

Prepare Boot Script

boot.cmd

setenv bootargs console=ttymxc0,115200 root=/dev/mmcblk0p2 rw rootwait video=mx3fb:800x480M-16@60
fatload mmc 0:1 0x8000 zImage
fatload mmc 0:1 0x100000 imx31-ubiq480-g070vw01.dtb
bootz 0x8000 - 0x100000


Compile it:

mkimage -A arm -T script -C none -n "UbiQ480 Boot" -d boot.cmd boot.scr

7. Image Layout
Partition	Filesystem	Contents	Size
Boot (p1)	FAT32	u-boot.bin, zImage, imx31-ubiq480-g070vw01.dtb, boot.scr	64 MB
Root (p2)	ext4	Debian rootfs (debootstrap or prebuilt)	≥ 1 GB
8. Expected Boot Sequence

Power on (PoE injector supplies 48 V).

U-Boot loads from microSD (DIP 1 = OFF, DIP 2 = ON).

boot.scr executes kernel and DTB load.

Kernel initialises framebuffer and mounts rootfs.

Login prompt or GUI auto-login appears.

Serial console: /dev/ttymxc0 @ 115200 8N1.
SSH available via DHCP-assigned IP.

9. Verification
Check	Expected Result
Serial output	U-Boot and kernel messages visible
Framebuffer	800×480 console visible
Ethernet	DHCP lease acquired
Rootfs mount	/ on /dev/mmcblk0p2
SSH	Login via Dropbear
GUI	Matchbox or LXDE desktop shown
10. Future Work

Add ADS7846 touchscreen driver & calibration (xinput_calibrator).

Map GPIOs for backlight control.

Create systemd service for auto-start kiosk app.

Generate OTA update mechanism.

Package as reproducible .img for Etcher.

11. Repository Structure
ubiq480/
 ├── u-boot/                # Bootloader sources
 ├── linux/                 # Kernel sources
 ├── rootfs/                # Minimal Debian root filesystem
 ├── scripts/
 │    ├── ubiq480_build.py  # Automated build & logging tool
 │    └── mkimg.sh          # SD card image creation
 ├── boot/
 │    ├── boot.cmd
 │    └── boot.scr
 ├── docs/
 │    ├── build-spec.md     # This document
 │    ├── hardware-notes.md
 │    └── debug-log.md
 └── README.md

12. References

U-Boot: https://source.denx.de/u-boot/u-boot

NXP i.MX31 Reference Manual: [IMX31RM.pdf]

AUO G070VW01 V0 Datasheet

Debian ARM Ports: https://wiki.debian.org/ArmPorts

Linaro Toolchains: https://releases.linaro.org/components/toolchain/binaries/

13. Goal for the Agent

A coding agent (with terminal access and permission to install dependencies) should be able to:

Clone the GitHub repository containing this document and the build scripts.

Run a single orchestrator (build.py or make all) that:

verifies dependencies;

builds U-Boot, kernel, DTB;

generates a boot.scr;

assembles the SD image;

and logs everything to build.log.

Upload logs or images back to the repo for validation.
