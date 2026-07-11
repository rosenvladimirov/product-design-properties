/** @odoo-module **/
// Copyright 2026 Rosen Vladimirov / Terraros Commerce Ltd.
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import { Component, onMounted, onWillUpdateProps, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { RuleMatrixPreview } from "../rule_matrix_preview/rule_matrix_preview";
import { coerceTable } from "../rule_matrix_preview/t0_evaluate";

/**
 * InlineMatrixPreview -- embedded T0-T3 preview in the BoM form.
 *
 * Registered as a field widget on the ``id`` field (same pattern as
 * MatrixPreviewButton).  Reads matrix tables from the form record,
 * loads the param definition via ORM, and renders parameter controls
 * + RuleMatrixPreview inline in the Design Matrix tab.
 */
export class InlineMatrixPreview extends Component {
    static template = "mrp_design_matrix.InlineMatrixPreview";
    static components = { RuleMatrixPreview };
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            collapsed: false,
            paramDefinition: [],
            bomLines: [],
            paramsVersion: 0,
        });
        this.params = useState({});

        onMounted(() => this._load());
        onWillUpdateProps(() => {
            // Reload when record data changes (e.g. after Load from Template)
            this._load();
        });
    }

    // -- Data access from form record ------------------------------------

    get recordData() {
        return this.props.record.data;
    }

    get constraintTable() {
        return coerceTable(this.recordData.constraint_table);
    }

    get geometryTable() {
        return coerceTable(this.recordData.geometry_table);
    }

    get materialTable() {
        return coerceTable(this.recordData.material_table);
    }

    get operationTable() {
        return coerceTable(this.recordData.operation_table);
    }

    get hasMatrix() {
        return !!(this.constraintTable || this.geometryTable ||
                  this.materialTable || this.operationTable);
    }

    get bomId() {
        return this.recordData.id;
    }

    // -- Loading ---------------------------------------------------------

    async _load() {
        if (!this.hasMatrix) {
            this.state.loading = false;
            return;
        }

        // Load param definition for controls
        const defId = this.recordData.design_param_definition_id;
        if (defId) {
            const id = Array.isArray(defId) ? defId[0] : defId;
            try {
                const [def] = await this.orm.read(
                    "design.param.definition", [id],
                    ["full_design_params_definition"]
                );
                if (def) {
                    this.state.paramDefinition = def.full_design_params_definition || [];
                    this._initParams(this.state.paramDefinition);
                }
            } catch {
                this.state.paramDefinition = [];
            }
        }

        // Load BoM lines for T2
        if (this.bomId) {
            try {
                const lines = await this.orm.searchRead(
                    "mrp.bom.line",
                    [["bom_id", "=", this.bomId]],
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
            } catch {
                this.state.bomLines = [];
            }
        }

        this.state.loading = false;
    }

    _initParams(definition) {
        for (const prop of definition || []) {
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

    // -- Display ---------------------------------------------------------

    get displayParams() {
        return (this.state.paramDefinition || []).map(p => ({
            ...p,
            key: p.string || p.name,
            value: this.params[p.string || p.name],
        }));
    }

    // -- Event handlers --------------------------------------------------

    toggleCollapsed() {
        this.state.collapsed = !this.state.collapsed;
    }

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
        this._bumpVersion();
    }
}

const inlineMatrixPreview = {
    component: InlineMatrixPreview,
    displayName: "Matrix Inline Preview",
    supportedTypes: ["integer"],
    extractProps: () => ({}),
};

registry.category("fields").add("matrix_inline_preview", inlineMatrixPreview);
