# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [18.0.1.3.0] - 2026-05-25

### Added

- `cascade_table` seed (TΦ Cascade — Phase A) — 12 rules за color cascade:
  когато `main_color` се промени → 12-те `color_*` sub-property params
  (`color_slat`, `color_caps`, `color_box`, `color_endcap`, `color_central_endcap`,
  `color_terminal`, `color_guide`, `color_brush`, `color_package`, `color_rope`,
  `color_shirit`, `color_safety`) получават новата стойност с `only_if_empty=true`.
  Modern JDM format from the start (inputNode → decisionTableNode → outputNode + edges).
  Заменя `_teolinoColorCascade` JS hardcode в teolino_sale_design_configurator_ui.

## [18.0.1.2.0] - 2026-05-23

### Added

- TΠ availability_table seed за template "Roller Shutters — 5 models".
  10 правила, hitPolicy=collect:
  - `built_in` → `box_size` disabled + auto-set `"none"`
  - `round`/`built_in`/`thermo_comfort` → `shutter_count` restricted to `["1"]`
  - `t_roll` → `shutter_count` restricted to `["1", "2"]`
  - `standard`/`round` → `box_size` restricted to `["137","165","180","205"]`
  - `t_roll`/`thermo_comfort` → `box_size` restricted to `["170","210"]`
  - `!= thermo_comfort` → `guide_type` restricted to `["standard"]`
    (feather guide само за Thermo)

  Modern JDM формат отначало (`inputNode → decisionTableNode → outputNode` +
  edges + `field` на всички колони).

## [18.0.1.1.0] - 2026-05-23

### Changed

- `data/matrix_templates.xml` — T0/T1/T2/T3 seed-овете на template
  *Roller Shutters — 5 models* преписани в modern zen-engine ≥ 0.50
  формат: `inputNode → decisionTableNode → outputNode` с explicit
  `edges`, и `field` (= id) на всички input/output колони.
  При fresh install `ZenWrapper._migrate_node_types` става no-op за
  тоя template. `noupdate="1"` — съществуващи записи на работещи
  бази НЕ се пренаписват.

## [18.0.1.0.0] - 2026-04-15

### Added

- Initial release: parametric 5-model roller-shutter range
  (Standard, Round, T-Roll, Built-In, Thermo Comfort) с DMN
  T0–T3 матрица и demo BoM (`demo_bom_teolino_standard.xml`).
