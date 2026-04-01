/** @odoo-module **/
// Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

/**
 * SaleOrderLineConfigurator
 * -------------------------
 * 1. Auto-open the Design Configurator dialog when a product with a
 *    design definition is selected on a new SO line.
 * 2. Provide a view widget (fa-cube button) that opens the dialog
 *    directly without leaving the SO form.
 */

import { Component } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { DesignConfiguratorDialog } from "./design_configurator/design_configurator_dialog";

// ── Helper: open configurator dialog on an SO line ─────────────────────

// Many2one value → ID (handles both list [id,"name"] and form proxy)
function m2oId(val) {
    if (!val) return false;
    if (Array.isArray(val)) return val[0];
    if (typeof val === "object") return val.resId || val.id || false;
    return val;
}

function openDesignConfigurator(dialogService, orm, record, productId, definitionId, existingLotId) {
    const lineId = record.resId;
    dialogService.add(DesignConfiguratorDialog, {
        productId,
        definitionId,
        existingLotId: existingLotId || false,
        onLotCreated: async (lotId) => {
            await orm.call("sale.order.line", "set_design_lot", [[lineId], lotId]);
            await record.load();
        },
    });
}

// ── Auto-open on product change ────────────────────────────────────────

import { SaleOrderLineProductField } from "@sale/js/sale_product_field";

patch(SaleOrderLineProductField.prototype, {
    setup() {
        super.setup(...arguments);
        this.dialogService = useService("dialog");
    },

    async _onProductUpdate() {
        await super._onProductUpdate(...arguments);

        const productId = m2oId(this.props.record.data.product_id);
        if (!productId) return;

        const result = await this.orm.call(
            "sale.order.line",
            "get_design_definition_for_product",
            [productId]
        );
        if (!result || !result.definitionId) return;

        if (!this.props.record.resId) {
            this.notification.add(
                "Save the line before configuring the design.",
                { type: "info" }
            );
            return;
        }

        openDesignConfigurator(
            this.dialogService, this.orm, this.props.record,
            productId, result.definitionId, false
        );
    },
});

// ── View widget: Configure Design button (replaces type=object btn) ────

export class DesignConfiguratorOpenWidget extends Component {
    static template = "sale_design_configurator.OpenWidget";
    static props = ["*"];

    setup() {
        this.dialogService = useService("dialog");
        this.orm = useService("orm");
    }

    onClick() {
        const record = this.props.record;
        const model = record.resModel;
        let productId, defId, lotId;

        if (model === "stock.lot") {
            productId = m2oId(record.data.product_id);
            defId = m2oId(record.data.design_param_definition_id);
            lotId = record.resId;
        } else if (model === "product.product") {
            productId = record.resId;
            defId = m2oId(record.data.design_param_definition_id);
            lotId = false;
        } else if (model === "product.template") {
            productId = m2oId(record.data.product_variant_id);
            defId = m2oId(record.data.design_param_definition_id);
            lotId = false;
        } else {
            productId = m2oId(record.data.product_id);
            defId = m2oId(record.data.design_param_definition_id);
            lotId = m2oId(record.data.design_lot_id);
        }

        if (!productId || !defId) return;

        if (model === "product.product" || model === "product.template") {
            // Preview only — no lot creation callback
            this.dialogService.add(DesignConfiguratorDialog, {
                productId,
                definitionId: defId,
                existingLotId: false,
            });
            return;
        }

        openDesignConfigurator(
            this.dialogService, this.orm, record,
            productId, defId, lotId
        );
    }
}

registry.category("view_widgets").add("design_configurator_open", {
    component: DesignConfiguratorOpenWidget,
});
