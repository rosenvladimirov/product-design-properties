/** @odoo-module **/
// Copyright 2026 BL Consulting
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Read-only DMN decision table renderer for GoRules JDM JSON fields.
 *
 * Renders the first node of a GoRules JDM document as a visual
 * decision table grid with input (blue) and output (green) columns.
 */
export class DesignMatrixField extends Component {
    static template = "mrp_design_matrix.DesignMatrixField";
    static props = {
        ...standardFieldProps,
        tableType: { type: String, optional: true },
    };

    setup() {
        this.state = useState({
            collapsed: false,
        });
    }

    // ── Getters ────────────────────────────────────────────────────────

    get rawValue() {
        return this.props.record.data[this.props.name];
    }

    /** Extract the first decision table node from the JDM structure. */
    get table() {
        const raw = this.rawValue;
        if (!raw) return null;
        // JDM format: { nodes: [{ id, name, type, content }] }
        if (raw.nodes && raw.nodes.length) {
            return raw.nodes[0];
        }
        // Fallback: maybe the field stores the node directly
        if (raw.content) {
            return raw;
        }
        return null;
    }

    get tableName() {
        return this.table?.name || "";
    }

    get inputs() {
        return this.table?.content?.inputs || [];
    }

    get outputs() {
        return this.table?.content?.outputs || [];
    }

    get rules() {
        return this.table?.content?.rules || [];
    }

    get hitPolicy() {
        return this.table?.content?.hitPolicy || "collect";
    }

    get hitPolicyLabel() {
        const labels = {
            collect: "COLLECT",
            first: "FIRST",
            priority: "PRIORITY",
        };
        return labels[this.hitPolicy] || this.hitPolicy.toUpperCase();
    }

    get hitPolicyClass() {
        const classes = {
            collect: "o_dmn_hp_collect",
            first: "o_dmn_hp_first",
            priority: "o_dmn_hp_priority",
        };
        return classes[this.hitPolicy] || "";
    }

    get hasData() {
        return this.table !== null && this.rules.length > 0;
    }

    get isEmpty() {
        return !this.rawValue;
    }

    get totalColumns() {
        return this.inputs.length + this.outputs.length;
    }

    // ── Cell display helpers ───────────────────────────────────────────

    /**
     * Format a cell value for display.
     * - Empty string / null / undefined → "--" (wildcard)
     * - Quoted strings like '"error"' → error (unquoted)
     * - Operators like '> 3000' → > 3000
     * - JSON objects → shortened display
     */
    formatCell(value) {
        if (value === undefined || value === null || value === "") {
            return { display: "--", cssClass: "o_dmn_cell_empty" };
        }
        const str = String(value);

        // Quoted string: "\"value\""
        if (str.startsWith('"') && str.endsWith('"') && str.length > 1) {
            try {
                const parsed = JSON.parse(str);
                return { display: parsed, cssClass: "" };
            } catch {
                // Not valid JSON, show as-is
            }
        }

        // Boolean
        if (str === "true") {
            return { display: "true", cssClass: "o_dmn_cell_bool" };
        }
        if (str === "false") {
            return { display: "false", cssClass: "o_dmn_cell_bool" };
        }

        // Numeric
        if (!isNaN(str) && str.trim() !== "") {
            return { display: str, cssClass: "o_dmn_cell_num" };
        }

        // Operator expressions: >, <, >=, <=, !=
        if (/^[><!]=?\s/.test(str)) {
            return { display: str, cssClass: "o_dmn_cell_op" };
        }

        // JSON object string
        if (str.startsWith("{")) {
            try {
                const obj = JSON.parse(str);
                const keys = Object.keys(obj);
                if (keys.length === 0) return { display: "{}", cssClass: "o_dmn_cell_json" };
                return {
                    display: `{${keys.join(", ")}}`,
                    cssClass: "o_dmn_cell_json",
                    title: str,
                };
            } catch {
                // Not valid JSON
            }
        }

        return { display: str, cssClass: "" };
    }

    /**
     * Determine the badge class for output cells in T0 constraint tables.
     * Recognizes error/warning levels.
     */
    levelBadgeClass(value) {
        if (!value) return "";
        const str = String(value);
        // Unquote if needed
        let level = str;
        if (str.startsWith('"')) {
            try {
                level = JSON.parse(str);
            } catch {
                // ignore
            }
        }
        if (level === "error") return "o_dmn_badge_error";
        if (level === "warning") return "o_dmn_badge_warning";
        return "";
    }

    /**
     * Get formatted cell data for a rule row.
     * Returns array of { display, cssClass, title?, badgeClass? }
     */
    getRuleCells(rule) {
        const cells = [];
        for (const input of this.inputs) {
            cells.push({
                ...this.formatCell(rule[input.id]),
                isInput: true,
            });
        }
        for (const output of this.outputs) {
            const formatted = this.formatCell(rule[output.id]);
            // Check for level badges (T0 constraint tables)
            if (output.id === "level") {
                formatted.badgeClass = this.levelBadgeClass(rule[output.id]);
            }
            formatted.isInput = false;
            cells.push(formatted);
        }
        return cells;
    }

    // ── Actions ────────────────────────────────────────────────────────

    toggleCollapse() {
        this.state.collapsed = !this.state.collapsed;
    }
}

export const designMatrixField = {
    component: DesignMatrixField,
    displayName: "Design Matrix",
    supportedTypes: ["json"],
    extractProps: ({ options }) => ({
        tableType: options?.table_type,
    }),
};

registry.category("fields").add("design_matrix", designMatrixField);
