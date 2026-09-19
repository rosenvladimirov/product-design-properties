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
// Проверката в интерфейса от изхода на S1: пропъртитата се попълват от
// формата, изчисленото се пише при запис, а схемата не се мени от POC.
import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

function property(code) {
    return `.o_field_widget[name=params] .o_property_field[property-name=${code}]`;
}

// „edit“ не потвърждава полето: потвърждава го излизането от него, а тогава
// уиджетът се рисува наново и изтрива написаното в СЛЕДВАЩОТО поле. Затова
// всяко поле се потвърждава и се чака форматираната стойност.
function editProperty(code, content, value) {
    return [
        {
            content,
            trigger: `${property(code)} input`,
            run: `edit ${value}`,
        },
        {
            content: `Leave ${content}`,
            trigger: ".o_form_view .oe_title h1",
            run: "click",
        },
        {
            content: `${content} is applied`,
            trigger: `${property(code)} input:value(/^${value}[.,]00$/)`,
        },
    ];
}

function openEditProperties() {
    return [
        {
            content: "Open the gear menu",
            trigger: ".o_form_view .o_cp_action_menus i.fa-cog",
            run: "click",
        },
        {
            content: "Edit Properties",
            trigger: ".o_menu_item:contains(Edit Properties)",
            run: "click",
        },
    ];
}

registry.category("web_tour.tours").add("sale_order_poc_salesman", {
    steps: () => [
        ...editProperty("t_width_mm", "Width", 300),
        ...editProperty("t_length_mm", "Length", 500),
        ...editProperty("t_thickness_um", "Thickness", 20),
        {
            // само за протокола: формулите се смятат при запис, не при onchange
            content: "Weight before saving",
            trigger: `${property("t_weight_g")} input`,
            run() {
                console.log(`POC-UI weight before save: [${this.anchor.value}]`);
            },
        },
        ...stepUtils.saveForm(),
        {
            content: "The weight is computed on save",
            trigger: `${property("t_weight_g")} input`,
            run() {
                console.log(`POC-UI weight after save: [${this.anchor.value}]`);
                if (!this.anchor.value.startsWith("5.52")) {
                    throw new Error(`Weight is "${this.anchor.value}", expected 5.52`);
                }
            },
        },
        {
            content: "No button to add a parameter",
            trigger: ".o_form_view:not(:has(.o_field_property_add button))",
        },
        ...openEditProperties(),
        {
            content: "A salesman may not change the definition",
            trigger: ".o_notification",
        },
        {
            content: "Still no button to add a parameter",
            trigger: ".o_form_view:not(:has(.o_field_property_add button))",
        },
    ],
});

registry.category("web_tour.tours").add("sale_order_poc_manager", {
    steps: () => [
        {
            content: "The parameters are shown",
            trigger: `${property("t_width_mm")} input`,
        },
        ...openEditProperties(),
        {
            // бутонът се вижда, защото мениджърът пише шаблона; записът на
            // схемата от тук спира пазачът в sale.order.poc.template.write
            content: "A manager reaches the definition editor",
            trigger: ".o_field_property_add button",
        },
    ],
});
