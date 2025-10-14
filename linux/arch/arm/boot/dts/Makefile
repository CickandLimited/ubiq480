# SPDX-License-Identifier: GPL-2.0+

dtb-y += imx31-ubiq480-g070vw01.dtb

# Allow the top-level Makefile to know which device trees exist.
DTBS := $(addprefix $(dir $(lastword $(MAKEFILE_LIST))),$(dtb-y))
