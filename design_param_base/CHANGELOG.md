# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [18.0.1.0.3] - 2026-04-29

### Fixed

- Coerce `default` value from XML `<item name="default">` string to the
  declared `type` (integer/float/boolean) so Owl form widgets
  (`formatInteger`, `formatFloat`, Boolean checkbox) no longer crash
  when the stored default is a string.

## [18.0.1.0.2] - 2026-04-05

### Fixed

- Multi-company `ir.rule` for `design.param.definition`: explicit
  `company_ids = [(5, 0, 0)]` in `_process_properties` so definitions
  are always created as global (accessible by all companies).
