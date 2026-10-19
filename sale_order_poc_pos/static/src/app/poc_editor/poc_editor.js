import { Component, markup, useEffect, useState } from "@odoo/owl";
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
            reports: {},
        });
        useEffect(
            (uuid, eligible) => {
                if (uuid !== this.state.uuid) {
                    this.state.uuid = uuid;
                    this.state.dismissed = false;
                    this.state.data = null;
                    this.state.updates = {};
                    this.state.reports = {};
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
                (line.product_id?.product_tmpl_id?.l10n_bg_pos_has_poc ||
                    this.standardLines.has(line.uuid)) &&
                this.order.getPartner()
        );
    }

    /**
     * Редовете, на които е избран готов продукт: артикулът им вече няма
     * шаблон, но конфигурацията е на същия ред — редакторът се отваря, за да
     * може да се върне изделието (ADR sale-order-poc/0027). Помни се за сесията.
     */
    get standardLines() {
        this.pos.l10nBgPocStandardLines ??= new Set();
        return this.pos.l10nBgPocStandardLines;
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
                await this._applyProduct(result.poc);
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
            // справките са по старите стойности — смятат се отново при поискване
            this.state.reports = {};
            await this._applyProduct(result);
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

    /**
     * Артикулът на реда в офертата → редът в касата: избраният готов продукт
     * или пак изделието. Иначе следващото запазване на офертата би върнало
     * артикула от касата.
     */
    async _applyProduct(data) {
        const line = this.order?.lines.find((l) => l.uuid === data.line.uuid);
        if (!line || !data.line.product_id) {
            return;
        }
        if (data.standard?.value) {
            this.standardLines.add(line.uuid);
        } else {
            this.standardLines.delete(line.uuid);
        }
        if (line.product_id?.id === data.line.product_id) {
            return;
        }
        const Product = this.pos.models["product.product"];
        if (!Product.get(data.line.product_id)) {
            await this.pos.loadNewProducts([["id", "in", [data.line.product_tmpl_id]]]);
        }
        const product = Product.get(data.line.product_id);
        if (product) {
            line.product_id = product;
            line.setFullProductName();
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
        if (param.readonly) {
            return;
        }
        this.state.updates[param.code] = value;
        this.schedulePicture();
    }

    /**
     * Визуализацията следва въвежданото веднага (Росен, 16.10.2026: „не
     * сменя картинката“): 0,4 s след последната промяна сървърът я рисува
     * с незаписаните стойности, без да пише нищо.
     */
    schedulePicture() {
        if (!this.state.data?.picture) {
            return;
        }
        clearTimeout(this._pictureTimer);
        this._pictureTimer = setTimeout(() => this.refreshPicture(), 400);
    }

    async refreshPicture() {
        const data = this.state.data;
        if (!data) {
            return;
        }
        const updates = { ...this.state.updates };
        delete updates.__fields;
        try {
            const picture = await this.pos.data.call("pos.config", "l10n_bg_poc_picture", [
                [this.pos.config.id],
                data.id,
                updates,
            ]);
            if (this.state.data === data && picture) {
                data.picture = picture;
            }
        } catch {
            // рисунката е помощ, не пречи на въвеждането
        }
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

    // ── готовият продукт вместо изделието (ADR sale-order-poc/0027) ──

    get standardValue() {
        return this.state.data?.standard?.value || false;
    }

    /** Изборът сменя реда веднага — запазва се с всичко въведено досега. */
    async chooseStandard(id) {
        if (!this.state.data?.editable || this.state.loading) {
            return;
        }
        this.state.updates.__standard = id || false;
        await this.compute();
    }

    // ── групите полета извън параметрите (тиражи, сравнение…) ──────

    fieldValue(field) {
        const updates = this.state.updates.__fields || {};
        return field.name in updates ? updates[field.name] : field.value;
    }

    setField(field, value) {
        this.state.updates.__fields = { ...(this.state.updates.__fields || {}), [field.name]: value };
    }

    onFieldNumber(field, ev) {
        const raw = ev.target.value;
        const value = raw === "" ? 0 : field.type === "integer" ? parseInt(raw) : parseFloat(raw);
        this.setField(field, Number.isNaN(value) ? 0 : value);
    }

    /** Групите, които стоят в секцията под параметъра ``code``. */
    anchoredGroups(code) {
        return (this.state.data?.field_groups || []).filter((group) => group.anchor === code);
    }

    /**
     * Картите в реда на екрана, с номер: секциите (изключената — само със
     * заглавието) и групите-карти — преди секцията на своя ``before``
     * или накрая. Номерът е на видимите карти, както в макета.
     */
    get cards() {
        const data = this.state.data;
        if (!data) {
            return [];
        }
        // група с котва, чийто параметър го няма в шаблона — своя карта
        const shown = new Set(data.sections.flatMap((section) => section.params.map((param) => param.code)));
        const own = (data.field_groups || []).filter((group) => !group.anchor || !shown.has(group.anchor));
        const placed = new Set();
        const cards = [];
        data.sections.forEach((section, index) => {
            const codes = new Set(section.params.map((param) => param.code));
            if (section.switch) {
                codes.add(section.switch.code);
            }
            for (const group of own) {
                if (!placed.has(group.key) && codes.has(group.before)) {
                    placed.add(group.key);
                    cards.push({ key: `group-${group.key}`, group });
                }
            }
            // изключената секция остава като заглавие с отметката си
            cards.push({ key: `section-${index}`, section, index });
        });
        for (const group of own) {
            if (!placed.has(group.key)) {
                cards.push({ key: `group-${group.key}`, group });
            }
        }
        return cards.map((card, position) => ({ ...card, number: position + 1 }));
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

    /** Справката (напр. „Офертни варианти“) — при натискане, бавна е. */
    async loadReport(report) {
        const data = this.state.data;
        this.state.reports[report.key] = { loading: true };
        try {
            const result = await this.pos.data.call("pos.config", "l10n_bg_poc_report", [
                [this.pos.config.id],
                data.id,
                report.key,
            ]);
            this.state.reports[report.key] = { result };
        } catch (error) {
            this.state.reports[report.key] = {};
            this.notification.add(error?.data?.message || error?.message || String(error), {
                type: "danger",
            });
        }
    }

    /** Картинката като SVG — от сървъра (схемата на вида изделие). */
    get pictureMarkup() {
        return markup(this.state.data?.picture?.svg || "");
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
