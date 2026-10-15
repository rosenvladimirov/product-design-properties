import { Component, useEffect, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";

/**
 * Тъч редакторът на конфигурацията (POC) на ред на едро — в десния екран
 * на касата. Отваря се, когато в „Редове“ стъпиш на ред с продукт, който
 * има шаблон за конфигурация; офертата се запазва сама
 * (ADR pos-b2b-wholesale/0004).
 */
export class L10nBgPocEditor extends Component {
    static template = "sale_order_poc_pos.PocEditor";
    static props = { fullscreen: { type: Boolean, optional: true } };

    setup() {
        this.pos = usePos();
        this.notification = useService("notification");
        this.state = useState({
            uuid: false,
            dismissed: false,
            loading: false,
            data: null,
            updates: {},
            open: {},
        });
        useEffect(
            (uuid, eligible) => {
                if (uuid !== this.state.uuid) {
                    this.state.uuid = uuid;
                    this.state.dismissed = false;
                    this.state.data = null;
                    this.state.updates = {};
                    if (uuid && eligible) {
                        this.load();
                    }
                }
            },
            () => [this.selectedLine?.uuid || false, this.eligible]
        );
    }

    get order() {
        return this.pos.getOrder();
    }

    get selectedLine() {
        const order = this.order;
        if (!order?.l10n_bg_wholesale || order.l10nBgPanel !== "lines") {
            return null;
        }
        return order.getSelectedOrderline() || null;
    }

    get eligible() {
        const line = this.selectedLine;
        return Boolean(
            line &&
                !line.combo_parent_id &&
                line.product_id?.product_tmpl_id?.l10n_bg_pos_has_poc &&
                this.order.getPartner()
        );
    }

    get visible() {
        return this.eligible && !this.state.dismissed;
    }

    get dirty() {
        return Object.keys(this.state.updates).length > 0;
    }

    async load() {
        const order = this.order;
        const uuid = this.state.uuid;
        this.state.loading = true;
        try {
            const result = await this.pos.data.call("pos.config", "l10n_bg_poc_open", [
                [this.pos.config.id],
                order.l10nBgQuotationPayload(),
                uuid,
            ]);
            order.l10nBgApplyQuotation(result.quotation);
            if (this.state.uuid === uuid) {
                this.state.data = result.poc;
                this._applyPrice(result.poc);
                await this._applyCompanions(result.poc);
            }
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || String(error), {
                type: "danger",
            });
            this.state.dismissed = true;
        } finally {
            this.state.loading = false;
        }
    }

    async compute() {
        const data = this.state.data;
        if (!data) {
            return;
        }
        this.state.loading = true;
        try {
            const result = await this.pos.data.call("pos.config", "l10n_bg_poc_save", [
                [this.pos.config.id],
                data.id,
                this.state.updates,
            ]);
            this.state.data = result;
            this.state.updates = {};
            this._applyPrice(result);
            await this._applyCompanions(result);
        } catch (error) {
            this.notification.add(error?.data?.message || error?.message || String(error), {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    /** Цената от конфигурацията → редът в касата (не се пресмята повече). */
    _applyPrice(data) {
        const line = this.order?.lines.find((l) => l.uuid === data.line.uuid);
        if (line && data.line.price_unit) {
            line.setUnitPrice(data.line.price_unit);
            line.price_type = "manual";
        }
    }

    /**
     * Допълнителните редове на офертата (сито, дръжки…) → редове в касата.
     *
     * Ключът на реда в офертата е и uuid-ът му в касата: запазването на
     * офертата обновява СЪЩИЯ ред. Ред с началото на ключа на тази
     * конфигурация, който сървърът вече не връща, се маха. Артикул, който
     * касата не е заредила (не е „в касата“), се зарежда.
     */
    async _applyCompanions(data) {
        const order = this.order;
        if (!order || !data?.companions || !data.companion_prefix) {
            return;
        }
        const wanted = new Map(data.companions.map((c) => [c.uuid, c]));
        for (const line of [...order.lines]) {
            if (line.uuid?.startsWith(data.companion_prefix) && !wanted.has(line.uuid)) {
                order.removeOrderline(line);
            }
        }
        const Product = this.pos.models["product.product"];
        const missing = data.companions
            .filter((c) => !Product.get(c.product_id))
            .map((c) => c.product_tmpl_id);
        if (missing.length) {
            await this.pos.loadNewProducts([["id", "in", missing]]);
        }
        for (const companion of data.companions) {
            const line = order.lines.find((l) => l.uuid === companion.uuid);
            if (line) {
                line.setQuantity(companion.qty, true);
                line.setUnitPrice(companion.price_unit);
                line.price_type = "manual";
                continue;
            }
            const product = Product.get(companion.product_id);
            if (!product) {
                continue;
            }
            await this.pos.addLineToOrder(
                {
                    product_tmpl_id: product.product_tmpl_id,
                    product_id: product,
                    qty: companion.qty,
                    price_unit: companion.price_unit,
                    uuid: companion.uuid,
                },
                order,
                { merge: false },
                false
            );
        }
        // новият ред се избира сам — изборът се връща на реда с
        // конфигурацията, иначе редакторът би се затворил
        const main = order.lines.find((l) => l.uuid === data.line.uuid);
        if (main && order.getSelectedOrderline() !== main) {
            order.selectOrderline(main);
        }
    }

    close() {
        this.state.dismissed = true;
    }

    // ── стойности ────────────────────────────────────────────────────

    value(param) {
        return param.code in this.state.updates ? this.state.updates[param.code] : param.value;
    }

    set(param, value) {
        this.state.updates[param.code] = value;
    }

    onNumber(param, ev) {
        const raw = ev.target.value;
        const value = raw === "" ? null : param.type === "integer" ? parseInt(raw) : parseFloat(raw);
        this.set(param, Number.isNaN(value) ? null : value);
    }

    onText(param, ev) {
        this.set(param, ev.target.value || false);
    }

    onRecord(param, ev) {
        this.set(param, parseInt(ev.target.value) || false);
    }

    // ── превключвателите на секциите (напр. „С печат“) ──────────────

    /** Превключвателите — горе, до „Close“. */
    get switches() {
        return (this.state.data?.sections || []).filter((section) => section.switch);
    }

    /** Секция без превключвател се вижда винаги; с — само когато е „да“. */
    isSwitchedOn(section) {
        return !section.switch || Boolean(this.value(section.switch));
    }

    toggleSwitch(section) {
        this.set(section.switch, !this.isSwitchedOn(section));
    }

    // ── опционалните продукти на артикула ──────────────────────────

    get optionalValue() {
        return this.state.updates.__optional || this.state.data?.optional?.value || [];
    }

    toggleOptional(id) {
        const current = [...this.optionalValue];
        const index = current.indexOf(id);
        if (index >= 0) {
            current.splice(index, 1);
        } else {
            current.push(id);
        }
        this.state.updates.__optional = current;
    }

    /** „Цената тръгва от“ — не е параметър; пътува със същото „Запази“. */
    get priceBase() {
        return this.state.updates.__price_base || this.state.data?.price_base?.value;
    }

    setPriceBase(key) {
        this.state.updates.__price_base = key;
    }

    toggleTag(param, key) {
        const current = [...(this.value(param) || [])];
        const index = current.indexOf(key);
        if (index >= 0) {
            current.splice(index, 1);
        } else {
            current.push(key);
        }
        this.set(param, current);
    }

    isSectionOpen(section, index) {
        return index in this.state.open ? this.state.open[index] : !section.folded;
    }

    toggleSection(section, index) {
        this.state.open[index] = !this.isSectionOpen(section, index);
    }

    formatCurrency(amount) {
        return this.env.utils.formatCurrency(amount || 0);
    }

    get title() {
        return this.state.data ? `${this.state.data.name} · ${this.state.data.line.product}` : _t("Configuration");
    }
}

patch(ProductScreen, {
    components: { ...ProductScreen.components, L10nBgPocEditor },
});
