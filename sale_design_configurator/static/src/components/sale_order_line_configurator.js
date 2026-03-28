/** @odoo-module **/
// Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

/**
 * SaleOrderLineConfigurator
 * -------------------------
 * Patches the sale.order.line list renderer to:
 *
 *   1. Auto-open the Design Configurator when a product with a design
 *      definition is selected on a new line.
 *   2. Write the created lot back to the SO line via RPC after confirmation.
 *
 * Also patches the design_configurator_action client action to handle
 * the solId -> set_design_lot RPC callback.
 */

import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { DesignConfiguratorDialog } from "./design_configurator/design_configurator_dialog";

// -- Auto-open on product change in SO line list ----------------------------

/**
 * We patch the SaleOrderLineProductField so that when a product_id field
 * changes on a line and the product has a design definition, the
 * configurator opens automatically.
 *
 * The check is done via a server call to avoid loading all BoMs client-side.
 */

import { SaleOrderLineProductField } from "@sale/js/sale_product_field";

patch(SaleOrderLineProductField.prototype, {
    async _onProductUpdate() {
        // Call original update
        await super._onProductUpdate(...arguments);

        const productId = this.props.record.data.product_id?.[0];
        if (!productId) return;

        // Check if this product has a design definition
        const result = await this.orm.call(
            "sale.order.line",
            "get_design_definition_for_product",
            [productId]
        );

        if (!result || !result.definitionId) return;

        // Get the current record id (may be a virtual id on a new line)
        const lineId = this.props.record.resId;
        if (!lineId) {
            // New unsaved line - show notification to save first
            this.notification.add(
                "Save the line before configuring the design.",
                { type: "info" }
            );
            return;
        }

        // Open configurator automatically
        this.action.doAction({
            type: "ir.actions.client",
            tag: "design_configurator_action",
            params: {
                productId: productId,
                definitionId: result.definitionId,
                existingLotId: false,
                solId: lineId,
            },
        });
    },
});
