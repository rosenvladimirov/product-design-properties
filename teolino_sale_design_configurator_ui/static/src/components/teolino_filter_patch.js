/** @odoo-module */

// Patch sale_design_configurator's DesignConfiguratorWidget to filter
// selection options per current shutter_model + auto-snap invalid values
// + hide irrelevant rows (e.g. guide_type unless model === thermo_comfort).
//
// Only activates when the definition contains a `shutter_model` property
// (i.e. it's our parametric shutter designer, not some other definition).

import { patch } from "@web/core/utils/patch";
import { DesignConfiguratorWidget } from "@sale_design_configurator/components/design_configurator/design_configurator";
import { SHUTTER_CONSTRAINTS, PARAM_KEYS } from "./teolino_constraints";

// Map param.string → param object (used to look up the UUID-hashed `name`
// by the human label).
function _byString(params) {
    const map = {};
    for (const p of params || []) {
        if (p.string) map[p.string] = p;
    }
    return map;
}

function _isShutterDefinition(params) {
    return (params || []).some(p => p && p.string === PARAM_KEYS.SHUTTER_MODEL);
}

function _restrictSelection(param, allowedValues) {
    if (!param || !param.selection) return param;
    const filtered = param.selection.filter(([v]) => allowedValues.includes(v));
    return Object.assign({}, param, { selection: filtered });
}

// @deprecated блок (mrp_design_matrix ≥ 1.14.0, Phase E):
// Upstream DesignConfiguratorWidget (sale_design_configurator ≥ 1.10.0) вече има
// `_decorateParam` + TΠ availability eval, които покриват displayParams filter
// + auto-snap functionality чрез matrix data (mrp_design_matrix_teolino_shutters
// availability_table + cascade_table seed).
//
// Този patch остава като UI fallback за следните случаи:
// 1. BoM-ове без матричен template (legacy data) — продължава да работи както досега
// 2. Кодов път където upstream TΠ flow още не покрива edge case
//
// План за пълно премахване:
// - Phase E+1: уверете се че всички BoM-ове на dev-teo-2305 имат matrix_template_id
// - Phase E+2: уверете се че матрицата покрива всички shutter constraints
// - Phase E+3: премахни патча и приеми upstream `displayParams`

