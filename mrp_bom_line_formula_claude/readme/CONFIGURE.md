The module requires a running Claude terminal MCP stack.  See
`l10n_bg_claude_terminal` for the full setup, and the
[odoo-claude-mcp](https://github.com/rosenvladimirov/odoo-claude-mcp)
repository for the Docker Compose configuration.

Per-user configuration lives in _Settings → Preferences → Claude
Terminal_:

- **Terminal URL** — URL of the terminal iframe (typically
  `http://localhost:8080`)
- **Odoo RPC Config** — URL, database, protocol used by the MCP server
  to talk back to Odoo

Without a configured terminal URL, the _Ask Claude_ button is disabled
and shows a configuration hint instead of opening a dialog.
