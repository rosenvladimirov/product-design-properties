/** @odoo-module **/
// Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import {
    Component,
    useState,
    useRef,
    onMounted,
    onWillUnmount,
    onWillUpdateProps,
} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { RuleMatrixPreview } from "@mrp_design_matrix/components/rule_matrix_preview/rule_matrix_preview";

// Three.js + SVGLoader loaded via assets bundle (see __manifest__.py)
// window.THREE is available after page load.

export class DesignConfiguratorWidget extends Component {
    static template = "sale_design_configurator.DesignConfiguratorWidget";
    static components = { RuleMatrixPreview };

    static props = {
        productId: { type: Number },
        definitionId: { type: Number },
        definitionCode: { type: String },
        paramDefinition: { type: Array },
        validationRules: { type: Array, optional: true },
        profiles: { type: Array, optional: true },
        bomAssets: { type: Array, optional: true },
        mainProductAssets: { type: Object, optional: true },
        childComponents: { type: Array, optional: true },
        accessoryVariants: { type: Array, optional: true },
        modelVariants: { type: Object, optional: true },
        constraintTable: { type: [Object, { value: false }], optional: true },
        geometryTable: { type: [Object, { value: false }], optional: true },
        materialTable: { type: [Object, { value: false }], optional: true },
        operationTable: { type: [Object, { value: false }], optional: true },
        availabilityTable: { type: [Object, { value: false }], optional: true },
        cascadeTable: { type: [Object, { value: false }], optional: true },
        multiplicityTable: { type: [Object, { value: false }], optional: true },
        layoutTable: { type: [Object, { value: false }], optional: true },
        bomId: { type: [Number, { value: false }], optional: true },
        bomLines: { type: Array, optional: true },
        hasAvailability: { type: Boolean, optional: true },
        existingLotId: { type: [Number, Boolean], optional: true },
        onLotCreated: { type: Function },
        onClose: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.canvasRef = useRef("canvas");
        this.overlayRef = useRef("overlay");

        this.params = useState(
            this._buildInitialParams(this.props.paramDefinition)
        );

        const hasAccessories = (this.props.accessoryVariants || []).length > 0;
        this.ui = useState({
            saving: false,
            validErrors: [],
            validWarns: [],
            autoRotate: true,
            overlayOpen: false,
            overlayHeight: 24,
            description: "",
            // TΠ — per-param availability state, populated reactively от сървъра.
            // Schema: { paramName: {visible?: bool, enabled?: bool,
            //                       allowed_values?: any[], default_override?: any} }
            // Празно ⇒ всичко visible+enabled (default behaviour).
            availability: {},
        });
        // Debounce за TΠ eval — да не bомбардираме сървъра при бързо driving
        // на slider-и. 150ms е sweet spot между responsivenes и rate-limit.
        this._availabilityTimer = null;

        this._three = {
            renderer: null, scene: null, camera: null, group: null,
            animId: null, rotX: 0.3, rotY: 0.4,
            drag: false, prevX: 0, prevY: 0,
            leafPivot: null,
            leafOpen: false,
            leafAnimating: false,
            leafTargetAngle: 0,
            raycaster: null,
        };

        onMounted(async () => {
            if (this.props.existingLotId) {
                await this._loadExistingLot(this.props.existingLotId);
            }
            // Initialize child component params with defaults
            for (const child of (this.props.childComponents || [])) {
                for (const def of (child.paramDefinition || [])) {
                    if (this.params[def.name] === undefined) {
                        if (def.type === 'boolean') {
                            this.params[def.name] = def.default === 'true' || def.default === true;
                        } else if (def.type === 'float') {
                            this.params[def.name] = parseFloat(def.default) || 0;
                        } else if (def.type === 'selection' && def.selection?.length) {
                            this.params[def.name] = def.default || def.selection[0][0];
                        } else {
                            this.params[def.name] = def.default || '';
                        }
                    }
                }
            }
            // Only init Three.js when NOT in rule preview mode
            if (!this.showRulePreview) {
                // Hide canvas until model is ready (prevents flash/jump)
                const canvas = this.canvasRef.el;
                if (canvas) {
                    canvas.style.opacity = "0";
                    canvas.style.transition = "opacity 0.3s ease";
                }
                this._applyVariantOverridesFromParams();
                this._initThree();
                await this._buildModel();
                // Fade in canvas
                if (canvas) canvas.style.opacity = "1";
            }
            this._validate();
            this._updateDescription();
            // Initial TΠ pass — установява първоначални disable/restrict-и
            this._scheduleAvailabilityEval(0);
        });

        onWillUpdateProps((newProps) => {
            if (newProps.definitionCode !== this.props.definitionCode) {
                Object.assign(
                    this.params,
                    this._buildInitialParams(newProps.paramDefinition)
                );
                this._buildModel();
                this._validate();
            }
        });

        onWillUnmount(() => this._destroyThree());
    }

    // ── Param initialisation ────────────────────────────────────────────

    _buildInitialParams(definition) {
        const p = {};
        for (const prop of definition || []) {
            if (prop.type === "boolean") {
                p[prop.name] = prop.default === "true" || prop.default === true;
            } else if (prop.type === "float") {
                p[prop.name] = parseFloat(prop.default) || 0.0;
            } else if (prop.type === "selection" && !prop.default && prop.selection?.length) {
                p[prop.name] = prop.selection[0][0];
            } else {
                p[prop.name] = prop.default || "";
            }
        }
        return p;
    }

    async _loadExistingLot(lotId) {
        const [lot] = await this.orm.read("stock.lot", [lotId], [
            "design_params",
        ]);
        if (!lot) return;
        const dp = lot.design_params;
        if (Array.isArray(dp)) {
            // Properties field returns [{name, type, string, value}, ...]
            for (const prop of dp) {
                if (prop.name && prop.value !== undefined) {
                    this.params[prop.name] = prop.value;
                }
            }
        } else if (dp && typeof dp === "object") {
            Object.assign(this.params, dp);
        }
    }

    // ── Data-driven validation ──────────────────────────────────────────

    _validate() {
        const rules = this.props.validationRules || [];
        const p = this.params;

        // If rules are defined, use generic evaluator
        if (rules.length > 0) {
            this._validateFromRules(rules, p);
            return;
        }
        // Fallback: legacy hardcoded validation for backward compatibility
        this._validateLegacy(p);
    }

    _validateFromRules(rules, p) {
        const errs = [], warns = [];
        for (const rule of rules) {
            if (!this._evaluateConditions(rule.conditions || [], p)) continue;

            if (rule.level === "error") {
                errs.push(this._formatMessage(rule.message, p, rule));
            } else if (rule.level === "warning") {
                warns.push(this._formatMessage(rule.message, p, rule));
            } else if (rule.level === "force") {
                this._applyForce(rule, p);
                warns.push(this._formatMessage(rule.message, p, rule));
            }
        }
        this.ui.validErrors = errs;
        this.ui.validWarns = warns;
    }

    _evaluateConditions(conditions, p) {
        return conditions.every((c) => {
            const val = p[c.param];
            switch (c.operator) {
                case "==":     return val === c.value;
                case "!=":     return val !== c.value;
                case ">":      return val > c.value;
                case "<":      return val < c.value;
                case ">=":     return val >= c.value;
                case "<=":     return val <= c.value;
                case "in":     return Array.isArray(c.value) && c.value.includes(val);
                case "not_in": return Array.isArray(c.value) && !c.value.includes(val);
                default:       return false;
            }
        });
    }

    _applyForce(rule, p) {
        if (!rule.force_min || !rule.min_value_map) return;
        const lookupVal = p[rule.min_value_map.param];
        const minVal = rule.min_value_map.values?.[lookupVal];
        if (minVal !== undefined && (p[rule.target_param] || 0) < minVal) {
            p[rule.target_param] = minVal;
        }
    }

    _formatMessage(template, p, rule) {
        if (!template) return "";
        return template.replace(/\{(\w+)\}/g, (_, key) => {
            if (key === "min_value" && rule?.min_value_map) {
                const lookupVal = p[rule.min_value_map.param];
                return rule.min_value_map.values?.[lookupVal] ?? key;
            }
            return p[key] ?? key;
        });
    }

    // ── TΩ Multiplicity + TΛ Layout — generic helpers за UI consumption ─

