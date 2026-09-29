/* Copyright 2024-2026 Rosen Vladimirov
   This file is available under a DUAL LICENSE: AGPL-3.0-or-later, or a
   commercial license from Rosen Vladimirov (see LICENSE-COMMERCIAL.md). */
// Кубчето на НОВ ред: офертата се записва, после се ражда партидата.
// Солид, 29.09: незаписаният ред пускаше onchange без поръчката и падаше в
// `_get_lang` с „Expected singleton: sale.order()“.
import { registry } from "@web/core/registry";

const ROW = ".o_field_one2many[name=order_line] .o_data_row";
const PRODUCT_INPUT = `${ROW} .o_field_widget[name=product_template_id] input, ${ROW} .o_field_widget[name=product_id] input`;

registry.category("web_tour.tours").add("sale_design_configurator_cube_new_line", {
    steps: () => [
        {
            content: "Add a line",
            trigger: ".o_field_one2many[name=order_line] .o_field_x2many_list_row_add a",
            run: "click",
        },
        {
            content: "Type the door",
            trigger: PRODUCT_INPUT,
            run: "edit DLC Cube Door",
        },
        {
            content: "Pick the door",
            trigger: ".o-autocomplete--dropdown-item:contains('DLC Cube Door')",
            run: "click",
        },
        {
            content: "The cube is on the new line",
            trigger: `${ROW} button[title='Configure Design']`,
            run: "click",
        },
        {
            content: "The configurator is open — create the lot",
            trigger: ".modal button.btn-primary:contains('Create Design Lot'):enabled",
            run: "click",
        },
        {
            content: "The dialog closes and the line shows its lot",
            trigger: `body:not(:has(.modal)) ${ROW} td[name=design_lot_id]:contains('DLC-CUBE')`,
        },
    ],
});
