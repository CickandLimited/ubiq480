# UbiQ-480 Hardware Notes

## Display (AUO G070VW01 V0)

* Native timing configured at 800×480 with a 33.2 MHz pixel clock, horizontal front/back porch of 40/88 pixels, 128 pixel HSYNC pulse, and vertical front/back porch of 5/35 lines with a 2 line VSYNC pulse. These numbers come directly from the AU Optronics G070VW01 V0 datasheet (section 3.5 "Timing Characteristics").
* LVDS mapping is set to JEIDA-18, matching the panel's 6-bit per channel LVDS description.
* The LED backlight is powered from a fixed 3.3 V rail and modulated through the SoC PWM block to achieve 16 brightness steps. The datasheet's recommended PWM base frequency of 20–25 kHz informed the 50 µs (20 kHz) period used in the device tree.

## Touchscreen (TI ADS7846)

* The resistive touch controller is attached to the CSPI1 bus with chip select routed to GPIO2_9. Pen IRQ is mapped to GPIO3_12 and flagged for falling-edge interrupts, matching the wiring notes from the i.MX31 reference schematic examples.
* Supply for the controller is shared with the display's 3.3 V regulator because the board ties the touch VDD to the LCD rail.

## Ethernet (FEC)

* The on-chip Fast Ethernet Controller operates in RMII mode. Clock gating uses the IPG and AHB roots (CCM clock indices 10 and 23) as recommended by Table 19-8 of the i.MX31 Reference Manual.
* Local MAC address placeholder is used pending manufacturing-assigned values.

## Backlight and GPIO

* GPIO2_24 enables panel power while GPIO2_25 toggles the LED enable pin, as measured on the production board harness.
* PWM0 drives the backlight dimming MOSFET with default brightness aligned to the factory 75% duty setting.

## References

1. AU Optronics, **G070VW01 V0 LCD Module Datasheet**, Rev. A3.
2. NXP, **i.MX31 Applications Processor Reference Manual**, Rev. 2, March 2008.
