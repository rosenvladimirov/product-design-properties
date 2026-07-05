/** @odoo-module **/
// Copyright 2026 BL Consulting
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { RuleMatrixPreview } from "../rule_matrix_preview/rule_matrix_preview";
import { coerceTable } from "../rule_matrix_preview/t0_evaluate";

/**
 * MatrixPreviewDialog — simulate matrix evaluation on a BoM.
 *
 * Opens from a button on the BoM form. Left panel has param controls,
 * right panel shows RuleMatrixPreview with T0/T1/T2/T3 sections.
 */
export class MatrixPreviewDialog extends Component {
    static components = { Dialog, RuleMatrixPreview };
    static template = "mrp_design_matrix.MatrixPreviewDialog";

    static props = {
        bomId: { type: Number },
        close: { type: Function },
    };

    get dialogTitle() {
        return _t("Matrix Preview");
    }

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            paramDefinition: [],
            constraintTable: false,
            geometryTable: false,
            materialTable: false,
            operationTable: false,
            bomLines: [],
            // Counter incremented on every param change — passed as a prop
            // to RuleMatrixPreview so OWL detects a "new" prop value and
            // triggers a re-render even though the params object reference
            // itself hasn't changed (it's mutated in-place by useState).
            paramsVersion: 0,
        });
        this.params = useState({});
        this._load();
    }

    async _load() {
        // Load BoM with tables + definition link
        const [bom] = await this.orm.read("mrp.bom", [this.props.bomId], [
            "design_param_definition_id",
            "constraint_table",
            "geometry_table",
            "material_table",
            "operation_table",
        ]);
        if (!bom) {
            this.state.loading = false;
            return;
        }

        this.state.constraintTable = coerceTable(bom.constraint_table);
        this.state.geometryTable = coerceTable(bom.geometry_table);
        this.state.materialTable = coerceTable(bom.material_table);
        this.state.operationTable = coerceTable(bom.operation_table);

        // Load param definition
        if (bom.design_param_definition_id) {
            const defId = bom.design_param_definition_id[0];
            const [def] = await this.orm.read(
                "design.param.definition", [defId],
                ["full_design_params_definition"]
            );
            if (def) {
                this.state.paramDefinition = def.full_design_params_definition || [];
                this._initParams(this.state.paramDefinition);
            }
        }

        // Load BoM lines
        const lines = await this.orm.searchRead(
            "mrp.bom.line",
            [["bom_id", "=", this.props.bomId]],
            ["product_id", "product_qty", "coeff_default", "matrix_coeff_rule"],
            { order: "sequence, id" }
        );
        this.state.bomLines = lines.map(l => ({
            product_id: l.product_id[0],
            product_name: l.product_id[1],
            product_qty: l.product_qty,
            coeff_default: l.coeff_default,
            matrix_coeff_rule: l.matrix_coeff_rule || "",
        }));

        this.state.loading = false;
    }

    _initParams(definition) {
        for (const prop of definition || []) {
            // Use prop.string (field name like "bag_type") as key, not
            // prop.name (UUID like "60cc0f08b68bc070").  The JDM table
            // inputs/outputs use field names, so the params dict must
            // match for RuleMatrixPreview evaluation to find the values.
            const key = prop.string || prop.name;
            if (prop.type === "boolean") {
                this.params[key] = prop.default === "true" || prop.default === true;
            } else if (prop.type === "float") {
                this.params[key] = parseFloat(prop.default) || 0;
            } else if (prop.type === "selection" && prop.selection?.length) {
                this.params[key] = prop.default || prop.selection[0][0];
            } else {
                this.params[key] = prop.default || "";
            }
        }
    }

    // ── Param display ──────────────────────────────────────────────────

    get displayParams() {
        return (this.state.paramDefinition || []).map(p => ({
            ...p,
            // Use string (field name) as the key for params lookup
            key: p.string || p.name,
            value: this.params[p.string || p.name],
        }));
    }

    // ── Event handlers ─────────────────────────────────────────────────

    _bumpVersion() {
        this.state.paramsVersion++;
    }

    onSliderInput(ev) {
        this.params[ev.target.dataset.param] = parseFloat(ev.target.value) || 0;
        this._bumpVersion();
    }

    onSegmentClick(ev) {
        this.params[ev.target.dataset.param] = ev.target.dataset.value;
        this._bumpVersion();
    }

    onCheckChange(ev) {
        this.params[ev.target.dataset.param] = ev.target.checked;
        this._bumpVersion();
    }

    onTextChange(ev) {
        this.params[ev.target.dataset.param] = ev.target.value;
        this._bumpVersion();
    }

    onSpinnerInput(ev) {
        this.params[ev.target.dataset.param] = parseFloat(ev.target.value) || 0;
    }
}
