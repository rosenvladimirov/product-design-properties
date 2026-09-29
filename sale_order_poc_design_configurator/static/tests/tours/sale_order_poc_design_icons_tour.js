/* Copyright 2024-2026 Rosen Vladimirov
   This file is available under a DUAL LICENSE: AGPL-3.0-or-later, or a
   commercial license from Rosen Vladimirov (see LICENSE-COMMERCIAL.md). */
// POC е за офертата, матрицата — за поръчката (ADR sale-order-poc/0019),
// и кубчето на потвърдената поръчка отваря фиксираната партида. Проверява се
// в браузъра: на 21.09 куката беше вързана за действие, през което кубчето
// изобщо не минава, а проверката по сървъра я показваше зелена.
import { registry } from "@web/core/registry";

const LINE = ".o_field_one2many[name=order_line] .o_data_row";
const SLIDERS = "button[name=action_open_poc]";
const CUBE = "button[title='Configure Design']";
// ширината — UUID-то на свойството в тестовата дефиниция
const WIDTH = "c0ffee0000000001";

registry.category("web_tour.tours").add("sale_order_poc_design_icons", {
    steps: () => [
        {
            content: "Quotation: the configuration icon is there",
            trigger: `${LINE} ${SLIDERS}`,
        },
        {
            content: "Quotation: no cube",
            trigger: `${LINE}:not(:has(${CUBE}))`,
        },
        {
            content: "Confirm the order",
            trigger: ".o_statusbar_buttons button[name=action_confirm]",
            run: "click",
        },
        {
            content: "Order: the cube is there",
            trigger: `${LINE} ${CUBE}`,
        },
        {
            content: "Order: no configuration icon",
            trigger: `${LINE}:not(:has(${SLIDERS}))`,
        },
        {
            content: "Open the configurator",
            trigger: `${LINE} ${CUBE}`,
            run: "click",
        },
        {
            // потвърдената поръчка има фиксирана дизайн партида — матрицата
            // чете от нея, не заключено от POC
            content: "The width comes from the fixed design lot",
            trigger: `.modal input[data-param='${WIDTH}']:not(:disabled):value(300)`,
        },
    ],
});