    /** Return TΩ metadata loaded with the dialog: ``{count_param?,
     *  per_instance_params?, aggregator?}`` или празен dict.
     *
     *  VK template (и бъдещи) могат да викат това вместо да hardcode-ват
     *  ``teolinoShutterCount()`` / ``teolinoShutterIndices()``.
     */
    get multiplicityMetadata() {
        const t = this.props.multiplicityTable;
        if (!t || !t.nodes) return {};
        // First decisionTableNode with first rule = canonical metadata.
        const dt = t.nodes.find(n => n && (n.type === "decisionTableNode" || n.type === "decisionTable"));
        if (!dt || !dt.content || !dt.content.rules || !dt.content.rules.length) return {};
        const rule = dt.content.rules[0];
        const out = {};
        for (const key of ["count_param", "per_instance_params", "aggregator"]) {
            const raw = rule[key];
            if (!raw) continue;
            // Strip JDM string-literal quoting
            if (typeof raw === "string" && raw.startsWith('"') && raw.endsWith('"')) {
                out[key] = raw.slice(1, -1);
            } else if (typeof raw === "string" && raw.startsWith("[")) {
                try { out[key] = JSON.parse(raw); } catch { out[key] = raw; }
            } else {
                out[key] = raw;
            }
        }
        return out;
    }

    /** Return current count for the multi-instance dimension (default 1). */
    get multiplicityCount() {
        const meta = this.multiplicityMetadata;
        if (!meta.count_param) return 1;
        const def = this._resolveParamDef(meta.count_param);
        const cur = def ? this.params[def.name] : this.params[meta.count_param];
        const n = parseInt(cur, 10);
        return Number.isFinite(n) && n > 0 ? n : 1;
    }

    /** Return TΛ layout state for a given param (DPD string ключ):
     *  ``{section?, widget_hint?, customer_visible?, submodal?}``.
     *  Празен dict (= "no hint") когато TΛ не е дефиниран или няма rule.
     *
     *  Note: layoutTable е full-graph JDM; за MVP filtering е flat (rules
     *  без conditional inputs). Бъдещи rules с conditional inputs трябва
     *  server-side `_configurator_evaluate_layout` RPC.
     */
    getLayoutForParam(paramKey) {
        const t = this.props.layoutTable;
        if (!t || !t.nodes) return {};
        const dt = t.nodes.find(n => n && (n.type === "decisionTableNode" || n.type === "decisionTable"));
        if (!dt || !dt.content || !dt.content.rules) return {};
        const target = `"${paramKey}"`;
        const rule = dt.content.rules.find(r => r && r.param === target);
        if (!rule) return {};
        const out = {};
        for (const key of ["section", "widget_hint", "submodal"]) {
            const raw = rule[key];
            if (!raw || raw === '""') continue;
            if (typeof raw === "string" && raw.startsWith('"') && raw.endsWith('"')) {
                out[key] = raw.slice(1, -1);
            } else {
                out[key] = raw;
            }
        }
        if (rule.customer_visible !== undefined && rule.customer_visible !== "") {
            out.customer_visible = rule.customer_visible === "true" || rule.customer_visible === true;
        }
        return out;
    }

    /** Convenience: param visible to customer-facing UI? Default true когато TΛ
     *  не казва нищо (backward compat). */
    isCustomerVisibleParam(paramKey) {
        const layout = this.getLayoutForParam(paramKey);
        return layout.customer_visible !== false;
    }

    // ── TΦ cascade — value propagation на onParamChange ────────────────

    /** Извикай TΦ eval синхронно и приложи cascade върху this.params.
     *
     *  Strategy:
     *  - Resolve `changed_param` to human label (DPD `string`) ако в bagaге
     *    е hash UUID name.
     *  - Server RPC: `mrp.bom._configurator_evaluate_cascade(bom_id, changed_param, context)`
     *  - За всеки target_param от резултата: ако `only_if_empty` && current
     *    не е празно/sentinel → skip; иначе set new value.
     *  - source value за `copy_from` се чете директно от текущия this.params
     *    (resolve-нат hash name).
     *
     *  Reentry guard: НЕ викай _applyCascade за TΦ-induced changes (би
     *  предизвикало loop ако rule сетва param, който е и changed_param на
     *  друг rule). За MVP — single-pass; multi-step cascade chains се
     *  решават с multiple onParamChange calls от потребителя.
     */
    async _applyCascade(changedKey, newValue) {
        if (!this.props.bomId || !this.props.cascadeTable) return;
        if (this._cascadeInProgress) return;
        this._cascadeInProgress = true;
        try {
            const def = this._resolveParamDef(changedKey);
            const changedParam = def && def.string ? def.string : changedKey;
            const ctx = this._buildAvailabilityContext();
            let cascade = {};
            try {
                cascade = await this.orm.call(
                    "mrp.bom",
                    "_configurator_evaluate_cascade",
                    [this.props.bomId, changedParam, ctx],
                );
            } catch (e) {
                console.warn("TΦ cascade eval failed:", e.message);
                return;
            }
            for (const [targetParam, spec] of Object.entries(cascade || {})) {
                const targetDef = this._resolveParamDef(targetParam);
                const targetName = targetDef ? targetDef.name : targetParam;
                const cur = this.params[targetName];
                const isEmpty = cur === undefined || cur === null
                    || cur === "" || cur === false || cur === "use_main";
                const onlyIfEmpty = spec.only_if_empty !== false;
                if (onlyIfEmpty && !isEmpty) continue;
                let nextVal;
                if (spec.derive_value !== undefined && spec.derive_value !== "") {
                    nextVal = spec.derive_value;
                } else if (spec.copy_from) {
                    const sourceDef = this._resolveParamDef(spec.copy_from);
                    const sourceName = sourceDef ? sourceDef.name : spec.copy_from;
                    nextVal = this.params[sourceName];
                }
                if (nextVal !== undefined && nextVal !== this.params[targetName]) {
                    this.params[targetName] = nextVal;
                }
            }
        } finally {
            this._cascadeInProgress = false;
        }
    }

    // ── TΠ availability — reactive UI control ───────────────────────────

    /** Schedule a debounced TΠ evaluate. `delay=0` за initial sync пас.
     *  hasAvailability — портален режим: клиентът няма достъп да прочете
     *  таблицата (record rules), но server-side meta потвърждава, че TΠ
     *  съществува (BoM или template fallback); RPC-то долу е sudo. */
    _scheduleAvailabilityEval(delay = 150) {
        if (!this.props.bomId) return;
        if (!this.props.availabilityTable && !this.props.hasAvailability) return;
        if (this._availabilityTimer) {
            clearTimeout(this._availabilityTimer);
        }
        this._availabilityTimer = setTimeout(() => {
            this._availabilityTimer = null;
            this._evaluateAvailability();
        }, delay);
    }

    /** Call server-side TΠ eval с текущия param context. */
    async _evaluateAvailability() {
        const ctx = this._buildAvailabilityContext();
        let result = {};
        try {
            result = await this.orm.call(
                "mrp.bom",
                // Public wrapper — private методи (с долна черта) не се викат
                // по RPC (Odoo блокира в call_kw).
                "configurator_evaluate_availability",
                [this.props.bomId, ctx],
            );
        } catch (e) {
            console.warn("TΠ availability eval failed:", e.message);
            return;
        }
        // Fixed-point guard: ако резултатът е идентичен с последно приложения,
        // НЕ пипай state и НЕ enforce-вай пак — убива всяка потенциална
        // re-render/re-eval верига на втората итерация (анти-цикъл).
        const resultJson = JSON.stringify(result || {});
        if (resultJson === this._lastAvailabilityJson) {
            this._enforceChain = 0; // конвергенция — auto веригата приключи
            return;
        }
        this._lastAvailabilityJson = resultJson;
        this.ui.availability = result || {};
        this._enforceAvailability();
    }

    /** Build flat context dict — multi-key resolution за rules/expressions:
     *  - hash UUID name (`f7692…`) — DPD storage key
     *  - human `string` ключ (`shutter_model`, `Height (mm)`) — DPD label
     *  - snake_case alias за base dims (`width`/`height`/`thickness`) —
     *    convention matching teolino_mrp_design_recompute._LABEL_TO_DIM.
     *    Дава експресии тип `lookup('box_by_height', shutter_model, slat_size, height)`
     *    без quirky punctuation в идентификатори.
     */
    _buildAvailabilityContext() {
        const ctx = { ...this.params };
        // VK convention: основни dimension labels → flat aliases.
        const dimAliases = {
            "Width (mm)": "width",
            "Height (mm)": "height",
            "Thickness (mm)": "thickness",
        };
        for (const def of (this.props.paramDefinition || [])) {
            if (def.string && def.name in this.params) {
                ctx[def.string] = this.params[def.name];
                const alias = dimAliases[def.string];
                if (alias) ctx[alias] = this.params[def.name];
            }
        }
        return ctx;
    }

