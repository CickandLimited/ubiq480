# U-Boot boot script for Advantech UbiQ-480-ENWPLE
#
# Environment assumptions:
#   - Primary console is provided on the SoC UART at ttymxc0 running 115200 8N1.
#   - Root filesystem is available on the second partition of the boot microSD (mmcblk0p2).
#   - Kernel and DTB are stored on the FAT32 boot partition (mmcblk0p1).

setenv bootargs console=ttymxc0,115200 root=/dev/mmcblk0p2 rw rootwait video=mx3fb:800x480M-16@60
fatload mmc 0:1 0x8000 zImage
fatload mmc 0:1 0x100000 imx31-ubiq480-g070vw01.dtb
bootz 0x8000 - 0x100000
