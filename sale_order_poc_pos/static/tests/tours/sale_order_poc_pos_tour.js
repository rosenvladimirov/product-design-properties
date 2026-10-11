/**
 * Тур: тъч редакторът на конфигурацията (POC) на ред на едро в касата
 * (ADR pos-b2b-wholesale/0004).
 */
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import { registry } from "@web/core/registry";

const PARAM = (code) => `.o_l10n_bg_poc_editor .o_l10n_bg_poc_param[data-code='${code}']`;

registry.category("web_tour.tours").add("sale_order_poc_pos_editor", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            {
                content: "switch to Wholesale",
                trigger: ".control-buttons .o_l10n_bg_wholesale_button",
                run: "click",
            },
            ProductScreen.clickPartnerButton(),
            ProductScreen.clickCustomer("ET Petrov Trade"),
            ProductScreen.clickDisplayedProduct("Configured Bag"),
            {
                // добавеният ред е избран — второ натискане би махнало избора
                content: "the configured line is selected",
                trigger: ".orderline.selected:contains('Configured Bag')",
            },
            {
                content: "the editor opens in the right pane",
                trigger: ".o_l10n_bg_poc_editor .o_l10n_bg_poc_title:contains('Configured Bag')",
            },
            {
                content: "width 350",
                trigger: `${PARAM("pos_width_mm")} input`,
                run: "edit 350",
            },
            {
                content: "material HDPE",
                trigger: `${PARAM("pos_material")} .o_l10n_bg_poc_option[data-key='hdpe']`,
                run: "click",
            },
            {
                content: "save and compute",
                trigger: ".o_l10n_bg_poc_compute:enabled",
                run: "click",
            },
            {
                content: "the formula is computed",
                trigger: `${PARAM("pos_double_mm")} input:value(700)`,
            },
            {
                content: "close the editor",
                trigger: ".o_l10n_bg_poc_close",
                run: "click",
            },
            {
                content: "the products are back",
                trigger: "body:not(:has(.o_l10n_bg_poc_editor))",
            },
        ].flat(),
});