    /** Если default_override е зададено за param и текущата стойност е
     *  извън allowed_values → auto-apply override-а. Това не trigger-ва нова
     *  TΠ eval (avoid recursion) — заа потребителя resolve-ва дилемата.
     */
    _enforceAvailability() {
        const av = this.ui.availability || {};
        let changed = false;
        for (const [paramKey, state] of Object.entries(av)) {
            if (!state || typeof state !== "object") continue;
            // Resolve param hash name ако TΠ ползва човешкия `string`
            const def = this._resolveParamDef(paramKey);
            const name = def ? def.name : paramKey;
            const cur = this.params[name];
            const allowed = state.allowed_values;
            const isInAllowed = Array.isArray(allowed)
                ? allowed.includes(cur)
                : true;
            if (state.default_override !== undefined
                && state.default_override !== ""
                && !isInAllowed) {
                this.params[name] = state.default_override;
                changed = true;
            }
        }
        if (changed) {
            this._validate();
            this._updateDescription();
            // Снапът промени контекста → още ЕДИН re-eval, за да не остане
            // stale availability (напр. снапната ос сменя allowed кутиите).
            // Анти-цикъл: fixed-point guard-ът горе спира идентични резултати,
            // а броячът ограничава data ping-pong до 3 auto итерации.
            this._enforceChain = (this._enforceChain || 0) + 1;
            if (this._enforceChain <= 3) {
                this._scheduleAvailabilityEval();
            } else {
                console.warn("TΠ enforce: ping-pong rules — спирам auto re-eval");
            }
        } else {
            this._enforceChain = 0;
        }
    }

    _resolveParamDef(key) {
        const defs = [
            ...(this.props.paramDefinition || []),
            ...((this.props.childComponents || []).flatMap(c => c.paramDefinition || [])),
        ];
        return defs.find(d => d.name === key || d.string === key);
    }

    /** Return UI state за param, merged from TΠ availability + defaults. */
    _availabilityFor(def) {
        const av = this.ui.availability || {};
        // TΠ може да адресира param-а по hash name (`f7692…`) ИЛИ по string
        // ключа (`shutter_model`); пробваме и двете.
        const state = av[def.name] || av[def.string] || {};
        return {
            visible: state.visible !== false,
            enabled: state.enabled !== false,
            allowedValues: Array.isArray(state.allowed_values)
                ? state.allowed_values
                : null,
        };
    }

    // Legacy hardcoded validation (used when no validation_rules are defined)
    _validateLegacy(p) {
        const errs = [], warns = [];
        const code = this.props.definitionCode;

        if (code === "bags") {
            if (p.bag_type === "sheet" && p.has_tie) {
                warns.push("Sheet + tie: the slitting operation will be skipped.");
            }
            if ((p.thickness || 0) < 12) {
                warns.push("Thickness < 12\u00b5m: check the resin.");
            }
        }
        if (code === "security_door") {
            const minThick = { RC1: 1.5, RC2: 2.0, RC3: 3.0, RC4: 4.0 };
            const rc = p.RC_class || "RC2";
            if (p.has_glass && rc === "RC4") {
                errs.push("Glass panel is not allowed for RC4.");
            }
            if (rc === "RC5" || rc === "RC6") {
                errs.push("RC5/RC6 require an individual project.");
            }
            const req = minThick[rc] || 0;
            if ((p.sheet_thickness || 0) < req) {
                warns.push(`${rc}: minimum thickness is ${req}mm. Value has been corrected.`);
                this.params.sheet_thickness = req;
            }
        }
        if (code === "interior_door") {
            if (p.leaf_type === "double" && p.opening !== "none") {
                errs.push("Double leaf door: the 'opening direction' must be 'none'.");
            }
            if (p.construction === "solid" && (p.width || 0) > 900) {
                warns.push("Solid wood door > 900mm: risk of warping.");
            }
        }
        this.ui.validErrors = errs;
        this.ui.validWarns = warns;
    }

    get hasErrors() {
        return this.ui.validErrors.length > 0;
    }

    /**
     * Show RuleMatrixPreview instead of 3D canvas when:
     * - No 3D models (GLB) — neither on main product nor in BoM components
     * - No SVG profiles
     * - No legacy shape builder (_buildBag, _buildShutter, etc.)
     * - At least one matrix table exists
     */
    get showRulePreview() {
        if (this._hasViewportAssets() || this._hasLegacyShape()) return false;
        const hasMatrix = !!(
            this.props.constraintTable ||
            this.props.geometryTable ||
            this.props.materialTable ||
            this.props.operationTable
        );
        return hasMatrix;
    }

    _hasViewportAssets() {
        const mainAssets = this.props.mainProductAssets || {};
        const hasMain3D = (mainAssets.models_3d || []).length > 0;
        const hasBom3D = (this.props.bomAssets || []).some(
            comp => (comp.assets?.models_3d || []).length > 0
        );
        const hasSVG = (this.props.profiles || []).length > 0
            && this.props.profiles[0]?.svg_content;
        return hasMain3D || hasBom3D || hasSVG;
    }

    _hasLegacyShape() {
        const code = this.props.definitionCode;
        return ["bags", "security_door", "roller_door", "interior_door",
                "corrugated", "shutters"].includes(code);
    }

    /**
     * Cтиснат grid layout — скрива right column когато viewport panel-ът
     * няма какво да показва (no 3D, no SVG, no legacy shape, no matrix
     * tables). Параметрите тогава заемат пълната широчина.
     */
    get hasViewport() {
        return this._hasViewportAssets()
            || this._hasLegacyShape()
            || this.showRulePreview;
    }

    // ── User interaction ────────────────────────────────────────────────

    onParamChange(key, value) {
        this.params[key] = value;
        // TΦ Cascade — синхронно (без debounce) преди TΠ: cascade-нати
        // стойности са новата база, върху която TΠ ще валидира allowed_values.
        this._applyCascade(key, value);
        this._validate();
        this._updateDescription();
        this._scheduleAvailabilityEval();

        // Find the param definition to check what changed
        const allDefs = [
            ...(this.props.paramDefinition || []),
            ...((this.props.childComponents || []).flatMap(c => c.paramDefinition || [])),
        ];
        const def = allDefs.find(d => d.name === key);
        const label = def?.string || "";

        // Opening Direction: just move hinge pivot
        if (label === "Opening Direction") {
            this._updateHingeDirection();
            return;
        }

        // Check if this param maps to a 3D model variant (e.g., Slab Type → different GLB)
        if (this._trySwapModelVariant(key, value)) return;

        // Structural changes that need full rebuild (different GLB set)
        const rebuildParams = ["Leaf Type"];
        if (rebuildParams.includes(label)) {
            this._buildModel();
        }
    }

    // Event handlers — use data-param attribute, no arrow functions
    onSliderInput(ev) {
        const key = ev.target.dataset.param;
        this.params[key] = parseFloat(ev.target.value) || 0;
        this._applyScale();
        this._updateDescription();
    }

    onSegmentClick(ev) {
        const key = ev.target.dataset.param;
        const value = ev.target.dataset.value;
        this.onParamChange(key, value);
    }

    onCheckChange(ev) {
        const key = ev.target.dataset.param;
        this.onParamChange(key, ev.target.checked);
    }

    onTextChange(ev) {
        const key = ev.target.dataset.param;
        this.onParamChange(key, ev.target.value);
    }

    _updateHingeDirection() {
        const t = this._three;
        if (!t.leafPivot) return;

        // Close leaf first
        t.leafPivot.rotation.y = 0;
        t.leafOpen = false;
        t.leafAnimating = false;

        const opening = this._getParamByLabel("Opening Direction") || "left";
        const newHingeX = opening === "right" ? t.hingeRightX : t.hingeLeftX;

        // Move pivot to new hinge
        t.leafPivot.position.x = newHingeX;

        // Reposition children: baseX was stored relative to the build-time hinge
        // (initialHingeX). Offset by the delta between new and initial hinge.
        t.leafPivot.children.forEach((child, i) => {
            const baseX = t.leafChildrenBaseX[i];
            if (baseX !== undefined) {
                child.position.x = baseX - (newHingeX - t.initialHingeX);
            }
        });
    }

    _toggleLeaf() {
        const t = this._three;
        if (!t.leafPivot) return;
        t.leafOpen = !t.leafOpen;
        const opening = this._getParamByLabel("Opening Direction") || "left";
        // Left opening: hinge on left side → rotate -90° (open inward to room)
        // Right opening: hinge on right side → rotate +90°
        const angle = opening === "right" ? -Math.PI / 2 : Math.PI / 2;
        t.leafTargetAngle = t.leafOpen ? angle : 0;
        t.leafAnimating = true;
    }

