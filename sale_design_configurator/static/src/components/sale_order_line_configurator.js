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
import { useService } from "@web/core/utils/hooks";
import { DesignConfiguratorDialog } from "./design_configurator/design_configurator_dialog";

// -- Auto-open on product change in SO line list ----------------------------

import { SaleOrderLineProductField } from "@sale/js/sale_product_field";

patch(SaleOrderLineProductField.prototype, {
    setup() {
        super.setup(...arguments);
        this.dialogService = useService("dialog");
    },

    async _onProductUpdate() {
        await super._onProductUpdate(...arguments);

        const productId = this.props.record.data.product_id?.[0];
        if (!productId) return;

        const result = await this.orm.call(
            "sale.order.line",
            "get_design_definition_for_product",
            [productId]
        );

        if (!result || !result.definitionId) return;

        const lineId = this.props.record.resId;
        if (!lineId) {
            this.notification.add(
                "Save the line before configuring the design.",
                { type: "info" }
            );
            return;
        }

        // Open as dialog overlay (SO form stays visible behind)
        this.dialogService.add(DesignConfiguratorDialog, {
            productId: productId,
            definitionId: result.definitionId,
            existingLotId: false,
            onLotCreated: async (lotId, lotParams) => {
                await this.orm.call("sale.order.line", "set_design_lot", [
                    [lineId],
                    lotId,
                ]);
                // Reload the SO line to show the lot badge
                await this.props.record.load();
            },
        });
    },
});
