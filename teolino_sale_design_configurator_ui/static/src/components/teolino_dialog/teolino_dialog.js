/** @odoo-module */

// Teolino-specific overrides on DesignConfiguratorWidget:
//   - param lookups by `string` label
//   - per-shutter dimension state (L/H array when shutter_count > 1)
//   - color-cascade helpers (main_color → 12 component colors)
//   - sub-modal openers (placeholders for Stage 3+4)
//   - filter helpers used by the override template
//   - LIVE BoM preview (debounced RPC → mrp.bom.simulate_for_variant)
// The template `sale_design_configurator.DesignConfiguratorWidget` is REPLACED
// by teolino_dialog.xml (loaded after upstream — last definition wins).
//
// ⚠ CONFLICT с TΠ Availability (mrp_design_matrix ≥ 1.10.0):
// teolino_dialog.xml не носи `t-att-class="...o_cfg_disabled..."` нито
// `t-att-disabled="param.tpiEnabled === false ? 'disabled' : undefined"`
// → когато тоя модул е installed, TΠ reactive disable от sale_design_configurator
// не работи в UI. Teolino-специфичните constraints се покриват от
// `teolinoFiltered(byStr[...])` (виж teolino_constraints.js — hardcoded shutter
// rules). За generic (не-shutter) дизайн модули, TΠ остава dead UI behavior
// тук, защото template-ът е full override.
//
// TODO: добави tpiEnabled awareness в teolinoFiltered() ИЛИ merge-ни
// availability.allowed_values с teolino's filter rules (union).
// До тогава: TΠ е useful само за BoM-ове без custom UI override.

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { DesignConfiguratorWidget } from "@sale_design_configurator/components/design_configurator/design_configurator";
import { SHUTTER_CONSTRAINTS, PARAM_KEYS, BOX_BY_HEIGHT_AND_SLAT, H_HARD_MAX, L_HARD_MAX } from "../teolino_constraints";
import { TeolinoColorDialog, TEOLINO_COMPONENT_COLOR_LABELS } from "../teolino_color_dialog/teolino_color_dialog";

// Full set, used for the "use_main" cascade on save (every defined sub-property
// gets resolved to main_color so lot.design_params never carries the sentinel).
const COMPONENT_COLOR_KEYS = [
    "color_slat", "color_caps", "color_box", "color_endcap",
    "color_central_endcap", "color_terminal", "color_guide",
    "color_brush", "color_package", "color_rope",
    "color_shirit", "color_safety",
];

// Subset surfaced in the customer-facing color sub-modal.  Per Vladimir
// (2026-05-24): кашон/четка/safety/central_endcap/rope/shirit are produced
// in a single fixed color regardless of how many variants the DB carries
// (натурален кашон, черна четка, default rope, ...), so offering a "color
// picker" for them is misleading.  Slat/caps/box/endcap/terminal/guide are
// the customer-visible exterior parts and stay user-pickable.
const CUSTOMER_PICKABLE_COLOR_KEYS = [
    "color_slat", "color_caps", "color_box", "color_endcap",
    "color_terminal", "color_guide",
];

function _byString(params) {
    const map = {};
    for (const p of params || []) {
        if (p && p.string) map[p.string] = p;
    }
    return map;
}

function _isShutterDef(params) {
    return (params || []).some(p => p && p.string === PARAM_KEYS.SHUTTER_MODEL);
}

// Point the component at our custom template (registered in teolino_dialog.xml).
// Owl rejects registering two templates with the same name, so we use a
// distinct name and swap the static `template` ref here.
DesignConfiguratorWidget.template = "teolino_sale_design_configurator_ui.DesignConfiguratorWidget";