    toggleAutoRotate() {
        this.ui.autoRotate = !this.ui.autoRotate;
    }

    resetView() {
        const t = this._three;
        t.rotX = 0.2;
        t.rotY = 0;
        this.ui.autoRotate = true;
    }

    // ── Save to Odoo ────────────────────────────────────────────────────

    async onConfirm() {
        if (this.hasErrors) {
            this.notification.add("Invalid configuration. Please correct the errors.", { type: "danger" });
            return;
        }
        this.ui.saving = true;
        try {
            this._resolveUseMainSentinels();
            const lotId = await this._saveDesignLot();
            this.notification.add("Design lot created successfully.", { type: "success" });
            // onLotCreated in dialog already calls close() — don't call onClose again
            this.props.onLotCreated(lotId, { ...this.params });
        } catch (e) {
            this.notification.add(`Error: ${e.message}`, { type: "danger" });
        } finally {
            this.ui.saving = false;
        }
    }

    /**
     * Expand the "use_main" UI sentinel into the real value before the lot
     * is saved.  Sub-property params (e.g. ``color_slat``, ``color_box``)
     * may carry the literal string ``"use_main"`` to signal "inherit from
     * the matching main_X param" (e.g. ``main_color``).  PTAV resolution
     * downstream needs concrete values, so we resolve the sentinel here.
     *
     * Resolution rule: for any param ``X_Y`` whose current value is
     * ``"use_main"``, look up ``main_X``.  If it exists and is non-empty,
     * copy its value.  Generalizes the shutter case (color_* → main_color)
     * to any prefix-based cascade.
     */
    _resolveUseMainSentinels() {
        const allDefs = [
            ...(this.props.paramDefinition || []),
            ...((this.props.childComponents || []).flatMap(c => c.paramDefinition || [])),
        ];
        const byName = {};
        for (const d of allDefs) {
            if (d && d.name) byName[d.name] = d;
        }
        for (const [key, val] of Object.entries(this.params)) {
            if (val !== "use_main") continue;
            const def = byName[key];
            const parts = (def && def.string || key).split("_");
            if (parts.length < 2) continue;
            const mainKey = `main_${parts[0]}`;
            // Look both by `name` (UUID) and by `string` (human label)
            const mainDef = byName[mainKey]
                || allDefs.find(d => d && d.string === mainKey);
            if (!mainDef) continue;
            const mainVal = this.params[mainDef.name];
            if (mainVal && mainVal !== "use_main") {
                this.params[key] = mainVal;
            }
        }
    }

    async _saveDesignLot() {
        // All params go into design_params (Properties field)
        // Filter out _acc_* keys (not in definition, accessory selections)
        const designParams = {};
        for (const [k, v] of Object.entries(this.params)) {
            if (!k.startsWith("_")) {
                designParams[k] = v;
            }
        }
        const lotName = await this.orm.call(
            "stock.lot", "generate_design_lot_name", [this.props.productId]
        );
        const vals = {
            name: lotName,
            product_id: this.props.productId,
            design_param_definition_id: this.props.definitionId,
            design_params: designParams,
        };
        if (this.props.existingLotId) {
            await this.orm.write("stock.lot", [this.props.existingLotId], vals);
            return this.props.existingLotId;
        }
        const [lotId] = await this.orm.create("stock.lot", [vals]);
        return lotId;
    }

    // ── Three.js ────────────────────────────────────────────────────────

    _initThree() {
        const THREE = window.THREE;
        if (!THREE) { console.error("Three.js not loaded"); return; }
        const canvas = this.canvasRef.el;
        const t = this._three;

        t.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
        t.renderer.setClearColor(0x000000, 0);
        t.renderer.setPixelRatio(window.devicePixelRatio);

        t.scene = new THREE.Scene();
        const camDist = (this.props.profiles?.[0]?.camera_distance) || 4;
        t.camera = new THREE.PerspectiveCamera(45, 1, 0.1, 500);
        t.camera.position.set(0, 0, camDist);

        t.scene.add(new THREE.AmbientLight(0xffffff, 0.6));
        const d1 = new THREE.DirectionalLight(0xffffff, 0.8);
        d1.position.set(3, 4, 5);
        t.scene.add(d1);
        const d2 = new THREE.DirectionalLight(0xffffff, 0.3);
        d2.position.set(-3, 1, -2);
        t.scene.add(d2);

        t.group = new THREE.Group();
        t.scene.add(t.group);

        this._resizeObserver = new ResizeObserver(() => this._resize());
        this._resizeObserver.observe(canvas.parentElement);
        this._resize();

        // Raycaster for click-to-open leaf
        t.raycaster = new THREE.Raycaster();
        const mouse = new THREE.Vector2();
        let clickStart = null;

        canvas.addEventListener("mousedown", (e) => {
            t.drag = true; t.prevX = e.clientX; t.prevY = e.clientY;
            clickStart = { x: e.clientX, y: e.clientY, time: Date.now() };
        });
        this._onMouseUp = (e) => {
            if (clickStart && !t.leafAnimating) {
                const dx = Math.abs(e.clientX - clickStart.x);
                const dy = Math.abs(e.clientY - clickStart.y);
                const dt = Date.now() - clickStart.time;
                if (dx < 5 && dy < 5 && dt < 300 && t.leafPivot) {
                    const rect = canvas.getBoundingClientRect();
                    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
                    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
                    t.raycaster.setFromCamera(mouse, t.camera);
                    if (t.leafPivot) {
                        const hits = t.raycaster.intersectObjects(t.leafPivot.children, true);
                        if (hits.length > 0) {
                            this._toggleLeaf();
                        }
                    }
                }
            }
            t.drag = false;
            clickStart = null;
        };
        this._onMouseMove = (e) => {
            if (!t.drag) return;
            t.rotY += (e.clientX - t.prevX) * 0.008;
            t.rotX += (e.clientY - t.prevY) * 0.008;
            t.rotX = Math.max(-1.2, Math.min(1.2, t.rotX));
            t.prevX = e.clientX; t.prevY = e.clientY;
        };
        window.addEventListener("mouseup", this._onMouseUp);
        window.addEventListener("mousemove", this._onMouseMove);

        const animate = () => {
            if (!t.renderer) return; // stop loop after destroy
            t.animId = requestAnimationFrame(animate);
            if (this.ui.autoRotate && !t.drag) t.rotY += 0.003;
            if (t.group) {
                t.group.rotation.x = t.rotX;
                t.group.rotation.y = t.rotY;
            }
            if (t.leafPivot && t.leafAnimating) {
                const diff = t.leafTargetAngle - t.leafPivot.rotation.y;
                if (Math.abs(diff) < 0.01) {
                    t.leafPivot.rotation.y = t.leafTargetAngle;
                    t.leafAnimating = false;
                } else {
                    t.leafPivot.rotation.y += diff * 0.08;
                }
            }
            t.renderer.render(t.scene, t.camera);
        };
        animate();
    }

    _resize() {
        const t = this._three;
        if (!t || !t.renderer) return;
        const vp = this.canvasRef.el?.parentElement;
        if (!vp) return;
        const w = vp.offsetWidth || 400;
        const h = vp.offsetHeight || 380;
        t.renderer.setSize(w, h);
        t.camera.aspect = w / h;
        t.camera.updateProjectionMatrix();
    }

    _clearModel() {
        const t = this._three;
        if (!t.group) return;
        while (t.group.children.length) t.group.remove(t.group.children[0]);
    }

    _makeMesh(geo, color, opacity = 1) {
        const THREE = window.THREE;
        return new THREE.Mesh(geo, new THREE.MeshPhongMaterial({
            color, opacity, transparent: opacity < 1,
            side: THREE.DoubleSide, shininess: 30,
        }));
    }

    // ── Scale: slider changes apply scale without rebuild ──────────────

    _getParamByLabel(label) {
        // Properties use UUID names but human-readable strings.
        // Find the UUID key whose string matches the label.
        for (const def of (this.props.paramDefinition || [])) {
            if (def.string === label) {
                return this.params[def.name];
            }
        }
        return undefined;
    }

    _applyScale() {
        const t = this._three;
        if (!t.group || !t.group.children.length) return;

        const refW = this._refWidth || 900;
        const refH = this._refHeight || 2100;
        const refWall = this._refWallWidth || 100;

        const w = this._getParamByLabel("Width (mm)") || refW;
        const h = this._getParamByLabel("Height (mm)") || refH;
        const wall = this._getParamByLabel("Wall Width (mm)") || refWall;

        const bs = this._baseScale || 1;
        t.group.scale.set(
            bs * (w / refW),
            bs * (h / refH),
            bs * (wall / refWall)
        );
    }

