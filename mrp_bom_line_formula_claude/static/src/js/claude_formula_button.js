/** @odoo-module **/
// Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import { Component, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// ── Dialog with terminal iframe for formula generation ─────────────

export class ClaudeFormulaDialog extends Component {
    static template = "mrp_bom_line_formula_claude.FormulaDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        url: { type: String, optional: true },
        wizardId: { type: Number, optional: true },
        odooConfig: { type: Object, optional: true },
    };

    get iframeSrc() {
        const base = (this.props.url || "").replace(/\/+$/, "");
        const odoo = this.props.odooConfig || {};
        const params = new URLSearchParams();
        params.append("arg", `ODOO_ORIGIN=${odoo.url || window.location.origin}`);
        params.append("arg", `ODOO_DB=${odoo.db || ""}`);
        params.append("arg", `ODOO_USER=${odoo.username || ""}`);
        params.append("arg", `ODOO_PROTOCOL=${odoo.protocol || "xmlrpc"}`);
        params.append("arg", "ODOO_MODEL=mrp.bom.line.formula.wizard");
        params.append("arg", `ODOO_RES_ID=${this.props.wizardId || 0}`);
        params.append("arg", "FORMULA_TASK=generate_bom_formula");
        return `${base}/?${params.toString()}`;
    }
}

// ── Widget button field for the wizard view ───────────────────────

export class ClaudeFormulaButton extends Component {
    static template = "mrp_bom_line_formula_claude.FormulaButton";
    static props = { ...standardFieldProps };

    setup() {
        this.dialogService = useService("dialog");
        this.claudeTerminalUrl = "";
        this.claudeOdooConfig = null;

        // Listen for Claude refresh — reload wizard when formula is written
        this._onClaudeRefresh = async ({ detail }) => {
            if (detail.model === "mrp.bom.line.formula.wizard") {
                // Reload the record to show the new formula
                await this.props.record.load();
                this.props.record.model.notify();
            }
        };
        onMounted(() => {
            this.env.bus.addEventListener("CLAUDE_REFRESH", this._onClaudeRefresh);
        });
        onWillUnmount(() => {
            this.env.bus.removeEventListener("CLAUDE_REFRESH", this._onClaudeRefresh);
        });

        onWillStart(async () => {
            try {
                const result = await rpc("/web/dataset/call_kw", {
                    model: "res.users",
                    method: "get_claude_mcp_config",
                    args: [],
                    kwargs: {},
                });
                if (result) {
                    this.claudeTerminalUrl = result.terminal_url || "";
                    this.claudeOdooConfig = result.odoo || null;
                }
            } catch {
                // MCP config not available — button will show config hint
            }
        });
    }

    get wizardId() {
        return this.props.record.data.id || this.props.record.resId;
    }

    get hasTerminal() {
        return !!this.claudeTerminalUrl;
    }

    async onClick() {
        // Force-save the record so Claude can read the wizard via RPC
        if (this.props.record.isNew || this.props.record.dirty) {
            await this.props.record.save();
        }
        this.dialogService.add(ClaudeFormulaDialog, {
            url: this.claudeTerminalUrl,
            wizardId: this.wizardId,
            odooConfig: this.claudeOdooConfig,
        });
    }
}

export const claudeFormulaButton = {
    component: ClaudeFormulaButton,
    displayName: "Claude Formula Button",
    supportedTypes: ["many2one", "integer", "char"],
    extractProps: () => ({}),
};

registry.category("fields").add("claude_formula_button", claudeFormulaButton);
