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

(steps omitted for brevity in code sample)
