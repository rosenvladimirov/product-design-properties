/** @odoo-module **/
// Copyright 2026 BL Consulting
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import { Component } from "@odoo/owl";

/**
 * RuleMatrixPreview — real-time constraint evaluation display.
 *
 * Shows real-time evaluation of GoRules DMN matrix tables against
 * a set of design parameters. Used in BoM preview and SO configurator.
 *
 * T0: Constraints — real-time rule match with error/warning/ok.
 * T1: Geometry — computed values from geometry_table.
 * T2: Materials — BoM composition with qty × coeff = final.
 * T3: Operations — conditional workorder cards.
 */
export class RuleMatrixPreview extends Component {
    static template = "mrp_design_matrix.RuleMatrixPreview";

    static props = {
        params: { type: Object },
        constraintTable: { type: [Object, { value: false }], optional: true },
        geometryTable: { type: [Object, { value: false }], optional: true },
        materialTable: { type: [Object, { value: false }], optional: true },
        operationTable: { type: [Object, { value: false }], optional: true },
        bomLines: { type: Array, optional: true },
    };

    // ── T0 — Constraint evaluation ──────────���──────────────────────────

    get t0() {
        const table = this._getTableContent(this.props.constraintTable);
        if (!table) return null;

        const inputs = table.inputs || [];
        const outputs = table.outputs || [];
        const rules = table.rules || [];
        const hitPolicy = table.hitPolicy || "collect";

        const results = [];
        for (const rule of rules) {
            const matched = this._evaluateRule(rule, this.props.params, inputs);
            const level = this._extractOutput(rule, outputs, "level");
            const message = this._extractOutput(rule, outputs, "message");
            const description = this._buildRuleDescription(rule, inputs);

            results.push({
                matched,
                level: matched ? level : "ok",
                message: matched ? message : description,
                description,
                icon: matched
                    ? level === "error" ? "fa-times-circle" : "fa-exclamation-triangle"
                    : "fa-check-circle",
                cssClass: matched
                    ? level === "error" ? "error" : "warning"
                    : "ok",
            });
        }
        return { results, hitPolicy };
    }

    get hasT0() {
        return this.t0 !== null && this.t0.results.length > 0;
    }

    get t0Errors() {
        if (!this.t0) return 0;
        return this.t0.results.filter(r => r.level === "error").length;
    }

    get t0Warnings() {
        if (!this.t0) return 0;
        return this.t0.results.filter(r => r.level === "warning").length;
    }

    get t0StatusText() {
        const errs = this.t0Errors;
        const warns = this.t0Warnings;
        const parts = [];
        if (errs) parts.push(`${errs} error${errs > 1 ? "s" : ""}`);
        if (warns) parts.push(`${warns} warning${warns > 1 ? "s" : ""}`);
        return parts.length ? parts.join(", ") : "All OK";
    }

    get t0StatusClass() {
        if (this.t0Errors) return "error";
        if (this.t0Warnings) return "warning";
        return "ok";
    }

    // ── T1 — Geometry evaluation ──────────────────────────────────────

    get t1() {
        const table = this._getTableContent(this.props.geometryTable);
        if (!table) return null;

        const inputs = table.inputs || [];
        const outputs = table.outputs || [];
        const rules = table.rules || [];
        const hitPolicy = table.hitPolicy || "first";

        const values = {};
        for (const rule of rules) {
            const matched = this._evaluateRule(rule, this.props.params, inputs);
            if (!matched) continue;

            for (const out of outputs) {
                const raw = rule[out.id];
                if (!raw && raw !== 0 && raw !== false) continue;
                const val = this._decodeJDMValue(raw);
                if (hitPolicy === "first" && !(out.id in values)) {
                    values[out.id] = { name: out.name || out.id, value: val };
                } else if (hitPolicy === "collect") {
                    // Collect: last match wins (overwrite)
                    values[out.id] = { name: out.name || out.id, value: val };
                }
            }
            if (hitPolicy === "first" && Object.keys(values).length === outputs.length) {
                break; // All outputs resolved
            }
        }

        const entries = Object.values(values);
        return entries.length ? entries : null;
    }

