import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";

/**
 * Ред на едро с продукт със шаблон за конфигурация: партидата идва от
 * конфигурацията (POC) при потвърждаване на поръчката, не от касата —
 * касата не пита за нея и не я брои за липсваща
 * (ADR pos-b2b-wholesale/0004).
 */
function l10nBgPocOwnsLot(order, product) {
    return Boolean(order?.l10n_bg_wholesale && product?.product_tmpl_id?.l10n_bg_pos_has_poc);
}

patch(PosStore.prototype, {
    async editLots(product, packLotLinesToEdit) {
        if (l10nBgPocOwnsLot(this.getOrder(), product)) {
            return { modifiedPackLotLines: {}, newPackLotLines: [] };
        }
        return await super.editLots(...arguments);
    },
});

patch(PosOrderline.prototype, {
    hasValidProductLot() {
        if (l10nBgPocOwnsLot(this.order_id, this.product_id)) {
            return true;
        }
        return super.hasValidProductLot(...arguments);
    },
});
