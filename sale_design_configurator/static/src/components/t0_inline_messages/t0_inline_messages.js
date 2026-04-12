/** @odoo-module **/
// Copyright 2026 BL Consulting
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import { Component, onMounted, onWillUpdateProps, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { evaluateT0 } from "@mrp_design_matrix/components/rule_matrix_preview/t0_evaluate";

/**
 * T0InlineMessages -- compact T0 constraint messages on SO line.
 *
 * Registered as a view widget. When a design_lot_id is set on the
 * SO line, loads the lot's params and the BoM's constraint_table
 * via RPC and evaluates T0 client-side, showing matched errors and
 * warnings inline.
 */
export class T0InlineMessages extends Component {
    static template = "sale_design_configurator.T0InlineMessages";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: false,
            results: null,
        });
        onMounted(() => this._loadIfNeeded());
        onWillUpdateProps(() => this._loadIfNeeded());
    }

    get lotId() {
        const raw = this.props.record.data.design_lot_id;
        if (!raw) return false;
        return Array.isArray(raw) ? raw[0] : (raw.id || raw);
    }

    get hasMessages() {
        return this.state.results && this.state.results.length > 0;
    }

    async _loadIfNeeded() {
        if (!this.lotId) {
            this.state.results = null;
            return;
        }
        const lineId = this.props.record.resId;
        if (!lineId) return;

        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "sale.order.line",
                "get_t0_validation_data",
                [[lineId]]
            );
            if (!data) {
                this.state.results = null;
            } else {
                const t0 = evaluateT0(data.params, data.constraintTable);
                // Keep only matched errors and warnings
                this.state.results = t0
                    ? t0.results.filter(r => r.matched && r.level !== "ok")
                    : null;
            }
        } catch {
            this.state.results = null;
        }
        this.state.loading = false;
    }
}

registry.category("view_widgets").add("t0_inline_messages", {
    component: T0InlineMessages,
});
