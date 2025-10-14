# SPDX-License-Identifier: GPL-2.0+

ARCH ?= arm
DTC ?= dtc
CPP ?= cpp

srctree := $(CURDIR)
DTS_DIR := $(srctree)/arch/$(ARCH)/boot/dts
CPP_INCLUDE_DIRS := -I$(DTS_DIR)

include $(DTS_DIR)/Makefile

DTB_NAMES := $(dtb-y)
DTB := $(addprefix $(DTS_DIR)/,$(DTB_NAMES))
DTS := $(DTB:.dtb=.dts)

all: $(DTB)

$(notdir $(DTB)): %: $(DTS_DIR)/%
	@echo "Built $@"

$(DTS_DIR)/%.dtb: $(DTS_DIR)/%.dts $(DTS_DIR)/imx31.dtsi
	@mkdir -p $(dir $@)
	$(CPP) -P -nostdinc -undef -x assembler-with-cpp $(CPP_INCLUDE_DIRS) $< > $@.tmp
	$(DTC) -q -I dts -O dtb -i $(DTS_DIR) -o $@ $@.tmp
	@rm -f $@.tmp

clean:
	rm -f $(DTB)

.PHONY: all clean imx31-ubiq480-g070vw01.dtb
