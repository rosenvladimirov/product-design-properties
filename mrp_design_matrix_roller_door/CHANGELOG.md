# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [18.0.1.2.0] - 2026-04-29

### Added

- Full T0/T1/T2/T3 matrix template based on "roller shuters.xlsx" BoM reference.
- T0: 9 constraint rules — PC+insulation error, min/max width (500–3300 mm),
  min/max height (300–3500 mm), per-box-size height warnings (137→1500,
  165→2400, 180→2800), manual+wide opening warning (>2000 mm).
- T1: slat geometry lookup by slat_type (hitPolicy: first):
  PVC=40mm/2.20kg·m², AL=40mm/2.68kg·m², AL_foam=40mm/3.80kg·m², PC=50mm/3.00kg·m².
  min_box_size per slat_type included.
- T2: 5 O-variant activation rules — motor-o (electric/radio), crank-o (chain),
  insulation-o, mosquito-o. Uses `bom_line_coeff_key` + `coefficient` columns.
- T3: motor install workorder (45 min) for electric; radio motor + test (60 min).
- box_size selection extended with "205" (205×205 mm) option.
- Full demo BoM (165mm box, AL slat, manual drive) with 20 BoM lines:
  - Formula-driven: AL guide, brush guide, gasket, terminal, box, axis 40/60,
    slat (linear meters), caps, security springs, taps WT-900.
  - Fixed qty: end cap, safety plate, pulley, bearing, cup 40, entry guide,
    rivets 3×8 + 4×10, stopper, package set.
  - O-variant (coeff=0): motor, axis 60, cup 60, crank, insulation, mosquito net.

### Changed

- `design_param_definitions.xml`: added `box_size = 205` option.

## [18.0.1.1.0] - 2026-04-01

### Added

- Module initial release: design parameter definitions for roller shutters.
- Empty matrix template placeholder (T0–T3 tables to be filled from BoM reference).
- Roller shutter demo product and BoM stub.
- O-variant BoM lines for motor and crank (coeff_default=0).
