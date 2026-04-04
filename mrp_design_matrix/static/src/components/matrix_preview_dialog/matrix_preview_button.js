/** @odoo-module **/
// Copyright 2026 BL Consulting
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { MatrixPreviewDialog } from "./matrix_preview_dialog";

/**
 * MatrixPreviewButton — a widget field that renders as a smart button
 * on the BoM form. Clicking it opens the MatrixPreviewDialog.
 *
 * Usage in XML:
 *   <field name="id" widget="matrix_preview_button" invisible="not constraint_table"/>
 */
export class MatrixPreviewButton extends Component {
    static template = "mrp_design_matrix.MatrixPreviewButton";
    static props = { ...standardFieldProps };

    setup() {
        this.dialog = useService("dialog");
    }

    get bomId() {
        return this.props.record.data.id;
    }

    get hasMatrix() {
        const d = this.props.record.data;
        return !!(d.constraint_table || d.geometry_table || d.material_table || d.operation_table);
    }

    get ruleCount() {
        let count = 0;
        for (const field of ["constraint_table", "geometry_table", "material_table", "operation_table"]) {
            const table = this.props.record.data[field];
            if (!table) continue;
            const content = table.nodes?.[0]?.content || table.content;
            if (content?.rules) count += content.rules.length;
        }
        return count;
    }

    onClick() {
        this.dialog.add(MatrixPreviewDialog, { bomId: this.bomId });
    }
}

export const matrixPreviewButton = {
    component: MatrixPreviewButton,
    displayName: "Matrix Preview Button",
    supportedTypes: ["integer"],
    extractProps: () => ({}),
};

registry.category("fields").add("matrix_preview_button", matrixPreviewButton);
