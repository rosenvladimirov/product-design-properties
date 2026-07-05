/** @odoo-module **/
// Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

/**
 * Registers the "design_configurator_action" client action tag.
 * Triggered by action_open_design_configurator() Python methods.
 *
 * When the lot is created/updated it:
 *   1. Links it to the MO (lot_producing_ids) if moId is present.
 *   2. Links it to the SO line (design_lot_id) if solId is present.
 *   3. Refreshes the current view.
 */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { browser } from "@web/core/browser/browser";
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
            level: params.level || "",

            onLotCreated: async (lotId, lotParams) => {
                if (params.moId) {
                    // Odoo 19: lot_producing_ids (M2M, мн.ч.) — старото singular
                    // lot_producing_id не съществува → write гърмеше при MO link.
                    // (6,0,[id]) = replace: design MO има точно ЕДИН producing
                    // лот; (4) би акумулирал втори при повторно конфигуриране.
                    await this.orm.write("mrp.production", [params.moId], {
                        lot_producing_ids: [[6, 0, [lotId]]],
                    });
                }
                if (params.solId) {
                    await this.orm.call("sale.order.line", "set_design_lot", [
                        [params.solId],
                        lotId,
                    ]);
                }
            },
        }, {
            onClose: () => {
                // Client action-ът зае breadcrumb-а (замени kanban/form). При
                // затваряне на диалога act_window_close оставяше празен екран
                // (изчезваха и менютата). Връщаме се с пълна навигация назад към
                // предходния изглед (kanban/form), който се презарежда (вкл.
                // преместен лот между колоните).
                browser.history.back();
            },
        });
    }
}

registry
    .category("actions")
    .add("design_configurator_action", DesignConfiguratorAction);