    get hasT1() {
        return this.t1 !== null;
    }

    // ── T2 — Materials / BoM composition ────────────────────────────────

    get t2() {
        const bomLines = this.props.bomLines || [];
        if (!bomLines.length) return null;

        const table = this._getTableContent(this.props.materialTable);
        const tableInputs = table ? (table.inputs || []) : [];
        const tableRules = table ? (table.rules || []) : [];
        const tableOutputs = table ? (table.outputs || []) : [];

        const lines = [];
        for (const line of bomLines) {
            const baseQty = line.product_qty || 0;
            let coeff = line.coeff_default !== undefined ? line.coeff_default : 1.0;
            let coeffSource = "default";

            // If line has a matrix_coeff_rule key, search materialTable
            if (line.matrix_coeff_rule && table) {
                const found = this._findMatrixCoeff(
                    line.matrix_coeff_rule, tableRules, tableInputs, tableOutputs
                );
                if (found !== null) {
                    coeff = found;
                    coeffSource = "matrix";
                }
            }

            const finalQty = baseQty * coeff;
            const inactive = finalQty === 0;
            const modified = coeff !== 1.0;

            lines.push({
                name: line.product_name || `Product #${line.product_id}`,
                productId: line.product_id,
                baseQty,
                coeff,
                finalQty: Math.round(finalQty * 1000) / 1000,
                inactive,
                modified,
                coeffSource,
                cssClass: inactive ? "inactive" : modified ? "modified" : "",
            });
        }
        return lines.length ? lines : null;
    }

    get hasT2() {
        return this.t2 !== null;
    }

    get t2ActiveCount() {
        if (!this.t2) return 0;
        return this.t2.filter(l => !l.inactive).length;
    }

    /**
     * Find coefficient from materialTable for a given coeff rule key.
     * Searches rules that match current params and have the coeff output.
     */
    _findMatrixCoeff(coeffKey, rules, inputs, outputs) {
        // Look for an output column matching the coeffKey
        const coeffOut = outputs.find(o => o.id === coeffKey);
        if (!coeffOut) return null;

        for (const rule of rules) {
            const matched = this._evaluateRule(rule, this.props.params, inputs);
            if (!matched) continue;
            const raw = rule[coeffOut.id];
            if (raw === undefined || raw === null || raw === "") continue;
            const val = parseFloat(this._decodeJDMValue(raw));
            if (!isNaN(val)) return val;
        }
        return null;
    }

    // ── T3 — Operations evaluation ─────────────────────────────────────

    get t3() {
        const table = this._getTableContent(this.props.operationTable);
        if (!table) return null;

        const inputs = table.inputs || [];
        const outputs = table.outputs || [];
        const rules = table.rules || [];

        const ops = [];
        for (const rule of rules) {
            const matched = this._evaluateRule(rule, this.props.params, inputs);
            const opName = this._extractOutput(rule, outputs, "operation")
                        || this._extractOutput(rule, outputs, "name")
                        || this._buildRuleDescription(rule, inputs);
            const duration = this._extractOutput(rule, outputs, "duration");
            const workcenter = this._extractOutput(rule, outputs, "workcenter");

            ops.push({
                name: opName,
                duration: duration ? `${duration} min` : "",
                workcenter: workcenter || "",
                active: matched,
                cssClass: matched ? "active" : "inactive",
            });
        }
        return ops.length ? ops : null;
    }

    get hasT3() {
        return this.t3 !== null;
    }

    get t3ActiveCount() {
        if (!this.t3) return 0;
        return this.t3.filter(o => o.active).length;
    }

    // ── Rule evaluation engine ─────────────────────────────────────────

