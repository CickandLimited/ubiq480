# SPDX-License-Identifier: GPL-2.0+

dtb-$(CONFIG_ARCH_MXC) += \
	imx31-ubiq480-g070vw01.dtb

dtb-y += $(dtb-$(CONFIG_ARCH_MXC))

# Allow the top-level Makefile to know which device trees exist.
DTBS := $(addprefix $(dir $(lastword $(MAKEFILE_LIST))),$(dtb-y))
