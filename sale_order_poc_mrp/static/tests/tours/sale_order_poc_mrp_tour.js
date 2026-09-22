/* Copyright 2026 Rosen Vladimirov

   This file is available under a DUAL LICENSE:
     1. GNU Lesser General Public License v3.0 or later (LGPL-3.0-or-later)
        https://www.gnu.org/licenses/lgpl-3.0.html
     2. A commercial license from Rosen Vladimirov, for use without the
        obligations of the LGPL. See LICENSE-COMMERCIAL.md.
        Contact: vladimirov.rosen@gmail.com

   Unless you hold a valid commercial license, your use of this file is
   governed by the LGPL-3.0-or-later.
*/
// Формата на MO с конфигурация: резюмето, отметнатите параметри във формата,
// параметрите само за четене и бутонът за преизчисляване (ADR
// sale-order-poc/0008, 0009, 0018).
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("sale_order_poc_mrp_planner", {
    steps: () => [
        {
            content: "The configuration summary is on the order",
            trigger: ".o_field_widget[name=poc_summary]:contains(300x500/20)",
        },
        // отметнатите параметри стоят във формата, без да се отваря раздел
        // (ADR sale-order-poc/0018)
        {
            content: "The marked parameter is on the form",
            trigger:
                ".o_field_widget[name=poc_mo_params] .o_property_field[property-name=t_width_mm]",
        },
        {
            content: "An unmarked parameter is not",
            trigger:
                ".o_field_widget[name=poc_mo_params]:not(:has(.o_property_field[property-name=t_length_mm]))",
        },
        {
            content: "Open the Configuration tab",
            trigger: ".o_notebook .nav-link:contains(Configuration)",
            run: "click",
        },
        {
            content: "The parameters are shown",
            trigger:
                ".o_field_widget[name=poc_params] .o_property_field[property-name=t_width_mm]",
        },
        {
            content: "Recompute from Configuration",
            trigger: "button[name=action_poc_recompute]",
            run: "click",
        },
        {
            content: "No error",
            trigger: ".o_form_view:not(:has(.o_form_status_indicator_buttons:visible))",
            run() {
                if (document.querySelector(".o_error_dialog")) {
                    throw new Error("Recompute raised an error dialog");
                }
            },
        },
    ],
});
