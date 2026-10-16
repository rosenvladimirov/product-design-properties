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

// Допълнителният ред на конфигурацията (сито, дръжки…) се появява в касата
registry.category("web_tour.tours").add("sale_order_poc_pos_companion", {
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
                content: "the editor opens",
                trigger: ".o_l10n_bg_poc_editor .o_l10n_bg_poc_title:contains('Configured Bag')",
            },
            {
                content: "no fee before Compute",
                trigger: "body:not(:has(.orderline:contains('Setup Fee (test)')))",
            },
            {
                content: "width 350 — the configuration now wants the fee",
                trigger: `${PARAM("pos_width_mm")} input`,
                run: "edit 350",
            },
            {
                content: "save and compute",
                trigger: ".o_l10n_bg_poc_compute:enabled",
                run: "click",
            },
            {
                content: "the fee line is in the order",
                trigger: ".orderline:contains('Setup Fee (test)')",
            },
            {
                content: "the configured line stays selected — the editor is still open",
                trigger: ".orderline.selected:contains('Configured Bag')",
            },
            {
                content: "the editor did not close",
                trigger: ".o_l10n_bg_poc_editor .o_l10n_bg_poc_title:contains('Configured Bag')",
            },
        ].flat(),
});

// Превключвателят на секцията горе и опционалните продукти (Росен, 15.10.2026)
registry.category("web_tour.tours").add("sale_order_poc_pos_switch", {
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
                content: "the switch is in the header of its card",
                trigger: ".o_l10n_bg_poc_editor .o_l10n_bg_poc_card[data-section='Print'] .o_l10n_bg_poc_switch[data-code='pos_print']",
            },
            {
                content: "the switched-off section is only its header",
                trigger: ".o_l10n_bg_poc_card[data-section='Print']:not(:has(.o_l10n_bg_poc_param))",
            },
            {
                content: "switch the print on",
                trigger: ".o_l10n_bg_poc_switch[data-code='pos_print']",
                run: "click",
            },
            {
                content: "the section shows",
                trigger: ".o_l10n_bg_poc_card[data-section='Print'] " + PARAM("pos_colours").replace(".o_l10n_bg_poc_editor ", "") + " input",
                run: "edit 2",
            },
            {
                content: "choose the optional product",
                trigger: ".o_l10n_bg_poc_optional_option:contains('Ribbon (test)')",
                run: "click",
            },
            {
                content: "save and compute",
                trigger: ".o_l10n_bg_poc_compute:enabled",
                run: "click",
            },
            {
                content: "the optional product is a line in the order",
                trigger: ".orderline:contains('Ribbon (test)')",
            },
        ].flat(),
});