patch(DesignConfiguratorWidget.prototype, {
    /**
     * Filter selection options per current shutter_model.  Falls back to
     * upstream behavior when the definition is not a shutter (no
     * `shutter_model` property found).
     *
     * @deprecated Phase E — upstream `displayParams` + `_decorateParam`
     * консумира TΠ availability_table (matrix-driven, same logic). Този
     * override остава като legacy fallback за non-matrix BoM-ове.
     */
    get displayParams() {
        const base = super.displayParams;
        if (!_isShutterDefinition(base)) {
            return base;
        }
        const byStr = _byString(base);
        const modelParam = byStr[PARAM_KEYS.SHUTTER_MODEL];
        if (!modelParam) return base;

        const modelValue = this.params[modelParam.name];
        if (!modelValue) return base;  // Nothing chosen yet — show everything

        const constraints = SHUTTER_CONSTRAINTS[modelValue];
        if (!constraints) return base;

        return base
            .map(p => {
                if (!p || !p.string) return p;
                if (p.string === PARAM_KEYS.BOX_SIZE) {
                    return _restrictSelection(p, constraints.boxes);
                }
                if (p.string === PARAM_KEYS.SHUTTER_COUNT) {
                    return _restrictSelection(p, constraints.shutter_counts);
                }
                if (p.string === PARAM_KEYS.CONTROL_TYPE) {
                    return _restrictSelection(p, constraints.controls);
                }
                if (p.string === PARAM_KEYS.GUIDE_TYPE) {
                    if (constraints.guides.length <= 1) {
                        return Object.assign({}, p, { _teolinoHidden: true });
                    }
                    return _restrictSelection(p, constraints.guides);
                }
                return p;
            })
            .filter(p => !(p && p._teolinoHidden));
    },

    /**
     * Override the central change handler to auto-snap dependent values
     * when shutter_model changes (e.g. switching from Standard to Round
     * with shutter_count = 3 → snap to 1).
     *
     * @deprecated Phase E — upstream `_enforceAvailability` (TΠ) +
     * `_applyCascade` (TΦ) покриват auto-snap семантиката чрез matrix-driven
     * rules. Този override остава за edge cases и legacy non-matrix BoM-ове.
     */
    onParamChange(key, value) {
        const ret = super.onParamChange(key, value);
        try {
            this._teolinoAutoSnap(key, value);
            this._teolinoColorCascade(key, value);
        } catch (e) {
            // Defensive — never break upstream flow on snap glitches.
            console.warn("teolino_filter_patch: auto-snap/cascade failed", e);
        }
        return ret;
    },

    /**
     * When main_color changes, cascade its value to all 12 component
     * color_* params.  User can later override individual colors.
     *
     * @deprecated mrp_design_matrix ≥ 1.11.0 — TΦ Cascade слоят (cascade_table
     * на mrp.matrix.template + mrp.bom) покрива този case декларативно.
     * Виж `mrp_design_matrix_teolino_shutters/data/matrix_templates.xml` →
     * cascade_table (12 rules за main_color → component_colors). Когато BoM
     * има cascade_table, upstream `_applyCascade` на DesignConfiguratorWidget
     * вече ще е приложил cascade-а преди тоя метод да се извика — current
     * values ще match-нат main_color, така че `cur !== "use_main"` ще guard-не
     * write-а тук (no-op за TΦ-enabled flow).
     *
     * Оставен като fallback за BoM-ове без cascade_table (legacy data).
     * За пълно premium: премахни TΦ-enabled flow и този метод след валидация
     * на dev-teo-2305.
     */
    _teolinoColorCascade(changedKey, newValue) {
        const base = this.props.paramDefinition || [];
        if (!_isShutterDefinition(base)) return;
        const byStr = _byString(base);
        const mainColorParam = byStr["main_color"];
        if (!mainColorParam || changedKey !== mainColorParam.name) return;
        if (!newValue) return;
        const componentColorKeys = [
            "color_slat", "color_caps", "color_box", "color_endcap",
            "color_central_endcap", "color_terminal", "color_guide",
            "color_brush", "color_package", "color_rope",
            "color_shirit", "color_safety",
        ];
        for (const ck of componentColorKeys) {
            const p = byStr[ck];
            if (!p) continue;
            // Only cascade if user hasn't explicitly overridden (current value
            // is empty or "use_main")
            const cur = this.params[p.name];
            if (!cur || cur === "use_main") {
                this.params[p.name] = newValue;
            }
        }
    },

    _teolinoAutoSnap(changedKey, newValue) {
        const base = this.props.paramDefinition || [];
        if (!_isShutterDefinition(base)) return;
        const byStr = _byString(base);
        const modelParam = byStr[PARAM_KEYS.SHUTTER_MODEL];
        if (!modelParam || changedKey !== modelParam.name) return;
        const constraints = SHUTTER_CONSTRAINTS[newValue];
        if (!constraints) return;

        const snap = (paramKey, allowed) => {
            const p = byStr[paramKey];
            if (!p || !allowed.length) return;
            const cur = this.params[p.name];
            if (cur && !allowed.includes(cur)) {
                this.params[p.name] = allowed[0];
            }
        };
        snap(PARAM_KEYS.BOX_SIZE, constraints.boxes);
        snap(PARAM_KEYS.SHUTTER_COUNT, constraints.shutter_counts);
        snap(PARAM_KEYS.CONTROL_TYPE, constraints.controls);
        snap(PARAM_KEYS.GUIDE_TYPE, constraints.guides);
    },
});
