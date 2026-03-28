/** @odoo-module **/
// Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

/**
 * Registers the "design_configurator_action" client action tag.
 * Triggered by action_open_design_configurator() Python methods.
 *
 * When the lot is created/updated it:
 *   1. Links it to the MO (lot_producing_id) if moId is present.
 *   2. Links it to the SO line (design_lot_id) if solId is present.
 *   3. Refreshes the current view.
 */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, useRef } from "@odoo/owl";
import { DesignConfiguratorDialog } from "./design_configurator/design_configurator_dialog";

class DesignConfiguratorAction extends Component {
    static template = "sale_design_configurator.DesignConfiguratorAction";

    setup() {
        this.dialog = useService("dialog");
        this.orm = useService("orm");
        this.action = useService("action");
        this.rootRef = useRef("root");

        onMounted(() => {
            this.openDialog();
        });
    }

    async openDialog() {
        const params = this.props.action.params || {};

        this.dialog.add(DesignConfiguratorDialog, {
            productId: params.productId,
            definitionId: params.definitionId,
            existingLotId: params.existingLotId || false,

            onLotCreated: async (lotId, lotParams) => {
                // MO flow: link lot_producing_id
                if (params.moId) {
                    await this.orm.write("mrp.production", [params.moId], {
                        lot_producing_id: lotId,
                    });
                }

                // SO line flow: write design_lot_id back
                if (params.solId) {
                    await this.orm.call("sale.order.line", "set_design_lot", [
                        [params.solId],
                        lotId,
                    ]);
                    // Trigger reload of the SO form to show the lot badge
                    this.action.doAction(
                        { type: "ir.actions.act_window_close" },
                        { stackPosition: "replaceCurrentAction" }
                    );
                } else {
                    // Refresh the underlying view
                    this.action.doAction({
                        type: "ir.actions.act_window_close",
                    });
                }
            },
        });
    }
}

registry
    .category("actions")
    .add("design_configurator_action", DesignConfiguratorAction);