    /**
     * Evaluate a single rule against current params.
     * Returns true if ALL input conditions match (rule fires).
     * Empty cell = wildcard (always matches).
     */
    _evaluateRule(rule, params, inputs) {
        for (const input of inputs) {
            const ruleVal = rule[input.id];
            if (!ruleVal && ruleVal !== false && ruleVal !== 0) continue;

            const paramVal = params[input.id];
            if (paramVal === undefined) continue;

            if (!this._matchCell(ruleVal, paramVal)) return false;
        }
        return true;
    }

    /**
     * Match a single JDM cell value against a param value.
     */
    _matchCell(ruleVal, paramVal) {
        const str = String(ruleVal);

        // Empty = wildcard
        if (str === "") return true;

        // Quoted string: exact match
        if (str.startsWith('"') && str.endsWith('"') && str.length > 1) {
            try {
                return paramVal === JSON.parse(str);
            } catch {
                return false;
            }
        }

        // Boolean
        if (str === "true") return paramVal === true;
        if (str === "false") return paramVal === false;

        // Comparison operators
        if (str.startsWith(">= ")) return Number(paramVal) >= parseFloat(str.slice(3));
        if (str.startsWith("<= ")) return Number(paramVal) <= parseFloat(str.slice(3));
        if (str.startsWith("> "))  return Number(paramVal) > parseFloat(str.slice(2));
        if (str.startsWith("< "))  return Number(paramVal) < parseFloat(str.slice(2));

        // Not-equal
        if (str.startsWith("!= ")) {
            const cmp = str.slice(3).trim();
            if (cmp.startsWith('"')) {
                try { return paramVal !== JSON.parse(cmp); } catch { return false; }
            }
            return paramVal !== cmp;
        }

        // Numeric equality
        if (!isNaN(str) && str.trim() !== "") {
            return Number(paramVal) === parseFloat(str);
        }

        // Fallback: string equality
        return String(paramVal) === str;
    }

    // ── Helpers ────────────────────────────────────────────────────────

    /**
     * Extract the first decision table content from a JDM structure.
     */
    _getTableContent(table) {
        if (!table) return null;
        if (table.nodes && table.nodes.length) {
            return table.nodes[0].content || null;
        }
        if (table.content) {
            return table.content;
        }
        return null;
    }

    /**
     * Extract an output value from a rule, decoding JDM quoting.
     */
    _extractOutput(rule, outputs, outputId) {
        const out = outputs.find(o => o.id === outputId);
        if (!out) return "";
        const val = rule[out.id];
        if (!val && val !== false && val !== 0) return "";
        const str = String(val);
        // Unquote JDM strings
        if (str.startsWith('"') && str.endsWith('"') && str.length > 1) {
            try { return JSON.parse(str); } catch { /* pass */ }
        }
        return str;
    }

    /**
     * Decode a JDM value to its native form.
     * "\"error\"" → "error", "3.5" → 3.5, "true" → true
     */
    _decodeJDMValue(raw) {
        if (raw === undefined || raw === null) return "";
        const str = String(raw);
        if (str.startsWith('"') && str.endsWith('"') && str.length > 1) {
            try { return JSON.parse(str); } catch { /* pass */ }
        }
        if (str === "true") return true;
        if (str === "false") return false;
        if (!isNaN(str) && str.trim() !== "") return parseFloat(str);
        return str;
    }

    /**
     * Build a human-readable description of a rule's input conditions.
     * e.g., "width < 600" or "construction = glass, leaf_type = double"
     */
    _buildRuleDescription(rule, inputs) {
        const parts = [];
        for (const input of inputs) {
            const val = rule[input.id];
            if (!val && val !== false && val !== 0) continue;
            const str = String(val);
            if (str === "") continue;

            const name = input.name || input.id;
            // Decode display value
            let display = str;
            if (str.startsWith('"') && str.endsWith('"') && str.length > 1) {
                try { display = `= ${JSON.parse(str)}`; } catch { /* pass */ }
            } else if (/^[><!]=?\s/.test(str)) {
                display = str;
            } else if (str === "true" || str === "false") {
                display = `= ${str}`;
            } else {
                display = `= ${str}`;
            }
            parts.push(`${name} ${display}`);
        }
        return parts.join(", ") || "—";
    }
}
