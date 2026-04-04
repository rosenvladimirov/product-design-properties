/** @odoo-module **/
// Copyright 2026 BL Consulting
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { RuleMatrixPreview } from "../rule_matrix_preview/rule_matrix_preview";

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

        this.state.constraintTable = bom.constraint_table || false;
        this.state.geometryTable = bom.geometry_table || false;
        this.state.materialTable = bom.material_table || false;
        this.state.operationTable = bom.operation_table || false;

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
            if (prop.type === "boolean") {
                this.params[prop.name] = prop.default === "true" || prop.default === true;
            } else if (prop.type === "float") {
                this.params[prop.name] = parseFloat(prop.default) || 0;
            } else if (prop.type === "selection" && prop.selection?.length) {
                this.params[prop.name] = prop.default || prop.selection[0][0];
            } else {
                this.params[prop.name] = prop.default || "";
            }
        }
    }

    // ── Param display ──────────────────────────────────────────────────

    get displayParams() {
        return (this.state.paramDefinition || []).map(p => ({
            ...p,
            value: this.params[p.name],
        }));
    }

    // ── Event handlers ─────────────────────────────────────────────────

    onSliderInput(ev) {
        this.params[ev.target.dataset.param] = parseFloat(ev.target.value) || 0;
    }

    onSegmentClick(ev) {
        this.params[ev.target.dataset.param] = ev.target.dataset.value;
    }

    onCheckChange(ev) {
        this.params[ev.target.dataset.param] = ev.target.checked;
    }

    onTextChange(ev) {
        this.params[ev.target.dataset.param] = ev.target.value;
    }

    onSpinnerInput(ev) {
        this.params[ev.target.dataset.param] = parseFloat(ev.target.value) || 0;
    }
}
