/** @odoo-module **/
// Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

/**
 * DesignConfiguratorDialog
 * ------------------------
 * Wraps DesignConfiguratorWidget in an Odoo dialog.
 * Called from the "Configure Design" button on sale.order.line,
 * mrp.production or stock.lot.
 *
 * Usage from another component or action:
 *
 *   this.dialog.add(DesignConfiguratorDialog, {
 *       productId:    this.productId,
 *       definitionId: this.definitionId,
 *       onLotCreated: (lotId, params) => { ... },
 *   });
 */

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { DesignConfiguratorWidget } from "./design_configurator";

export class DesignConfiguratorDialog extends Component {
    static components = { Dialog, DesignConfiguratorWidget };
    static template = "sale_design_configurator.DesignConfiguratorDialog";

    static props = {
        productId: { type: Number },
        definitionId: { type: Number },
        existingLotId: { type: [Number, Boolean], optional: true },
        onLotCreated: { type: Function, optional: true },
        close: { type: Function }, // injected by Dialog service
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            definitionCode: "",
            paramDefinition: [],
        });
        this._loadDefinition();
    }

    async _loadDefinition() {
        const [def] = await this.orm.read(
            "design.param.definition",
            [this.props.definitionId],
            ["code", "design_params_definition"]
        );
        if (def) {
            this.state.definitionCode = def.code;
            this.state.paramDefinition = def.design_params_definition || [];
        }
        this.state.loading = false;
    }

    onLotCreated(lotId, params) {
        if (this.props.onLotCreated) {
            this.props.onLotCreated(lotId, params);
        }
        this.props.close();
    }

    onClose() {
        this.props.close();
    }
}
