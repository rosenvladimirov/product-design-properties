# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [18.0.1.0.0] - 2026-04-29

### Added

- Initial industry module for roller garage door manufacturers.
- 7 design parameters: slat_type (4 options), drive_type (4 options),
  guide_type (2 options), spring_type (2 options), has_bottom_seal,
  has_side_seal, has_wicket_door.
- T0: 9 constraint rules — dimension range checks, wicket door size
  requirements, heavy-guide recommendation for wide openings.
- T1: slat properties (height_mm, weight_kg_m²) and guide rail weight
  by slat_type/guide_type using hitPolicy:collect.
- T2: 3 O-variant activation rules — motor (electric/smart drives),
  side seals (has_side_seal), wicket door kit (has_wicket_door).
- T3: 4 operations — slat cutting + assembly always; motor install &
  programming for electric/smart; QC always.
- Demo BoM with 7 BoM lines (4 formula-driven + 3 O-variants).

## 18.0.1.0.1 (2026-09-08)

### Fixed
- Демо данните реферираха `uom.product_uom_kg` — идентификатор, който не
  съществува в ядрото на 18.0 (то дефинира `product_uom_kgm`). Инсталацията
  с демо данни падаше с External ID not found. Осем места.
