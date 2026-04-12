/** @odoo-module **/
// Copyright 2026 BL Consulting
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import { Component } from "@odoo/owl";

import {
    evaluateT0,
    getTableContent,
    evaluateRule,
    extractOutput,
    decodeJDMValue,
    buildRuleDescription,
} from "./t0_evaluate";

/**
 * RuleMatrixPreview -- real-time constraint evaluation display.
 *
 * Shows real-time evaluation of GoRules DMN matrix tables against
 * a set of design parameters. Used in BoM preview and SO configurator.
 *
 * T0: Constraints -- real-time rule match with error/warning/ok.
 * T1: Geometry -- computed values from geometry_table.
 * T2: Materials -- BoM composition with qty x coeff = final.
 * T3: Operations -- conditional workorder cards.
 */
export class RuleMatrixPreview extends Component {
    static template = "mrp_design_matrix.RuleMatrixPreview";

    static props = {
        params: { type: Object },
        paramsVersion: { type: Number, optional: true },
        constraintTable: { type: [Object, { value: false }], optional: true },
        geometryTable: { type: [Object, { value: false }], optional: true },
        materialTable: { type: [Object, { value: false }], optional: true },
        operationTable: { type: [Object, { value: false }], optional: true },
        bomLines: { type: Array, optional: true },
    };

    // -- T0: Constraint evaluation (delegated to shared utility) ----------

    get t0() {
        return evaluateT0(this.props.params, this.props.constraintTable);
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

    // -- T1: Geometry evaluation ------------------------------------------

    get t1() {
        const table = getTableContent(this.props.geometryTable);
        if (!table) return null;

        const inputs = table.inputs || [];
        const outputs = table.outputs || [];
        const rules = table.rules || [];
        const hitPolicy = table.hitPolicy || "first";

        const values = {};
        for (const rule of rules) {
            const matched = evaluateRule(rule, this.props.params, inputs);
            if (!matched) continue;

            for (const out of outputs) {
                const raw = rule[out.id];
                if (!raw && raw !== 0 && raw !== false) continue;
                const val = decodeJDMValue(raw);
                if (hitPolicy === "first" && !(out.id in values)) {
                    values[out.id] = { name: out.name || out.id, value: val };
                } else if (hitPolicy === "collect") {
                    values[out.id] = { name: out.name || out.id, value: val };
                }
            }
            if (hitPolicy === "first" && Object.keys(values).length === outputs.length) {
                break;
            }
        }

        const entries = Object.values(values);
        return entries.length ? entries : null;
    }

    get hasT1() {
        return this.t1 !== null;
    }

    // -- T2: Materials / BoM composition ----------------------------------

    get t2() {
        const bomLines = this.props.bomLines || [];
        if (!bomLines.length) return null;

        const table = getTableContent(this.props.materialTable);
        const tableInputs = table ? (table.inputs || []) : [];
        const tableRules = table ? (table.rules || []) : [];
        const tableOutputs = table ? (table.outputs || []) : [];

        const lines = [];
        for (const line of bomLines) {
            const baseQty = line.product_qty || 0;
            let coeff = line.coeff_default !== undefined ? line.coeff_default : 1.0;
            let coeffSource = "default";

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
     */
    _findMatrixCoeff(coeffKey, rules, inputs, outputs) {
        const coeffOut = outputs.find(o => o.id === coeffKey);
        if (!coeffOut) return null;

        for (const rule of rules) {
            const matched = evaluateRule(rule, this.props.params, inputs);
            if (!matched) continue;
            const raw = rule[coeffOut.id];
            if (raw === undefined || raw === null || raw === "") continue;
            const val = parseFloat(decodeJDMValue(raw));
            if (!isNaN(val)) return val;
        }
        return null;
    }

    // -- T3: Operations evaluation ----------------------------------------

    get t3() {
        const table = getTableContent(this.props.operationTable);
        if (!table) return null;

        const inputs = table.inputs || [];
        const outputs = table.outputs || [];
        const rules = table.rules || [];

        const ops = [];
        for (const rule of rules) {
            const matched = evaluateRule(rule, this.props.params, inputs);
            const opName = extractOutput(rule, outputs, "operation")
                        || extractOutput(rule, outputs, "name")
                        || buildRuleDescription(rule, inputs);
            const duration = extractOutput(rule, outputs, "duration");
            const workcenter = extractOutput(rule, outputs, "workcenter");

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
}
