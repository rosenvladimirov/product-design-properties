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
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { evaluateBooleanExpr } from "@web/core/py_js/py";
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

/**
 * Редът трябва да е записан, преди да се роди партида за него.
 *
 * Нов ред (или нова оферта) няма id: `set_design_lot` получаваше празен
 * списък, а `record.load()` пускаше onchange на реда БЕЗ поръчката и падаше
 * в `_get_lang` с „Expected singleton: sale.order()“ (Солид, 29.09). Затова
 * офертата се записва първо. Записът пресъздава редовете на списъка — старият
 * обект вече не е редът, — затова записаният се намира по позицията си и се
 * сверява по продукта. Връща записания ред или null, ако записът не мина.
 */
async function savedSaleLine(record) {
    if (record.resId || record.resModel !== "sale.order.line") {
        return record;
    }
    const root = record.model.root;
    const lines = root.data.order_line;
    const index = lines ? lines.records.indexOf(record) : -1;
    const productId = m2oId(record.data.product_id);
    if (index < 0 || !(await root.save())) {
        return null;
    }
    const saved = root.data.order_line.records[index];
    if (!saved || !saved.resId || m2oId(saved.data.product_id) !== productId) {
        return null;
    }
    return saved;
}

async function openDesignConfigurator(dialogService, orm, record, productId, definitionId, existingLotId, notification) {
    record = await savedSaleLine(record);
    if (!record) {
        notification?.add(
            _t("Save the quotation before configuring the design."),
            { type: "warning" }
        );
        return;
    }
    const lineId = record.resId;
    // Записът прерисува редовете и унищожава уиджета, който е отворил
    // диалога — неговият `orm` (от useService) след това отказва с
    // „Component is destroyed“ и партидата остава без ред. Моделът живее.
    orm = record.model.orm || orm;
    dialogService.add(DesignConfiguratorDialog, {
        productId,
        definitionId,
        existingLotId: existingLotId || false,
        // редът стига до куката на вертикала: стойностите, които идват от
        // продажбата (конфигурацията на производството). Кубчето на реда
        // отваря диалога директно, не през action_open_design_configurator.
        solId: record.resModel === "sale.order.line" ? lineId : false,
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
        // autoOpen=false: вертикалът води реда по друг път (напр. POC на офертата)
        if (!result || !result.definitionId || result.autoOpen === false) return;

        if (!this.props.record.resId) {
            this.notification.add(
                _t("Save the line before configuring the design."),
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
        this.notification = useService("notification");
    }

    get isInvisible() {
        const expr = this.props.invisibleExpr;
        return Boolean(expr) && evaluateBooleanExpr(expr, this.props.record.evalContextWithVirtualIds);
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
            productId, defId, lotId, this.notification
        );
    }
}

registry.category("view_widgets").add("design_configurator_open", {
    component: DesignConfiguratorOpenWidget,
    // Списъкът на Odoo 19 НЕ смята `invisible` на <widget> клетка — рисува я
    // винаги (web/views/list/list_renderer.xml). Уиджетът го смята сам.
    extractProps: ({ attrs }) => ({ invisibleExpr: attrs.invisible || "" }),
});
