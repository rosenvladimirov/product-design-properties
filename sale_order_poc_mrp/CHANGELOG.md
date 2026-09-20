# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [19.0.1.0.0] - 2026-09-19

### Added

- Initial release: the manufacturing bridge of the production
  configuration (ADR sale-order-poc/0007–0010, 0016). No formula engine of
  its own; installs without one.
- The manufacturing order carries the configuration (`poc_id`), its lot,
  its summary in the product description and its parameters, read-only.
  Work orders show the summary and the parameters.
- Orders of different configurations are never merged into one MO; more
  quantity of the same configuration goes into its MO.
- A component manufactured for the configuration gets a lot of the
  configuration family, and the parent reserves only from that family,
  also with two-step manufacturing. Template flag "Reserve Own Component
  Lots" (default on); BoM line flag "Always Take from Stock".
- Backorders keep the configuration and its lot; with the template flag
  "New Lot per Backorder" each backorder gets the next batch. Merging MOs
  of one configuration keeps it; of different ones is refused. Serial
  numbers join the configuration family.
- Recompute from the configuration: a change of the configuration, of the
  MO quantity or Update BoM runs the explosion again and writes only the
  differences, matched by (BoM line, product), never below what was
  consumed. Draft and confirmed, not started orders are recomputed
  automatically; started ones get an activity and the button "Recompute
  from Configuration".
- A component order of the same configuration follows the parent's need
  both up and down while it has not started; a started one gets an
  activity. The core only increases it and silently keeps it too large on
  a decrease (ADR sale-order-poc/0016).
- A production manager is a configuration manager.
- Bulgarian translation. Tests with a stub engine, mutations, license
  graph and a browser tour of the MO form.

*Assisted by Claude Code*
