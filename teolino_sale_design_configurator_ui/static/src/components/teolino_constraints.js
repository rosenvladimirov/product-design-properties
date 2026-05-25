/** @odoo-module */

// Per-model constraints for the shutter design configurator.
// Source of truth derived from prototype/web_configurator_mockup.html
// + docs/model_specs.md (2026-05-13 catalog).
//
// Each model declares which option values are valid for box_size,
// shutter_count, control_type, guide_type.  The patch in
// teolino_filter_patch.js consumes this map to filter selection lists
// and auto-snap invalid values when the model changes.

export const SHUTTER_CONSTRAINTS = {
    standard: {
        boxes: ["137", "165", "180", "205"],
        shutter_counts: ["1", "2", "3", "4"],
        controls: ["rope", "shirit", "motor"],
        guides: ["standard"],
        h_max: 2800,
        l_max: 4000,
    },
    round: {
        boxes: ["137", "165", "180", "205"],
        shutter_counts: ["1"],
        controls: ["rope", "shirit", "motor"],
        guides: ["standard"],
        h_max: 2800,
        l_max: 4000,
    },
    t_roll: {
        boxes: ["160", "200"],
        shutter_counts: ["1", "2"],
        controls: ["shirit", "motor"],  // T-Roll has no rope option
        guides: ["standard"],
        h_max: 2800,
        l_max: 4000,
    },
    thermo_comfort: {
        boxes: ["170", "210"],
        shutter_counts: ["1"],
        controls: ["rope", "shirit", "motor"],
        guides: ["standard", "feather"],  // Only Thermo offers feather
        h_max: 2800,
        l_max: 4000,
    },
    built_in: {
        boxes: ["none"],  // No box — wall-mounted
        shutter_counts: ["1"],
        controls: ["rope", "shirit", "motor"],
        guides: ["standard"],
        h_max: 2800,  // weight-driven in catalog, conservative cap
        l_max: 3000,
    },
};

// Per-model height thresholds for box auto-selection.
// Source: prototype/bom_engine.py BOX_BY_HEIGHT_AND_SLAT (Teolino каталог 2022).
// For each (model, slat) → ordered [(H_max, box_code), ...] ascending.
// Pick smallest box where H_max >= requested H.  If H exceeds last entry,
// invalid → returns null (Create Lot button must be blocked).
//
// @deprecated mrp_design_matrix ≥ 1.12.0 (Phase B) — same data lives в
// `mrp_design_matrix_teolino_shutters/data/matrix_templates.xml`
// (lookup_tables.box_by_height) + TΦ derive_expression rule auto-selects
// box на всяка промяна на shutter_model / slat_size / Height (mm). Upstream
// `_applyCascade` ще писа в this.params преди тоя dict да се чете.
// Запазен като fallback за non-TΦ BoM-ове (legacy data). За пълно
// premium: премахни след валидация на dev-teo-2305.
export const BOX_BY_HEIGHT_AND_SLAT = {
    standard: {
        40: [[1500, "137"], [2300, "165"], [2800, "180"], [3500, "205"]],
        50: [[ 900, "137"], [1400, "165"], [2000, "180"], [2700, "205"]],
    },
    round: {
        40: [[1500, "137"], [2300, "165"], [2800, "180"], [3500, "205"]],
        50: [[ 900, "137"], [1400, "165"], [2000, "180"], [2700, "205"]],
    },
    t_roll: {
        40: [[2000, "160"], [2800, "200"]],
        50: [[1500, "160"], [2700, "200"]],
    },
    thermo_comfort: {
        40: [[2300, "170"], [2800, "210"]],
        50: [[1400, "170"], [2700, "210"]],
    },
    built_in: {
        40: [[2800, "none"]],
        50: [[2700, "none"]],
    },
};

// Global hard maxima — never produce above these.
export const H_HARD_MAX = 3500;
export const L_HARD_MAX = 4000;

// Param keys (the `string` field on each property in design.param.definition).
// These match what Rosen set up in design.param.definition id=3.
export const PARAM_KEYS = {
    SHUTTER_MODEL: "shutter_model",
    BOX_SIZE: "box_size",
    SLAT_SIZE: "slat_size",
    AXIS_SIZE: "axis_size",
    CONTROL_TYPE: "control_type",
    GUIDE_TYPE: "guide_type",
    SHUTTER_COUNT: "shutter_count",
    H_MM: "h_mm",
    L_MM: "l_mm",
};