    // ── Model building: SVG profile (primary) or legacy fallback ────────

    _applyVariantOverridesFromParams() {
        // Check all current param values against modelVariants PTAV names.
        // If any match, set the override so _buildModel uses the right GLB.
        const mv = this.props.modelVariants || {};
        for (const [productId, variants] of Object.entries(mv)) {
            for (const v of variants) {
                // Check if any param has this variant's ptav_name as value
                for (const val of Object.values(this.params)) {
                    if (val === v.ptav_name) {
                        this._variantOverrides = this._variantOverrides || {};
                        this._variantOverrides[parseInt(productId)] = v.assets;
                        break;
                    }
                }
            }
        }
    }

    async _trySwapModelVariant(paramKey, selectedValue) {
        const mv = this.props.modelVariants || {};
        for (const [productId, variants] of Object.entries(mv)) {
            const match = variants.find(v => v.ptav_name === selectedValue);
            if (match) {
                this._variantOverrides = this._variantOverrides || {};
                this._variantOverrides[parseInt(productId)] = match.assets;
                // Brief fade during rebuild to avoid visual jump
                const canvas = this.canvasRef.el;
                if (canvas) canvas.style.opacity = "0.3";
                await this._buildModel();
                if (canvas) canvas.style.opacity = "1";
                return true;
            }
        }
        return false;
    }

    async _buildModel() {
        const bomAssets = this.props.bomAssets || [];
        const glbAssets = bomAssets.filter(a => a.assets.models_3d.length > 0);

        if (glbAssets.length > 0) {
            await this._buildFromBomAssets(glbAssets);
        } else {
            const profiles = this.props.profiles || [];
            if (profiles.length > 0 && profiles[0].svg_content && profiles[0].profile_definition) {
                this._buildFromSVGProfile(profiles[0]);
            } else {
                this._buildLegacyModel();
            }
        }
    }

    async _buildFromBomAssets(assets) {
        const t = this._three;
        // Freeze camera during rebuild to prevent jumps
        const savedAutoRotate = this.ui.autoRotate;
        this.ui.autoRotate = false;

        this._clearModel();
        const THREE = window.THREE;
        if (!THREE || !THREE.GLTFLoader) {
            console.warn("GLTFLoader not available, falling back");
            this._buildLegacyModel();
            return;
        }
        const loader = new THREE.GLTFLoader();
        let frameBox = null;
        let componentIndex = 0;

        for (const component of assets) {
            // Use variant override if available (e.g., different slab GLB)
            const overrideAssets = (this._variantOverrides || {})[component.product_id];
            const glbList = overrideAssets ? overrideAssets.models_3d : component.assets.models_3d;
            const texList = overrideAssets ? overrideAssets.textures : component.assets.textures;
            for (const glb of glbList) {
                try {
                    const url = `/web/content/${glb.id}?download=true`;
                    const gltf = await new Promise((resolve, reject) => {
                        loader.load(url, resolve, undefined, reject);
                    });

                    const scene = gltf.scene;

                    // Apply texture: prefer main product texture (coating),
                    // then component texture, then default color
                    const mainTex = (this.props.mainProductAssets?.textures || []);
                    const compTex = texList;
                    const textures = mainTex.length > 0 ? mainTex : compTex;
                    if (textures.length > 0) {
                        const texUrl = `/web/content/${textures[0].id}?download=true`;
                        const texLoader = new THREE.TextureLoader();
                        const texture = await new Promise(r => texLoader.load(texUrl, r));
                        texture.wrapS = THREE.RepeatWrapping;
                        texture.wrapT = THREE.RepeatWrapping;
                        scene.traverse(child => {
                            if (child.isMesh) {
                                child.material = new THREE.MeshPhongMaterial({
                                    map: texture, side: THREE.DoubleSide, shininess: 20,
                                });
                            }
                        });
                    } else {
                        const colors = [0xd4a852, 0xb8893a, 0x8899aa, 0xc0c8d0, 0x5c3d55, 0xcccccc];
                        const color = colors[componentIndex % colors.length];
                        scene.traverse(child => {
                            if (child.isMesh && !child.material?.map) {
                                child.material = new THREE.MeshPhongMaterial({
                                    color, side: THREE.DoubleSide, shininess: 30,
                                });
                            }
                        });
                    }

                    // Detect component type and position accordingly
                    const box = new THREE.Box3().setFromObject(scene);
                    const size = box.getSize(new THREE.Vector3());

                    if (componentIndex === 0) {
                        // First component = frame (reference)
                        frameBox = box.clone();
                    } else if (frameBox) {
                        // Subsequent components = leaf/lock — position inside frame
                        const frameCenter = frameBox.getCenter(new THREE.Vector3());
                        const leafCenter = box.getCenter(new THREE.Vector3());

                        // Check if leaf is flat (one axis near zero) — needs rotation
                        const minAxis = Math.min(size.x, size.y, size.z);
                        if (size.y < 0.05 && size.x > 0.1) {
                            // Leaf is horizontal (X-wide, Y-thin) — rotate to stand up
                            scene.rotation.x = -Math.PI / 2;
                            scene.updateMatrixWorld(true);
                        } else if (size.z < 0.01 && size.x > 0.1) {
                            // Leaf is in XY plane already — just position
                        }

                        // Recalculate box after rotation
                        scene.updateMatrixWorld(true);
                        const newBox = new THREE.Box3().setFromObject(scene);
                        const newCenter = newBox.getCenter(new THREE.Vector3());
                        const newSize = newBox.getSize(new THREE.Vector3());

                        // Leaf positioning + Г-lip generation
                        const lipOverlap = (this._getParamByLabel("Lip Overlap (mm)") || 10) / 1000;
                        const lipDepth = (this._getParamByLabel("Lip Depth (mm)") || 10) / 1000;

                        // Position leaf body: centered X, bottom-aligned Y,
                        // Z = inner face of frame minus lip depth
                        scene.position.set(
                            frameCenter.x - newCenter.x,
                            frameBox.min.y - newBox.min.y,
                            frameBox.min.z - newBox.min.z - lipDepth
                        );
                        scene.updateMatrixWorld(true);

                        // Create pivot group for leaf rotation (hinge animation)
                        // Get leaf bounds AFTER positioning (world space)
                        scene.updateMatrixWorld(true);
                        const leafBox = new THREE.Box3().setFromObject(scene);
                        const leafW = leafBox.max.x - leafBox.min.x;
                        const leafH = leafBox.max.y - leafBox.min.y;
                        const leafZ = leafBox.min.z;

                        const opening = this._getParamByLabel("Opening Direction") || "left";
                        // Hinge at world position of leaf edge
                        const hingeX = opening === "right" ? leafBox.max.x : leafBox.min.x;
                        const hingeY = 0;  // pivot Y at origin (leaf rotates around vertical axis)
                        const hingeZ = leafBox.min.z;  // pivot Z at leaf front face

                        const leafPivot = new THREE.Group();
                        leafPivot.position.set(hingeX, hingeY, hingeZ);

                        // Move scene into pivot space (subtract pivot world pos from scene pos)
                        scene.position.x -= hingeX;
                        scene.position.z -= hingeZ;
                        leafPivot.add(scene);

                        // Г-lip strips
                        const lipColor = 0xb8893a;
                        const lipMat = new THREE.MeshPhongMaterial({
                            color: lipColor, side: THREE.DoubleSide, shininess: 20,
                        });

                        // Lip positions in pivot local space (subtract hingeX and hingeZ)
                        const lx = (leafBox.min.x + leafBox.max.x) / 2 - hingeX;
                        const ly = (leafBox.min.y + leafBox.max.y) / 2;

                        const topLip = new THREE.Mesh(
                            new THREE.BoxGeometry(leafW + lipOverlap * 2, lipOverlap, lipDepth), lipMat
                        );
                        topLip.position.set(lx, leafBox.max.y + lipOverlap / 2, lipDepth / 2);
                        leafPivot.add(topLip);

                        const leftLip = new THREE.Mesh(
                            new THREE.BoxGeometry(lipOverlap, leafH + lipOverlap, lipDepth), lipMat
                        );
                        leftLip.position.set(
                            leafBox.min.x - lipOverlap / 2 - hingeX,
                            ly + lipOverlap / 2,
                            lipDepth / 2
                        );
                        leafPivot.add(leftLip);

                        const rightLip = new THREE.Mesh(
                            new THREE.BoxGeometry(lipOverlap, leafH + lipOverlap, lipDepth), lipMat
                        );
                        rightLip.position.set(
                            leafBox.max.x + lipOverlap / 2 - hingeX,
                            ly + lipOverlap / 2,
                            lipDepth / 2
                        );
                        leafPivot.add(rightLip);

                        t.group.add(leafPivot);
                        t.leafPivot = leafPivot;
                        t.leafOpen = false;
                        t.leafAnimating = false;
                        // Store hinge edges for direction switching
                        t.hingeLeftX = leafBox.min.x;
                        t.hingeRightX = leafBox.max.x;
                        t.hingeZ = hingeZ;
                        t.initialHingeX = hingeX;  // hinge used at build time
                        t.leafChildrenBaseX = {};  // store original X positions
                        leafPivot.children.forEach((child, i) => {
                            t.leafChildrenBaseX[i] = child.position.x;
                        });
                    }

                    if (componentIndex === 0 || !frameBox) {
                        t.group.add(scene);
                    }
                    // leaf scene already added to leafPivot above
                    componentIndex++;
                } catch (e) {
                    console.error(`Failed to load GLB ${glb.name}:`, e);
                }
            }
        }

        // Auto-center and auto-scale
        if (t.group.children.length > 0) {
            // Move all children into an inner group for offset
            const inner = new THREE.Group();
            while (t.group.children.length) {
                inner.add(t.group.children[0]);
            }
            t.group.add(inner);

            // Measure bounds of inner
            inner.updateMatrixWorld(true);
            const box = new THREE.Box3().setFromObject(inner);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());
            const maxDim = Math.max(size.x, size.y, size.z);

            if (maxDim > 0) {
                this._baseScale = 2.3 / maxDim;
                this._refWidth = this._getParamByLabel("Width (mm)") || 900;
                this._refHeight = this._getParamByLabel("Height (mm)") || 2100;
                this._refWallWidth = this._getParamByLabel("Wall Width (mm)") || 100;

                // Offset inner to center at origin
                inner.position.set(-center.x, -center.y, -center.z);
                // Scale the outer group
                t.group.scale.setScalar(this._baseScale);
            }

            // Keep reference to inner group
            t.innerGroup = inner;
        } else {
            this._buildLegacyModel();
        }

