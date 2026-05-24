/** @odoo-module */

// Sub-modal opened from the main configurator's "Цветове на компонентите ▸"
// button.  Lets the user override per-component colors that otherwise inherit
// from main_color via _teolinoColorCascade.

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

// Bulgarian labels for component color params (id=6 design definition).
// Keyed by the property's `string` (which equals the param key like
// "color_slat" — set by Vladimir when extending Rosen's id=5 with colors).
export const TEOLINO_COMPONENT_COLOR_LABELS = {
    color_slat: "Ламел",
    color_caps: "Капачета",
    color_box: "Кутия",
    color_endcap: "Капак на кутията",
    color_central_endcap: "Централен капак",
    color_terminal: "Терминал",
    color_guide: "Водач",
    color_brush: "Четка",
    color_package: "Кашон",
    color_rope: "Въже",
    color_shirit: "Ширит",
    color_safety: "Защитна пластина",
};

export class TeolinoColorDialog extends Component {
    static template = "teolino_sale_design_configurator_ui.TeolinoColorDialog";
    static components = { Dialog };
    static props = {
        colorParams: Array,
        currentValues: Object,
        mainColorValue: { type: String, optional: true },
        mainColorLabel: { type: String, optional: true },
        onSave: Function,
        close: Function,
    };

    setup() {
        this.state = useState({
            values: { ...this.props.currentValues },
        });
    }

    onPick(paramName, value) {
        this.state.values[paramName] = value;
    }

    isActive(cp, optValue) {
        return this.state.values[cp.name] === optValue;
    }

    resetAllToMain() {
        for (const cp of this.props.colorParams) {
            this.state.values[cp.name] = "use_main";
        }
    }

    onSaveClick() {
        this.props.onSave({ ...this.state.values });
        this.props.close();
    }

    onCancelClick() {
        this.props.close();
    }
}