patch(DesignConfiguratorWidget.prototype, {
    setup() {
        super.setup();
        // Dialog service for the per-component color sub-modal (Sprint 3).
        this._teolinoDialog = useService("dialog");
        // Seed the live-preview state slot so Owl reactivity picks it up
        // and trigger an initial simulate after mount completes.
        if (this.ui && this.ui.teolinoBomPreview === undefined) {
            this.ui.teolinoBomPreview = { lines: [], total_material: 0, active_count: 0, total_count: 0, loading: false };
        }
        // Defer initial RPC + per-shutter restore to give onMounted (lot
        // load + defaults) time to settle.
        setTimeout(async () => {
            await this._teolinoRestorePerShutterFromLot();
            this._teolinoScheduleSimulate();
        }, 600);
    },

    /**
     * If we're editing an existing lot that has teolino_per_shutter_dims,
     * pre-fill the JS store so the per-shutter L/H inputs show user's
     * previously entered values instead of an equal split of the total.
     */
    async _teolinoRestorePerShutterFromLot() {
        if (!this.props.existingLotId || !this.orm) return;
        try {
            const [lot] = await this.orm.read(
                "stock.lot", [this.props.existingLotId],
                ["teolino_per_shutter_dims"],
            );
            const raw = (lot && lot.teolino_per_shutter_dims) || "";
            if (!raw) return;
            const store = this._teolinoEnsurePerShutterStore();
            store.L = []; store.H = [];
            for (const chunk of raw.split(",")) {
                const clean = chunk.trim().toLowerCase().replace("х", "x");
                if (!clean || !clean.includes("x")) continue;
                const [lS, hS] = clean.split("x");
                store.L.push(parseFloat(lS) || 0);
                store.H.push(parseFloat(hS) || 0);
            }
        } catch (e) {
            console.warn("teolino_dialog: per-shutter restore failed", e);
        }
    },

    // ── Lookup ─────────────────────────────────────────────

    get teolinoParamsByString() {
        return _byString(this.props.paramDefinition || []);
    },

    // ── Live BoM preview ───────────────────────────────────

    /**
     * Build a rich design_params list (Properties format) from current
     * this.params dict + paramDefinition.  Mirrors what stock.lot stores.
     */
    _teolinoBuildRichParams() {
        const out = [];
        for (const def of (this.props.paramDefinition || [])) {
            if (!def || !def.name) continue;
            const value = this.params[def.name];
            if (value === undefined || value === null || value === "") continue;
            out.push({
                name: def.name,
                type: def.type || "char",
                string: def.string || def.name,
                value: value,
            });
        }
        // Width/height live as flat keys in this.params; surface them too.
        for (const flatKey of ["width", "height", "thickness"]) {
            if (this.params[flatKey] !== undefined && this.params[flatKey] !== "") {
                const labelMap = {width: "Width (mm)", height: "Height (mm)", thickness: "Thickness (mm)"};
                out.push({
                    name: flatKey,
                    type: "float",
                    string: labelMap[flatKey],
                    value: this.params[flatKey],
                });
            }
        }
        return out;
    },

    _teolinoScheduleSimulate() {
        if (this._teolinoSimTimer) clearTimeout(this._teolinoSimTimer);
        this._teolinoSimTimer = setTimeout(() => this._teolinoRunSimulate(), 300);
    },

    /**
     * Build the per-shutter dimensions array for backend (sc=1 returns []).
     * Reads from the JS instance store filled by teolinoOnPerShutterDimChange.
     */
    _teolinoBuildPerShutterPairs() {
        const sc = this.teolinoShutterCount();
        if (sc <= 1) return [];
        const store = this._teolinoEnsurePerShutterStore();
        const out = [];
        for (let i = 0; i < sc; i++) {
            const L = parseFloat(store.L[i]) || 0;
            const H = parseFloat(store.H[i]) || 0;
            if (L > 0 && H > 0) out.push([L, H]);
        }
        return out;
    },

    _teolinoBuildPerShutterDimsString() {
        const pairs = this._teolinoBuildPerShutterPairs();
        return pairs.map(([L, H]) => `${L}x${H}`).join(",");
    },

    async _teolinoRunSimulate() {
        if (!this.props.productId || !this.orm) return;
        const rich = this._teolinoBuildRichParams();
        if (!rich.length) return;
        if (!this.ui.teolinoBomPreview) {
            this.ui.teolinoBomPreview = { lines: [], total_material: 0, active_count: 0, total_count: 0, loading: true };
        } else {
            this.ui.teolinoBomPreview.loading = true;
        }
        try {
            const perShutter = this._teolinoBuildPerShutterPairs();
            const result = await this.orm.call(
                "mrp.bom", "simulate_for_variant",
                [this.props.productId, rich, 1.0, perShutter],
            );
            this.ui.teolinoBomPreview = Object.assign({ loading: false, hidden: false }, result);
        } catch (e) {
            console.warn("teolino_dialog: simulate RPC failed", e);
            // Hide the panel silently when the backend method is missing —
            // happens after asset-only deploy before the worker restart picks
            // up new Python code (see feedback_base_import_module_python_cache).
            // The "method does not exist" string lives in error.data.debug;
            // error.message is the generic "Odoo Server Error" wrapper.
            const exc = e || {};
            const data = exc.data || (exc.exceptionName ? exc : {});
            const debug = (data && (data.debug || data.message)) || "";
            const name = (data && data.name) || "";
            const msg = exc.message || debug || "";
            const isMissing = (
                /does not exist/i.test(debug) ||
                /does not exist/i.test(msg) ||
                name === "builtins.AttributeError"
            );
            this.ui.teolinoBomPreview = {
                lines: [], total_material: 0, active_count: 0, total_count: 0,
                loading: false,
                hidden: isMissing,
                error: isMissing ? "" : (msg || "RPC failed"),
            };
        }
    },

    teolinoBomPreview() {
        return this.ui.teolinoBomPreview || { lines: [], total_material: 0, active_count: 0, total_count: 0, loading: false };
    },

    teolinoBomPreviewActiveLines() {
        const p = this.teolinoBomPreview();
        return (p.lines || []).filter(l => l.qty > 0);
    },

    teolinoFormatNum(v, digits = 2) {
        const n = parseFloat(v) || 0;
        return n.toFixed(digits);
    },

    // Capture the id returned by upstream _saveDesignLot AND write the
    // per-shutter dims field on the same lot BEFORE upstream's onConfirm
    // fires set_design_lot — otherwise the description regen on the SO
    // line runs against an empty teolino_per_shutter_dims and falls back
    // to flat Width/Height instead of the per-panel breakdown.
    async _saveDesignLot() {
        const id = await super._saveDesignLot();
        this._teolinoLastLotId = id;
        try {
            const dimsStr = this._teolinoBuildPerShutterDimsString();
            if (id && this.orm) {
                await this.orm.write("stock.lot", [id], {
                    teolino_per_shutter_dims: dimsStr || false,
                });
            }
        } catch (e) {
            console.warn("teolino_dialog: per-shutter dims pre-write failed", e);
        }
        return id;
    },

    teolinoModelValue() {
        const byStr = this.teolinoParamsByString;
        const p = byStr[PARAM_KEYS.SHUTTER_MODEL];
        return p ? this.params[p.name] : null;
    },

    teolinoModelConstraints() {
        const m = this.teolinoModelValue();
        return m ? SHUTTER_CONSTRAINTS[m] : null;
    },

    // ── Per-param selection filter ─────────────────────────

    teolinoFiltered(param) {
        if (!param || !param.selection) return [];
        if (!_isShutterDef(this.props.paramDefinition)) return param.selection;
        const c = this.teolinoModelConstraints();
        if (!c) return param.selection;
        let allowed = null;
        if (param.string === PARAM_KEYS.BOX_SIZE) allowed = c.boxes;
        else if (param.string === PARAM_KEYS.SHUTTER_COUNT) allowed = c.shutter_counts;
        else if (param.string === PARAM_KEYS.CONTROL_TYPE) allowed = c.controls;
        else if (param.string === PARAM_KEYS.GUIDE_TYPE) allowed = c.guides;
        if (!allowed) return param.selection;
        return param.selection.filter(([v]) => allowed.includes(v));
    },

    teolinoBoxAllowed() {
        const m = this.teolinoModelValue();
        // Built-In has no box → hide row
        return m !== "built_in";
    },

    teolinoGuideVisible() {
        // Only Thermo Comfort uses the guide choice
        return this.teolinoModelValue() === "thermo_comfort";
    },

    // ── Per-shutter dimension state ────────────────────────

    teolinoShutterCount() {
        const byStr = this.teolinoParamsByString;
        const p = byStr[PARAM_KEYS.SHUTTER_COUNT];
        if (!p) return 1;
        const v = this.params[p.name];
        return v ? parseInt(v, 10) || 1 : 1;
    },

    teolinoShutterIndices() {
        const sc = this.teolinoShutterCount();
        return Array.from({ length: sc }, (_, i) => i);
    },

    _teolinoEnsurePerShutterStore() {
        if (!this._teolinoPerShutter) {
            this._teolinoPerShutter = { L: [], H: [] };
        }
        return this._teolinoPerShutter;
    },

    teolinoPerShutterL(i) {
        const store = this._teolinoEnsurePerShutterStore();
        if (store.L[i] === undefined) {
            // Initialize from current width split equally
            const sc = this.teolinoShutterCount();
            const w = parseFloat(this.params["width"] || 0);
            store.L[i] = sc > 0 ? Math.round(w / sc) : 0;
        }
        return store.L[i];
    },

    teolinoPerShutterH(i) {
        const store = this._teolinoEnsurePerShutterStore();
        if (store.H[i] === undefined) {
            store.H[i] = parseFloat(this.params["height"] || 0);
        }
        return store.H[i];
    },

    teolinoTotalL() {
        const store = this._teolinoEnsurePerShutterStore();
        const sc = this.teolinoShutterCount();
        let total = 0;
        for (let i = 0; i < sc; i++) {
            total += parseFloat(store.L[i] || 0);
        }
        return total;
    },

    teolinoOnDimChange(ev) {
        const key = ev.target.dataset.param;
        const value = parseFloat(ev.target.value) || 0;
        if (!key) return;
        // Route through upstream onParamChange so reactive state, props
        // dispatch, and downstream re-validation all fire (matches behavior
        // of slider/segment events on other params).
        this.onParamChange(key, value);
    },

    teolinoOnPerShutterDimChange(ev) {
        const idx = parseInt(ev.target.dataset.shutterIndex, 10);
        const dim = ev.target.dataset.dim;
        const value = parseFloat(ev.target.value) || 0;
        const store = this._teolinoEnsurePerShutterStore();
        store[dim][idx] = value;
        if (dim === "L") {
            this.params["width"] = this.teolinoTotalL();
        } else if (dim === "H") {
            // Use the maximum H across shutters (single box)
            this.params["height"] = Math.max(...store.H.map(v => parseFloat(v) || 0));
        }
        this._teolinoScheduleSimulate();
    },

    // ── Color cascade + sub-modal opener ────────────────────

    /**
     * Walk the active BoM lines for this product, derive which color_X
     * groups have at least one component template with real color variants
     * (matched via default_code suffix "-NNN"), and return the union of
     * available color codes per group:
     *
     *   { color_box: Set("001","002",...), color_slat: Set(...), ... }
     *
     * Components without variants (Pulley, Axis, Cup) carry
     * param_attribute_map=false in BoM and are skipped.  Sub-properties
     * that DO have a definition entry but no BoM coverage (color_rope,
     * color_shirit pre-kits-sprint) get dropped here so the modal only
     * shows rows the customer can actually act on.
     */
    async _teolinoFetchColorAvailability() {
        if (this._teolinoColorAvailCache) return this._teolinoColorAvailCache;
        if (!this.orm || !this.props.productId) return {};
        const COLOR_ATTR = "teolino_shutters.product_attribute_color";
        try {
            const boms = await this.orm.searchRead("mrp.bom", [
                ["product_tmpl_id.product_variant_ids", "in", [this.props.productId]],
                ["active", "=", true],
            ], ["id"], { limit: 1 });
            if (!boms.length) return {};
            const lines = await this.orm.searchRead(
                "mrp.bom.line", [["bom_id", "=", boms[0].id]],
                ["product_id", "param_attribute_map"], { limit: 500 },
            );
            // {color_X: Set(template_ids)}
            const tmplByKey = {};
            const placeholderTmplIds = new Set();
            for (const line of lines) {
                const pam = line.param_attribute_map || {};
                for (const [colorKey, attrXmlId] of Object.entries(pam)) {
                    if (attrXmlId !== COLOR_ATTR) continue;
                    placeholderTmplIds.add(line.product_id[0]);
                    if (!tmplByKey[colorKey]) tmplByKey[colorKey] = new Set();
                    tmplByKey[colorKey].add(line.product_id[0]);
                }
            }
            if (!placeholderTmplIds.size) return {};
            // Resolve placeholder variants → product_tmpl_id, then fetch all
            // variants of those templates to read their default_codes.
            const placeholders = await this.orm.read(
                "product.product", [...placeholderTmplIds],
                ["id", "product_tmpl_id"],
            );
            const tmplIdByPlaceholder = {};
            const tmplIds = new Set();
            for (const p of placeholders) {
                tmplIdByPlaceholder[p.id] = p.product_tmpl_id[0];
                tmplIds.add(p.product_tmpl_id[0]);
            }
            const variants = await this.orm.searchRead(
                "product.product",
                [["product_tmpl_id", "in", [...tmplIds]]],
                ["id", "default_code", "product_tmpl_id"], { limit: 5000 },
            );
            const colorsByTmpl = {};
            for (const v of variants) {
                if (!v.default_code) continue;
                const m = v.default_code.match(/-(\d{3})$/);
                if (!m) continue;
                const tid = v.product_tmpl_id[0];
                if (!colorsByTmpl[tid]) colorsByTmpl[tid] = new Set();
                colorsByTmpl[tid].add(m[1]);
            }
            const out = {};
            for (const [colorKey, placeholderSet] of Object.entries(tmplByKey)) {
                const codes = new Set();
                for (const phId of placeholderSet) {
                    const tid = tmplIdByPlaceholder[phId];
                    const cs = colorsByTmpl[tid];
                    if (cs) cs.forEach(c => codes.add(c));
                }
                if (codes.size) out[colorKey] = codes;
            }
            this._teolinoColorAvailCache = out;
            return out;
        } catch (e) {
            console.warn("teolino_dialog: color availability fetch failed", e);
            return {};
        }
    },

    async teolinoOpenColorModal() {
        const byStr = this.teolinoParamsByString;
        const mainP = byStr["main_color"];
        const mainVal = mainP ? this.params[mainP.name] : "";
        const mainLabel = mainP && mainVal
            ? ((mainP.selection || []).find(([v]) => v === mainVal) || [mainVal, mainVal])[1]
            : "";

        const availability = await this._teolinoFetchColorAvailability();

        // Two filters: (1) component is customer-pickable per Vladimir's
        // list (excludes brush/package/safety/rope/etc that ship in a fixed
        // color), AND (2) BoM actually carries that color group with real
        // variant coverage.  Trim each row's selection to codes that exist
        // (plus the "use_main" sentinel — UI-only placeholder).
        const colorParams = CUSTOMER_PICKABLE_COLOR_KEYS
            .map(k => byStr[k])
            .filter(p => p)
            .filter(p => availability[p.string] && availability[p.string].size > 0)
            .map(p => {
                const avail = availability[p.string];
                return {
                    name: p.name,
                    label: TEOLINO_COMPONENT_COLOR_LABELS[p.string] || p.string,
                    selection: (p.selection || []).filter(
                        ([code]) => code === "use_main" || avail.has(code)
                    ),
                };
            });

        if (!colorParams.length) {
            if (this.notification) {
                this.notification.add(
                    "Няма компоненти с цветни варианти за този продукт.",
                    { type: "info" }
                );
            }
            return;
        }

        const current = {};
        for (const cp of colorParams) {
            current[cp.name] = this.params[cp.name] || "use_main";
        }

        this._teolinoDialog.add(TeolinoColorDialog, {
            colorParams,
            currentValues: current,
            mainColorValue: mainVal,
            mainColorLabel: mainLabel,
            onSave: (values) => {
                for (const [name, val] of Object.entries(values)) {
                    this.params[name] = val;
                }
                this._teolinoScheduleSimulate();
            },
        });
    },

    /**
     * Before creating/updating the lot, expand any color_X="use_main" to the
     * actual main_color value so PTAV resolution at MO time picks the right
     * variant (lot.design_params must store concrete colors — "use_main" is
     * a UI-only sentinel).  Sprint 3 fix for memory bug #3.
     *
     * After the super-save resolves with a lot id, also write the per-shutter
     * dims string (sc>1) so BoM simulate evaluates slat/guide formulas per
     * panel and produces N separate slat cuts at the panel widths.
     */
    async onConfirm() {
        try {
            const byStr = this.teolinoParamsByString;
            const mainP = byStr["main_color"];
            const mainVal = mainP ? this.params[mainP.name] : null;
            if (mainVal && mainVal !== "use_main") {
                for (const ck of COMPONENT_COLOR_KEYS) {
                    const p = byStr[ck];
                    if (!p) continue;
                    const cur = this.params[p.name];
                    if (!cur || cur === "use_main") {
                        this.params[p.name] = mainVal;
                    }
                }
            }
        } catch (e) {
            console.warn("teolino_dialog: use_main resolution failed", e);
        }
        return super.onConfirm();
    },

    // Override the central change handler to cascade colors + auto-snap.
    onParamChange(key, value) {
        const ret = super.onParamChange(key, value);
        try {
            this._teolinoAutoSnap(key, value);
            this._teolinoColorCascade(key, value);
            this._teolinoSyncPerShutter(key, value);
            this._teolinoScheduleSimulate();
        } catch (e) {
            console.warn("teolino_dialog: handler failed", e);
        }
        return ret;
    },

    _teolinoAutoSnap(changedKey, newValue) {
        const base = this.props.paramDefinition || [];
        if (!_isShutterDef(base)) return;
        const byStr = _byString(base);
        const modelParam = byStr[PARAM_KEYS.SHUTTER_MODEL];
        if (!modelParam || changedKey !== modelParam.name) return;
        const c = SHUTTER_CONSTRAINTS[newValue];
        if (!c) return;
        const snap = (paramKey, allowed) => {
            const p = byStr[paramKey];
            if (!p || !allowed.length) return;
            const cur = this.params[p.name];
            if (cur && !allowed.includes(cur)) this.params[p.name] = allowed[0];
        };
        snap(PARAM_KEYS.BOX_SIZE, c.boxes);
        snap(PARAM_KEYS.SHUTTER_COUNT, c.shutter_counts);
        snap(PARAM_KEYS.CONTROL_TYPE, c.controls);
        snap(PARAM_KEYS.GUIDE_TYPE, c.guides);
    },

    _teolinoColorCascade(changedKey, newValue) {
        const base = this.props.paramDefinition || [];
        if (!_isShutterDef(base)) return;
        const byStr = _byString(base);
        const mainParam = byStr["main_color"];
        if (!mainParam || changedKey !== mainParam.name || !newValue) return;
        for (const ck of COMPONENT_COLOR_KEYS) {
            const p = byStr[ck];
            if (!p) continue;
            const cur = this.params[p.name];
            if (!cur || cur === "use_main") {
                this.params[p.name] = newValue;
            }
        }
    },

    _teolinoSyncPerShutter(changedKey, newValue) {
        const byStr = this.teolinoParamsByString;
        const scParam = byStr[PARAM_KEYS.SHUTTER_COUNT];
        if (scParam && changedKey === scParam.name) {
            // Re-initialize per-shutter store on count change
            this._teolinoPerShutter = null;
        }
    },

    // ── Box auto-suggestion + H_MAX validation ─────────────

    /**
     * Pick the smallest box that supports the given H for current
     * (shutter_model, slat_size).  Returns null when H exceeds all
     * thresholds — caller must block save in that case.
     */
    teolinoSuggestBox(model, slat, heightMm) {
        const slatKey = parseInt(slat, 10);
        const modelMap = BOX_BY_HEIGHT_AND_SLAT[model];
        if (!modelMap) return null;
        const thresholds = modelMap[slatKey];
        if (!thresholds) return null;
        for (const [hMax, box] of thresholds) {
            if (heightMm <= hMax) return box;
        }
        return null;  // H too large
    },

    teolinoAutoSuggestBox() {
        const byStr = this.teolinoParamsByString;
        const modelP = byStr[PARAM_KEYS.SHUTTER_MODEL];
        const slatP = byStr[PARAM_KEYS.SLAT_SIZE];
        const boxP = byStr[PARAM_KEYS.BOX_SIZE];
        if (!modelP || !slatP || !boxP) return;
        const model = this.params[modelP.name];
        const slat = this.params[slatP.name];
        const h = parseFloat(this.params["height"] || 0);
        if (!model || !slat || !h) return;
        const suggested = this.teolinoSuggestBox(model, slat, h);
        if (!suggested) return;  // hard-max validation will flag in render
        const currentBox = this.params[boxP.name];
        // Auto-snap only when current box is unset OR can't fit current H.
        const currentIsAdequate = (() => {
            if (!currentBox) return false;
            const modelMap = BOX_BY_HEIGHT_AND_SLAT[model] || {};
            const thresholds = modelMap[parseInt(slat, 10)] || [];
            const entry = thresholds.find(([, box]) => box === currentBox);
            return entry && h <= entry[0];
        })();
        if (!currentIsAdequate) {
            this.params[boxP.name] = suggested;
        }
    },

    /**
     * Returns true when current H exceeds the maximum allowed for
     * (model, slat).  Template uses this to disable Create Lot button.
     */
    teolinoHardMaxExceeded() {
        const byStr = this.teolinoParamsByString;
        const modelP = byStr[PARAM_KEYS.SHUTTER_MODEL];
        const slatP = byStr[PARAM_KEYS.SLAT_SIZE];
        const h = parseFloat(this.params["height"] || 0);
        const w = parseFloat(this.params["width"] || 0);
        if (h > H_HARD_MAX) return true;
        if (w > L_HARD_MAX) return true;
        if (!modelP || !slatP) return false;
        const model = this.params[modelP.name];
        const slat = this.params[slatP.name];
        if (!model || !slat || !h) return false;
        return this.teolinoSuggestBox(model, slat, h) === null;
    },

    teolinoMaxBoxMessage() {
        const byStr = this.teolinoParamsByString;
        const modelP = byStr[PARAM_KEYS.SHUTTER_MODEL];
        const slatP = byStr[PARAM_KEYS.SLAT_SIZE];
        const model = modelP && this.params[modelP.name];
        const slat = slatP && this.params[slatP.name];
        if (!model || !slat) return "";
        const modelMap = BOX_BY_HEIGHT_AND_SLAT[model] || {};
        const thresholds = modelMap[parseInt(slat, 10)] || [];
        if (!thresholds.length) return "";
        const last = thresholds[thresholds.length - 1];
        return `Макс H за ${model} / slat ${slat} = ${last[0]} mm (box ${last[1]}).`;
    },
});

// Hook box auto-suggestion + recheck on every height/slat/model change.
// Done via patching onParamChange + teolinoOnDimChange.
const origOnParamChange = DesignConfiguratorWidget.prototype.onParamChange;
DesignConfiguratorWidget.prototype.onParamChange = function (key, value) {
    const ret = origOnParamChange.call(this, key, value);
    try {
        const byStr = this.teolinoParamsByString;
        const triggerKeys = [
            byStr[PARAM_KEYS.SHUTTER_MODEL]?.name,
            byStr[PARAM_KEYS.SLAT_SIZE]?.name,
        ];
        if (triggerKeys.includes(key)) this.teolinoAutoSuggestBox();
    } catch (e) {
        console.warn("teolino_dialog: post-change auto-suggest failed", e);
    }
    return ret;
};

const origOnDimChange = DesignConfiguratorWidget.prototype.teolinoOnDimChange;
DesignConfiguratorWidget.prototype.teolinoOnDimChange = function (ev) {
    const ret = origOnDimChange.call(this, ev);
    if (ev.target.dataset.param === "height") {
        try { this.teolinoAutoSuggestBox(); }
        catch (e) { console.warn("teolino_dialog: height auto-suggest failed", e); }
    }
    return ret;
};
