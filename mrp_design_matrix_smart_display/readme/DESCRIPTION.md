Industry sub-module for smart home display panel manufacturers.
Covers electronics assembly where the matrix drives panel size,
touch type (capacitive / resistive), MCU variant, enclosure colour,
and firmware flavour.

T2 material table resolves to different MCU SKUs via PTAV matching,
and T3 operation table conditionally adds the firmware flashing step
only when the board type requires it.