        // Restore auto-rotate after rebuild
        this.ui.autoRotate = savedAutoRotate;
    }

    _buildFromSVGProfile(profile) {
        this._clearModel();
        const THREE = window.THREE;
        const t = this._three;
        if (!THREE || !THREE.SVGLoader) {
            console.warn("SVGLoader not available, falling back to legacy builder");
            this._buildLegacyModel();
            return;
        }

        const profileDef = profile.profile_definition || {};
        const components = profileDef.components || {};
        const dimMapping = profileDef.dimension_mapping || {};
        const defaultDepth = profile.extrude_depth || 0.05;

        const loader = new THREE.SVGLoader();
        let svgData;
        try {
            svgData = loader.parse(profile.svg_content);
        } catch (e) {
            console.error("SVG parse error:", e);
            this._buildLegacyModel();
            return;
        }

        const scaleX = this._calcDimScale(dimMapping.scale_x);
        const scaleY = this._calcDimScale(dimMapping.scale_y);

        for (const path of svgData.paths) {
            const pathId = path.userData?.node?.id || "";
            const compDef = components[pathId];
            if (!compDef) continue;

            // Visibility check
            if (!compDef.always && compDef.condition) {
                const paramVal = this.params[compDef.condition.param];
                if (paramVal !== compDef.condition.value) continue;
            }

            // Color resolution
            let colorHex = compDef.color || "#888888";
            if (compDef.color_map) {
                const mapVal = this.params[compDef.color_map.param];
                colorHex = compDef.color_map.values?.[mapVal] || colorHex;
            }
            const color = parseInt(colorHex.replace("#", ""), 16);
            const opacity = compDef.opacity || 1.0;
            const depth = compDef.extrude_depth || defaultDepth;

            const shapes = THREE.SVGLoader.createShapes(path);
            for (const shape of shapes) {
                const geo = new THREE.ExtrudeGeometry(shape, {
                    depth, bevelEnabled: false,
                });
                const mesh = this._makeMesh(geo, color, opacity);
                mesh.scale.set(scaleX, -scaleY, 1); // SVG Y-axis flip
                t.group.add(mesh);
            }
        }

        // Center the group
        if (t.group.children.length > 0) {
            const box = new THREE.Box3().setFromObject(t.group);
            const center = box.getCenter(new THREE.Vector3());
            t.group.position.sub(center);
        } else {
            // No paths rendered — show fallback
            this._buildLegacyModel();
        }
    }

    _calcDimScale(dimConfig) {
        if (!dimConfig) return 1.0;
        const paramVal = this.params[dimConfig.param] || dimConfig.reference;
        return paramVal / (dimConfig.reference || 1);
    }

    // ── Legacy builders (fallback when no SVG profile exists) ───────────

    _buildLegacyModel() {
        this._baseScale = 1;
        this._refWidth = this._getParamByLabel("Width (mm)") || 900;
        this._refHeight = this._getParamByLabel("Height (mm)") || 2100;
        this._refWallWidth = this._getParamByLabel("Wall Width (mm)") || 100;
        const code = this.props.definitionCode;
        if (code === "bags") this._buildBag();
        else if (code === "security_door") this._buildSecurityDoor();
        else if (code === "roller_door") this._buildRollerDoor();
        else if (code === "interior_door") this._buildInteriorDoor();
        else if (code === "corrugated") this._buildBox();
        else if (code === "shutters") this._buildShutter();
        else this._buildGenericBox();
    }

    _buildBag() {
        this._clearModel();
        const THREE = window.THREE; const t = this._three; const p = this.params;
        const W = (p.width || 600) / 800, H = (p.height || 800) / 800;
        const T = Math.max(0.015, (p.thickness || 25) / 2000);
        const COL = { black: 0x222222, green: 0x2d7a2d, white: 0xeeeeee, blue: 0x1a4a9a };
        const depth = p.bag_type === "sleeve" ? T * 2 : T;
        const body = this._makeMesh(new THREE.BoxGeometry(W, H, depth), COL[p.color] || 0x222222);
        t.group.add(body);
        t.group.add(new THREE.LineSegments(new THREE.EdgesGeometry(body.geometry),
            new THREE.LineBasicMaterial({ color: 0x000000, opacity: 0.12, transparent: true })));
        if (p.has_tie) {
            const band = this._makeMesh(new THREE.BoxGeometry(W * 0.6, 0.03, depth + 0.002), 0xcc3333);
            band.position.y = H / 2 + 0.02; t.group.add(band);
            const knot = this._makeMesh(new THREE.SphereGeometry(0.025, 8, 6), 0xcc3333);
            knot.position.y = H / 2 + 0.04; t.group.add(knot);
        }
        if (p.has_print) {
            const ink = this._makeMesh(new THREE.BoxGeometry(W * 0.5, H * 0.3, depth + 0.003), 0x334488, 0.9);
            ink.position.set(0, 0, depth / 2 + 0.002); t.group.add(ink);
        }
        t.group.position.set(0, -H * 0.1, 0);
    }

    _buildSecurityDoor() {
        this._clearModel();
        const THREE = window.THREE; const t = this._three; const p = this.params;
        const W = (p.width || 900) / 2000, H = (p.height || 2100) / 2000;
        const T = Math.max(0.04, (p.sheet_thickness || 2) / 50), FW = 0.04;
        const FC = { RAL: 0x5c3d55, galv: 0x8899aa, ss: 0xc0c8d0 };
        const pc = FC[p.finish] || 0x5c3d55;
        [[0,H/2,W,FW],[0,-H/2,W,FW],[-W/2,0,FW,H],[W/2,0,FW,H]].forEach(([x,y,fw,fh]) => {
            const m = this._makeMesh(new THREE.BoxGeometry(fw, fh, T), 0x444444);
            m.position.set(x, y, 0); t.group.add(m);
        });
        if (p.has_glass) {
            t.group.add(Object.assign(this._makeMesh(new THREE.BoxGeometry(W*0.5, H*0.35, 0.008), 0x88bbdd, 0.4), {position: new THREE.Vector3(0, H*0.15, 0)}));
            t.group.add(Object.assign(this._makeMesh(new THREE.BoxGeometry(W-FW*2, H*0.38, T*0.8), pc), {position: new THREE.Vector3(0, -H*0.22, 0)}));
        } else {
            t.group.add(this._makeMesh(new THREE.BoxGeometry(W-FW*2, H-FW*2, T*0.8), pc));
        }
        if (p.has_electronic_lock) {
            const el = this._makeMesh(new THREE.BoxGeometry(0.04, 0.1, T+0.015), 0x334488);
            el.position.set(W/2-FW*1.5, 0.05, 0); t.group.add(el);
        }
        t.group.position.set(0, -H * 0.45, 0);
    }

    _buildRollerDoor() {
        this._clearModel();
        const THREE = window.THREE; const t = this._three; const p = this.params;
        const W = (p.width || 2500) / 3000, H = (p.height || 2500) / 3000;
        const SC = { AL: 0xc0c8d0, steel: 0x8899aa, PC: 0xaaddee };
        const col = SC[p.slat_type] || 0xc0c8d0, sH = 0.04;
        const cnt = Math.floor(H / sH);
        for (let i = 0; i < cnt; i++) {
            const y = -H/2 + i*sH + sH/2;
            const s = this._makeMesh(new THREE.BoxGeometry(W, sH*0.88, 0.015), col);
            s.position.y = y; t.group.add(s);
        }
        const g = this._makeMesh(new THREE.BoxGeometry(0.025, H, 0.025), 0x444444);
        g.position.x = -W/2-0.015; t.group.add(g);
        const g2 = g.clone(); g2.position.x = W/2+0.015; t.group.add(g2);
        if (p.drive_type === "electric") {
            const m = this._makeMesh(new THREE.BoxGeometry(0.15, 0.1, 0.1), 0x334466);
            m.position.set(0, H/2+0.07, 0); t.group.add(m);
        }
        t.group.position.set(0, -H * 0.05, 0);
    }

    _buildInteriorDoor() {
        this._clearModel();
        const THREE = window.THREE; const t = this._three; const p = this.params;
        const mult = p.leaf_type === "double" ? 2 : 1;
        const W = ((p.width || 900) / 2000) * mult, H = (p.height || 2100) / 2000;
        const FC = { veneer: 0xd4a852, lacquer: 0xf0ead6, RAL: 0x5c3d55, foil: 0xcccccc };
        const col = FC[p.finish] || 0xd4a852, T = 0.04;
        const fr = this._makeMesh(new THREE.BoxGeometry(W, H, T), col);
        t.group.add(fr);
        t.group.add(new THREE.LineSegments(new THREE.EdgesGeometry(fr.geometry),
            new THREE.LineBasicMaterial({ color: 0x000000, opacity: 0.15, transparent: true })));
        if (p.has_glass_panel) {
            const gl = this._makeMesh(new THREE.BoxGeometry(W*0.45, H*0.3, T+0.005), 0x88bbdd, 0.45);
            gl.position.set(0, H*0.2, 0); t.group.add(gl);
        }
        const h = this._makeMesh(new THREE.BoxGeometry(0.012, 0.1, 0.012), 0xaa9944);
        h.position.set(W/2-0.05, 0, T/2+0.006); t.group.add(h);
        if (p.leaf_type === "double") {
            t.group.add(new THREE.Line(
                new THREE.BufferGeometry().setFromPoints([
                    new THREE.Vector3(0, -H/2, T/2+0.001), new THREE.Vector3(0, H/2, T/2+0.001)]),
                new THREE.LineBasicMaterial({ color: 0x888888, opacity: 0.4, transparent: true })));
        }
        t.group.position.set(0, -H * 0.4, 0);
    }

    _buildShutter() {
        // Roller shutter ("Щора Standard" и др. варианти от mrp_design_matrix_shutters).
        // Геометрия от долу нагоре: terminal slat → regular slats stack → brush → box (top).
        // Параметри се четат от this.params (имената идват от shutters DPD set).
        this._clearModel();
        const THREE = window.THREE; const t = this._three; const p = this.params;
        const W = (p.width || 1000) / 3000;
        const H = (p.height || 1500) / 3000;
        const BH = (parseInt(p.box_size, 10) || 165) / 3000;
        const SH = (parseInt(p.slat_size, 10) || 40) / 3000;
        const GW = 0.022, capW = 0.005, boxDepth = BH * 1.1;
        const toColor = (v, fb) => {
            if (!v) return fb;
            try { return new THREE.Color(v).getHex(); } catch (_) { return fb; }
        };
        const cBox = toColor(p.color_box || p.main_color, 0xeeeeee);
        const cSlat = toColor(p.color_slat || p.main_color, 0xdddddd);
        const cTerminal = toColor(p.color_terminal || p.color_slat || p.main_color, 0xcccccc);
        const cGuide = toColor(p.color_guide || p.main_color, 0x888888);
        const cEndcap = toColor(p.color_endcap, 0x444444);
        const cBrush = toColor(p.color_brush, 0x333333);
        const cRope = toColor(p.color_rope, 0x555555);
        const cShirit = toColor(p.color_shirit, 0x999999);
        const cMotor = 0x224488;
        const cSafety = toColor(p.color_safety, 0xff8800);

        // Box (top)
        const boxY = H / 2 - BH / 2;
        const box = this._makeMesh(new THREE.BoxGeometry(W + GW * 2, BH, boxDepth), cBox);
        box.position.set(0, boxY, 0);
        t.group.add(box);
        t.group.add(new THREE.LineSegments(
            new THREE.EdgesGeometry(box.geometry),
            new THREE.LineBasicMaterial({ color: 0x000000, opacity: 0.15, transparent: true })));

        // Box endcaps (left/right)
        const capL = this._makeMesh(new THREE.BoxGeometry(capW, BH, boxDepth + 0.002), cEndcap);
        capL.position.set(-(W / 2 + GW + capW / 2), boxY, 0);
        t.group.add(capL);
        const capR = capL.clone(); capR.position.x = W / 2 + GW + capW / 2;
        t.group.add(capR);

        // Side guides (rails)
        const slatStartY = boxY - BH / 2;
        const guideH = slatStartY - (-H / 2);
        const guideY = (-H / 2 + slatStartY) / 2;
        const guideL = this._makeMesh(new THREE.BoxGeometry(GW, guideH, 0.025), cGuide);
        guideL.position.set(-(W / 2 + GW / 2), guideY, 0);
        t.group.add(guideL);
        const guideR = guideL.clone(); guideR.position.x = W / 2 + GW / 2;
        t.group.add(guideR);

        // Brush at bottom of box (place where slats exit)
        const brush = this._makeMesh(new THREE.BoxGeometry(W, 0.004, 0.018), cBrush);
        brush.position.set(0, slatStartY - 0.002, 0);
        t.group.add(brush);

        // Terminal (bottom slat — debelijo от обикновените)
        const terminalH = SH * 1.2;
        const termY = -H / 2 + terminalH / 2;
        const term = this._makeMesh(new THREE.BoxGeometry(W, terminalH, 0.018), cTerminal);
        term.position.set(0, termY, 0);
        t.group.add(term);

        // Regular slats stacked between terminal-top и brush-bottom
        const slatsAreaTop = slatStartY - 0.004;
        const slatsAreaBot = termY + terminalH / 2;
        const nSlats = Math.max(0, Math.floor((slatsAreaTop - slatsAreaBot) / SH));
        for (let i = 0; i < nSlats; i++) {
            const y = slatsAreaBot + i * SH + SH / 2;
            const s = this._makeMesh(new THREE.BoxGeometry(W, SH * 0.92, 0.014), cSlat);
            s.position.set(0, y, 0);
            t.group.add(s);
        }

        // Control element (motor inside box / rope или shirit hanging)
        if (p.control_type === "motor") {
            const motor = this._makeMesh(
                new THREE.CylinderGeometry(BH * 0.35, BH * 0.35, W * 0.15, 12),
                cMotor);
            motor.rotation.z = Math.PI / 2;
            motor.position.set(W / 2 - W * 0.1, boxY, 0);
            t.group.add(motor);
            // safety badge (cylinder disc) — visual hint за motor_safety O-variant
            const safety = this._makeMesh(
                new THREE.CylinderGeometry(BH * 0.12, BH * 0.12, 0.005, 16),
                cSafety);
            safety.rotation.x = Math.PI / 2;
            safety.position.set(W / 2 - W * 0.1, boxY, boxDepth / 2 + 0.003);
            t.group.add(safety);
        } else if (p.control_type === "rope") {
            const rope = this._makeMesh(
                new THREE.BoxGeometry(0.006, H * 0.4, 0.006), cRope);
            rope.position.set(W / 2 + GW + 0.012, 0, 0.015);
            t.group.add(rope);
        } else if (p.control_type === "shirit") {
            const shirit = this._makeMesh(
                new THREE.BoxGeometry(0.012, H * 0.4, 0.002), cShirit);
            shirit.position.set(W / 2 + GW + 0.014, 0, 0.015);
            t.group.add(shirit);
        }

        // Multi-shutter separators (central endcaps между съседни щори)
        const sc = parseInt(p.shutter_count, 10) || 1;
        if (sc > 1) {
            const cCentral = toColor(p.color_central_endcap, 0x666666);
            const stepW = W / sc;
            for (let i = 1; i < sc; i++) {
                const x = -W / 2 + i * stepW;
                const sep = this._makeMesh(
                    new THREE.BoxGeometry(0.004, H * 0.95, 0.022),
                    cCentral);
                sep.position.set(x, 0, 0);
                t.group.add(sep);
            }
        }

        t.group.position.set(0, -H * 0.05, 0);
    }

    _buildBox() {
        this._clearModel();
        const THREE = window.THREE; const t = this._three; const p = this.params;
        const L = (p.box_l||400)/600, W = (p.box_w||300)/600, D = (p.box_d||200)/600;
        const body = this._makeMesh(new THREE.BoxGeometry(L, D, W), 0xd4a852);
        t.group.add(body);
        t.group.add(new THREE.LineSegments(new THREE.EdgesGeometry(body.geometry),
            new THREE.LineBasicMaterial({ color: 0xb8893a, opacity: 0.4, transparent: true })));
        const flap = this._makeMesh(new THREE.BoxGeometry(L, D*0.48, 0.01), 0xb8893a, 0.85);
        flap.position.y = D/2+D*0.24; t.group.add(flap);
        if (p.has_print) {
            const ink = this._makeMesh(new THREE.BoxGeometry(L*0.5, D*0.35, 0.008), 0x334488, 0.85);
            ink.position.set(0, 0, W/2+0.005); t.group.add(ink);
        }
        t.group.position.set(0, -D * 0.4, 0);
    }

    _buildGenericBox() {
        this._clearModel();
        const THREE = window.THREE; const t = this._three;
        const box = this._makeMesh(new THREE.BoxGeometry(1.2, 1.8, 0.08), 0x888888);
        t.group.add(box);
        t.group.add(new THREE.LineSegments(new THREE.EdgesGeometry(box.geometry),
            new THREE.LineBasicMaterial({ color: 0x444444, opacity: 0.3, transparent: true })));
    }

    _destroyThree() {
        try {
            const t = this._three;
            if (t.animId) cancelAnimationFrame(t.animId);
            t.animId = null;
            if (t.renderer) t.renderer.dispose();
            t.renderer = null;
            if (this._resizeObserver) this._resizeObserver.disconnect();
            // Clean up window event listeners added in _initThree
            if (this._onMouseUp) window.removeEventListener("mouseup", this._onMouseUp);
            if (this._onMouseMove) window.removeEventListener("mousemove", this._onMouseMove);
            // Изчисти pending TΠ eval ако има
            if (this._availabilityTimer) {
                clearTimeout(this._availabilityTimer);
                this._availabilityTimer = null;
            }
        } catch (e) {
            console.warn("Three.js cleanup error:", e);
        }
    }

    // ── Overlay panel ──────────────────────────────────────────────────

    toggleOverlay() {
        this.ui.overlayOpen = !this.ui.overlayOpen;
        if (this.ui.overlayOpen) {
            const vp = this.canvasRef.el?.parentElement;
            this.ui.overlayHeight = vp ? vp.offsetHeight : 400;
        } else {
            this.ui.overlayHeight = 24;
        }
    }

    onOverlayHandleDrag(ev) {
        if (ev.button !== 0) return;
        ev.preventDefault();
        const overlay = this.overlayRef.el;
        const vp = this.canvasRef.el?.parentElement;
        if (!overlay || !vp) return;

        const vpH = vp.offsetHeight;
        const startY = ev.clientY;
        const startH = overlay.offsetHeight;
        let moved = false;

        overlay.style.transition = "none";

        const onMove = (e) => {
            moved = true;
            const delta = startY - e.clientY;
            const h = Math.max(44, Math.min(vpH * 0.85, startH + delta));
            overlay.style.height = h + "px";
        };
        const onUp = () => {
            window.removeEventListener("mousemove", onMove);
            window.removeEventListener("mouseup", onUp);
            overlay.style.transition = "";

            const finalH = overlay.offsetHeight;
            if (finalH < 60) {
                this.ui.overlayHeight = 24;
                this.ui.overlayOpen = false;
            } else {
                this.ui.overlayHeight = finalH;
                this.ui.overlayOpen = true;
            }

            if (!moved) {
                this.toggleOverlay();
            }
        };
        window.addEventListener("mousemove", onMove);
        window.addEventListener("mouseup", onUp);
    }

    onAccessorySelect(ev) {
        const paramKey = ev.currentTarget.dataset.param;
        const value = ev.currentTarget.dataset.variant;
        this.onParamChange(paramKey, value);
    }

    _updateDescription() {
        const parts = [];
        for (const def of (this.props.paramDefinition || [])) {
            const val = this.params[def.name];
            if (val === undefined || val === "") continue;
            if (def.type === "float" && def.string?.includes("mm")
                && !def.string.includes("Wall") && !def.string.includes("Lip")
                && !def.string.includes("Каса")) {
                parts.push(`${def.string}: ${val}`);
            } else if (def.type === "selection" && def.selection) {
                const opt = def.selection.find(s => s[0] === val);
                if (opt) parts.push(`${def.string}: ${opt[1]}`);
            }
        }
        for (const child of (this.props.childComponents || [])) {
            for (const def of (child.paramDefinition || [])) {
                if (def.type !== "selection" || !def.selection) continue;
                const val = this.params[def.name];
                if (val === undefined) continue;
                const opt = def.selection.find(s => s[0] === val);
                if (opt) parts.push(`${child.definitionName}: ${opt[1]}`);
            }
        }
        this.ui.description = parts.join(" | ");
    }

    get overlayGroups() {
        return (this.props.accessoryVariants || []).filter(g => g.definitionParamKey).map(group => {
            const paramKey = group.definitionParamKey;
            const selectedVal = this.params[paramKey];
            return {
                ...group,
                paramKey,
                variants: group.variants.map(v => ({
                    ...v,
                    variantStr: v.ptav_name,
                    imageUrl: `/web/content/${v.textures[0].id}?download=true`,
                    selected: v.ptav_name === selectedVal,
                })),
            };
        });
    }

    // ── Computed display helpers ─────────────────────────────────────────

    get displayParams() {
        // Exclude child component params (shown in their own sections)
        const childNames = new Set(
            (this.props.childComponents || [])
                .flatMap(c => (c.paramDefinition || []).map(d => d.name))
        );
        return this.props.paramDefinition
            .filter(def => !childNames.has(def.name))
            .map(def => this._decorateParam(def))
            .filter(def => def.tpiVisible);
    }

    /** Mix TΠ state into a param definition for the template:
     *  - ``tpiVisible`` (bool) — false => template филтрира param-а навън
     *  - ``tpiEnabled`` (bool) — false => input disabled
     *  - ``selection`` се филтрира до ``allowed_values`` ако са зададени
     */
    _decorateParam(def) {
        const state = this._availabilityFor(def);
        let selection = def.selection;
        if (state.allowedValues && Array.isArray(def.selection)) {
            selection = def.selection.filter(
                opt => state.allowedValues.includes(opt[0])
            );
        }
        return {
            ...def,
            value: this.params[def.name],
            selection,
            tpiVisible: state.visible,
            tpiEnabled: state.enabled,
        };
    }

    get childDisplayParams() {
        // Returns child component params with current values for Fine Tuning.
        // Child params също минават през TΠ decorator-а.
        const children = this.props.childComponents || [];
        return children.map(child => ({
            ...child,
            params: (child.paramDefinition || []).map(def => {
                const decorated = this._decorateParam(def);
                const fallback = def.type === 'float'
                    ? (parseFloat(def.default) || 0)
                    : (def.default || '');
                return {
                    ...decorated,
                    value: this.params[def.name] !== undefined
                        ? this.params[def.name]
                        : fallback,
                };
            }).filter(p => p.tpiVisible),
        }));
    }

    get lotPreview() {
        return Object.entries(this.params)
            .map(([k, v]) => `${k}: ${v}`)
            .join("\n");
    }
}

registry.category("fields").add("design_configurator", {
    component: DesignConfiguratorWidget,
});
