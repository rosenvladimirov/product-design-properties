# Changelog

All notable changes to this module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [18.0.1.0.0] - 2026-04-04

### Added

- New module: Claude AI assistance for BoM line formula generation
- **Ask Claude** button in formula wizard (next to formula editor)
- Embedded Claude terminal via iframe (same pattern as `l10n_bg_claude_terminal`)
- URL parameters pass: Odoo RPC config, wizard model, wizard res_id, formula task hint
- `claude_brief` field: auto-computed JSON context with BoM line, matrix tables, design param definition
- `claude_instructions` field: static task description that Claude reads on start
- Bus refresh listener: wizard reloads automatically when Claude writes formula via MCP
- Full flow: Claude reads wizard → generates formula → `odoo_write` → `odoo_refresh` → wizard shows new formula

### Depends

- `mrp_bom_line_formula_wizard` — base wizard with formula editor
- `mrp_bom_line_formula_template` — extended formula output variables (result, product, uom)
- `l10n_bg_claude_terminal` — terminal URL configuration + bus refresh service

*Assisted by Claude Code*
