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
import { debounce } from "@web/core/utils/timing";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { RuleMatrixPreview } from "@mrp_design_matrix/components/rule_matrix_preview/rule_matrix_preview";
import { evaluateT0 } from "@mrp_design_matrix/components/rule_matrix_preview/t0_evaluate";

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
        // Generic level gating: {param_string: "sales"|"technical"|"production"}
        // + active level. Empty level = full configurator (show everything).
        paramLevels: { type: Object, optional: true },
        // D1: семантични роли {param_string → role} (width|height|wall_width|
        // opening_direction|rebuild|numeric|operation|hide_in_description|…)
        // — UI-ът резолвва параметри по РОЛЯ; label lookup остава fallback.
        paramRoles: { type: Object, optional: true },
        level: { type: String, optional: true },
        validationRules: { type: Array, optional: true },
        profiles: { type: Array, optional: true },
        bomAssets: { type: Array, optional: true },
        costData: { type: Object, optional: true },
        mainProductAssets: { type: Object, optional: true },
        childComponents: { type: Array, optional: true },
        accessoryVariants: { type: Array, optional: true },
        // Backend-derived toggle accessories (от BoM-а през RPC): [{param_name,label}]
        accessoryToggles: { type: Array, optional: true },
        // Избираеми операции от BoM-а: [{wcId, name}]
        operationChoices: { type: Array, optional: true },
        // Атрибути на полуфабрикатите (цвят/покритие/материал/мотив) от BoM-а
        componentAttributes: { type: Array, optional: true },
        modelVariants: { type: Object, optional: true },
        constraintTable: { type: [Object, { value: false }], optional: true },
        geometryTable: { type: [Object, { value: false }], optional: true },
        materialTable: { type: [Object, { value: false }], optional: true },
        operationTable: { type: [Object, { value: false }], optional: true },
        bomLines: { type: Array, optional: true },
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

        // Динамична себестойност (ниво cost): реактивно състояние + debounced
        // преизчисляване при смяна на параметър.
        this.cost = useState({ data: this.props.costData || {} });
        this._recomputeCostDebounced = debounce(
            this._recomputeCost.bind(this), 400
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
        });

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
            // Only init Three.js when NOT in rule preview mode AND visual level.
            // Technical/production нивата не зареждат 3D/снимки — нямат място там.
            if (!this.showRulePreview && this.show3D) {
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
            // Първоначална калкулация по живите параметри (sales + cost).
            if (this.props.level !== "technical" && this.props.level !== "production") {
                this._recomputeCost();
            }
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
            "matrix_material_choices",
            "matrix_operation_choices",
            "matrix_component_attrs",
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
        // Възстанови запомнените избори (иначе при повторно отваряне се губят):
        // материал-избори (choice_*) + компонент-атрибути цвят/мотив (cattr_*).
        const mc = lot.matrix_material_choices;
        if (mc && typeof mc === "object") Object.assign(this.params, mc);
        const ca = lot.matrix_component_attrs;
        if (ca && typeof ca === "object") Object.assign(this.params, ca);
        // избрани операции (op_*).
        for (const opKey of (lot.matrix_operation_choices || [])) {
            this.params["op_" + opKey] = true;
        }
    }

    // ── Data-driven validation ──────────────────────────────────────────

    _validate() {
        const rules = this.props.validationRules || [];
        const p = this.params;

        // If rules are defined, use generic evaluator
        if (rules.length > 0) {
            this._validateFromRules(rules, p);
        } else {
            // Fallback: legacy hardcoded validation for backward compatibility
            this._validateLegacy(p);
        }
        // T0 constraints (GoRules) — оценяват се на ВСИЧКИ нива, вкл. sales,
        // не само при MO. Грешките блокират потвърждението.
        this._validateT0();
    }

    _validateT0() {
        if (!this.props.constraintTable) return;
        const t0 = evaluateT0(this._buildDesignContext(), this.props.constraintTable);
        if (!t0 || !t0.results) return;
        for (const r of t0.results) {
            if (!r.matched) continue;
            if (r.level === "error") {
                this.ui.validErrors.push(r.message);
            } else if (r.level === "warning") {
                this.ui.validWarns.push(r.message);
            }
        }
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

    // Legacy hardcoded validation (used when no validation_rules are defined)
    _validateLegacy(p) {
        const errs = [], warns = [];
        const code = this.props.definitionCode;

        if (code === "bags") {
            if (p.bag_type === "sheet" && p.has_tie) {
                warns.push(_t("Sheet + tie: the slitting operation will be skipped."));
            }
            if ((p.thickness || 0) < 12) {
                warns.push("Thickness < 12\u00b5m: check the resin.");
            }
        }
        if (code === "security_door") {
            const minThick = { RC1: 1.5, RC2: 2.0, RC3: 3.0, RC4: 4.0 };
            const rc = p.RC_class || "RC2";
            if (p.has_glass && rc === "RC4") {
                errs.push(_t("Glass panel is not allowed for RC4."));
            }
            if (rc === "RC5" || rc === "RC6") {
                errs.push(_t("RC5/RC6 require an individual project."));
            }
            const req = minThick[rc] || 0;
            if ((p.sheet_thickness || 0) < req) {
                warns.push(_t("%s: minimum thickness is %smm. Value has been corrected.", rc, req));
                this.params.sheet_thickness = req;
            }
        }
        if (code === "interior_door") {
            if (p.leaf_type === "double" && p.opening !== "none") {
                errs.push(_t("Double leaf door: the 'opening direction' must be 'none'."));
            }
            if (p.construction === "solid" && (p.width || 0) > 900) {
                warns.push(_t("Solid wood door > 900mm: risk of warping."));
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
     * - At least one matrix table exists
     */
    get showRulePreview() {
        const mainAssets = this.props.mainProductAssets || {};
        const hasMain3D = (mainAssets.models_3d || []).length > 0;
        const hasBom3D = (this.props.bomAssets || []).some(
            comp => (comp.assets?.models_3d || []).length > 0
        );
        const has3D = hasMain3D || hasBom3D;
        const hasSVG = (this.props.profiles || []).length > 0
            && this.props.profiles[0]?.svg_content;
        const hasMatrix = !!(
            this.props.constraintTable ||
            this.props.geometryTable ||
            this.props.materialTable ||
            this.props.operationTable
        );
        return !has3D && !hasSVG && hasMatrix;
    }

    // ── User interaction ────────────────────────────────────────────────

    onParamChange(key, value) {
        this.params[key] = value;
        this._validate();
        this._updateDescription();

        // Преизчисли калкулацията при смяна на параметър (debounced) —
        // и на sales (жива калкулация), и на cost ниво.
        this._recomputeCostDebounced();

        // Find the param definition to check what changed
        const allDefs = [
            ...(this.props.paramDefinition || []),
            ...((this.props.childComponents || []).flatMap(c => c.paramDefinition || [])),
        ];
        const def = allDefs.find(d => d.name === key);
        const label = def?.string || "";

        // Посока на отваряне: само мести шарнирния pivot.
        // D1: роля opening_direction (данни); label fallback за заварени.
        const role = this._roleOf(label);
        if (role === "opening_direction"
            || label === "Opening Direction" || label === "Посока") {
            this._updateHingeDirection();
            return;
        }

        // Цвят/покритие на компонент (ключ cattr_<lineId>_<attrId>): пребоядисай
        // 3D-то веднага, без пълен rebuild. _applyComponentColors() чете само
        // isColor атрибутите (мотивът е отделен GLB механизъм), има guard за
        // незаредени mesh-ове → евтино и безопасно да се вика при всяка cattr_ смяна.
        // (Багфикс: изборът на цвят преизчисляваше цената, но не пречертаваше вратата.)
        if (key.startsWith("cattr_")) {
            this._applyComponentColors();
            return;
        }

        // Check if this param maps to a 3D model variant (e.g., Slab Type → different GLB)
        if (this._trySwapModelVariant(key, value)) return;

        // Structural changes that need full rebuild (different GLB set).
        // D1: роля rebuild (данни); label fallback за заварени.
        const rebuildParams = ["Leaf Type"];
        if (role === "rebuild" || rebuildParams.includes(label)) {
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

    onSelectChange(ev) {
        this.onParamChange(ev.target.dataset.param, ev.target.value);
    }

    // Размерни/числови char-параметри → рендират се с number input.
    isNumericParam(label) {
        // D1: роля numeric (данни) first; хардкоднатият сет остава fallback
        // за заварените врати-дефиниции без param_roles.
        if (this._roleOf(label) === "numeric") return true;
        const num = new Set([
            "H", "B", "BA", "BP", "Т", "T", "Ниво", "Луфт",
            "Hкаса", "Вкаса", "Пяна (бр)", "Брой карти", "Пас.шип (бр)",
            "Мастър ключ бр", "Метална конструкция (m)", "Монтаж в дни",
        ]);
        return num.has((label || "").trim());
    }

    _updateHingeDirection() {
        const t = this._three;
        if (!t.leafPivot) return;

        // Close leaf first
        t.leafPivot.rotation.y = 0;
        t.leafOpen = false;
        t.leafAnimating = false;

        const opening = this._getOpeningDirection();
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
        const opening = this._getOpeningDirection();
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
            this.notification.add(_t("Invalid configuration. Please correct the errors."), { type: "danger" });
            return;
        }
        this.ui.saving = true;
        try {
            const lotId = await this._saveDesignLot();
            this.notification.add(_t("Design lot created successfully."), { type: "success" });
            // onLotCreated in dialog already calls close() — don't call onClose again
            this.props.onLotCreated(lotId, { ...this.params });
        } catch (e) {
            this.notification.add(_t("Error: %s", e.message), { type: "danger" });
        } finally {
            this.ui.saving = false;
        }
    }

    async _saveDesignLot() {
        // All params go into design_params (Properties field).
        // Filter out _acc_* keys; choice_* keys (material choices) go into a
        // separate Json field (Properties би изхвърлило ключове извън дефиницията).
        const designParams = {};
        const materialChoices = {};
        const operationChoices = [];
        const componentAttrs = {};
        for (const [k, v] of Object.entries(this.params)) {
            if (k.startsWith("_")) continue;
            if (k.startsWith("choice_")) {
                materialChoices[k] = v;
            } else if (k.startsWith("op_")) {
                if (v) operationChoices.push(k.slice(3));
            } else if (k.startsWith("cattr_")) {
                if (v) componentAttrs[k] = v;
            } else {
                designParams[k] = v;
            }
        }
        const vals = {
            product_id: this.props.productId,
            design_param_definition_id: this.props.definitionId,
            design_params: designParams,
            matrix_material_choices: materialChoices,
            matrix_operation_choices: operationChoices,
            matrix_component_attrs: componentAttrs,
        };
        // Редакция на съществуващ лот: НЕ пипай името (не преименувай, не хаби
        // сериен номер) — само обнови параметрите.
        if (this.props.existingLotId) {
            await this.orm.write("stock.lot", [this.props.existingLotId], vals);
            return this.props.existingLotId;
        }
        // Нов лот: името се иска от сървъра, като му се подава и КОМБИНАЦИЯТА —
        // продукт с префиксен шаблон дава своя поредица за всяка комбинация,
        // а без шаблон отговорът пада към категорийната/продуктовата.
        vals.name = await this.orm.call(
            "stock.lot", "generate_design_lot_name",
            [this.props.productId, designParams, this.props.definitionId]
        );
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
        // D3: cap 2 — uncapped devicePixelRatio (3-4 на телефони) взривява
        // framebuffer-а → GPU OOM → блед/черен canvas (Android бъгът).
        t.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        // D3: context-loss recovery — мобилният GPU дропва контекста при
        // паметов натиск/таб суич; без handler canvas-ът остава мъртъв.
        this._onCtxLost = (ev) => {
            ev.preventDefault();
            console.warn("WebGL context lost — awaiting restore");
        };
        this._onCtxRestored = () => {
            console.info("WebGL context restored — rebuilding model");
            this._buildModel();
        };
        canvas.addEventListener("webglcontextlost", this._onCtxLost, false);
        canvas.addEventListener("webglcontextrestored", this._onCtxRestored, false);

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
        while (t.group.children.length) {
            const child = t.group.children[0];
            t.group.remove(child);
            this._disposeObject(child);
        }
    }

    // D3: GPU памет СЕ ОСВОБОЖДАВА явно — three.js не прави GC на GPU
    // ресурси; без dispose всяка смяна на мотив/rebuild трупаше geometry/
    // texture в VRAM до блед/черен canvas (особено на таблет/телефон).
    _disposeObject(root) {
        if (!root) return;
        root.traverse ? root.traverse((o) => this._disposeOne(o))
                      : this._disposeOne(root);
    }

    _disposeOne(o) {
        if (o.geometry) o.geometry.dispose();
        const mats = Array.isArray(o.material) ? o.material
                                               : (o.material ? [o.material] : []);
        for (const m of mats) {
            for (const key of ["map", "normalMap", "roughnessMap",
                               "metalnessMap", "aoMap", "emissiveMap",
                               "bumpMap", "alphaMap", "envMap"]) {
                if (m[key] && m[key].dispose) m[key].dispose();
            }
            m.dispose();
        }
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

    // D1: роля на параметър по label (от param_roles канала на дефиницията).
    _roleOf(label) {
        return (this.props.paramRoles || {})[label];
    }

    // D1: стойност на параметър по СЕМАНТИЧНА РОЛЯ (width/height/…) — данни,
    // не код. Fallback-ът по label остава при викащите (заварени дефиниции
    // без param_roles).
    _getParamByRole(role) {
        const roles = this.props.paramRoles || {};
        for (const def of (this.props.paramDefinition || [])) {
            if (roles[def.string] === role) {
                return this.params[def.name];
            }
        }
        return undefined;
    }

    // Посока на отваряне → нормализирано "left"/"right" за 3D логиката.
    // Роля opening_direction (нови дефиниции); fallback: label "Посока"
    // (Лява/Дясна) или "Opening Direction" (left/right) — заварени врати.
    _getOpeningDirection() {
        const raw = this._getParamByRole("opening_direction")
            ?? this._getParamByLabel("Посока")
            ?? this._getParamByLabel("Opening Direction");
        return /дясн|right/i.test(String(raw || "")) ? "right" : "left";
    }

    _applyScale() {
        const t = this._three;
        if (!t.group || !t.group.children.length) return;

        const refW = this._refWidth || 900;
        const refH = this._refHeight || 2100;
        const refWall = this._refWallWidth || 100;

        // D1: роля first (width/height/wall_width); label fallback за заварени
        // роля first; ТЕРМИНАЛЕН || (не ??): дименсия 0/'' не е легитимна →
        // пада на референтния дефолт (?? би колабирал модела при scale 0).
        const w = this._getParamByRole("width")
            || this._getParamByLabel("Width (mm)") || refW;
        const h = this._getParamByRole("height")
            || this._getParamByLabel("Height (mm)") || refH;
        const wall = this._getParamByRole("wall_width")
            || this._getParamByLabel("Wall Width (mm)") || refWall;

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

    // Избраният Цвят за компонент (BoM ред) → {html_color, image} или null.
    // Ползва се при ЗАРЕЖДАНЕ на модела, за да се боядиса крилото/касата.
    _selectedColorForLine(lineId) {
        const comp = (this.props.componentAttributes || [])
            .find(c => c.bomLineId === lineId);
        if (!comp) return null;
        // Само „Цвят" (цвят/покритие) → боядисва геометрията. Мотивът НЕ се
        // рисува като текстура (даваше „два декора" върху F01-релефа) — той е
        // GLB-суап на крилото (отделен механизъм по мотив).
        // D1: кандидати = isColor атрибутите (данни от design_role); legacy
        // имената подреждат приоритета (вън преди общ) за заварените врати.
        const colorAttrs = (comp.attributes || []).filter(a => a.isColor);
        const ordered = [
            ...colorAttrs.filter(a => a.name === "Цвят (вън)"),
            ...colorAttrs.filter(a => a.name !== "Цвят (вън)"),
        ];
        for (const attr of ordered) {
            const sel = this.params["cattr_" + lineId + "_" + attr.attrId];
            if (!sel) continue;
            const v = (attr.values || []).find(x => String(x.id) === String(sel));
            if (v && (v.image || v.html_color)) {
                return { html_color: v.html_color, image: v.image };
            }
        }
        return null;
    }

    // Статичен slab GLB URL за избрания „Мотив" (F01-F41) на компонента, или
    // null (напр. „Без мотив" → дефолтния GLB). F28 липсва → дефолт.
    _motifGlbUrlForLine(lineId) {
        const comp = (this.props.componentAttributes || [])
            .find(c => c.bomLineId === lineId);
        if (!comp) return null;
        // D1: isMotif (design_role) first; името е fallback за заварени данни.
        const attr = (comp.attributes || []).find(a => a.isMotif)
            || (comp.attributes || []).find(a => a.name === "Мотив");
        if (!attr) return null;
        const sel = this.params["cattr_" + lineId + "_" + attr.attrId];
        if (!sel) return null;
        const v = (attr.values || []).find(x => String(x.id) === String(sel));
        const name = v && v.name ? v.name.trim() : "";
        if (!/^F\d+$/.test(name) || name === "F28") return null;
        return "/sale_design_configurator/static/src/models/slabs/" + name + ".glb";
    }

    // Прилага избрания Цвят на всеки компонент върху неговите 3D мрежи:
    // html_color → плътен material.color; image → текстура (декор).
    _applyComponentColors() {
        const t = this._three;
        const THREE = window.THREE;
        if (!t.componentMeshes || !THREE) return;
        // ЗАМЕНЯ материала с чист дифузен MeshPhongMaterial — GLB-материалите
        // често са металически (metalness) и сетването на color НЕ личи без
        // environment map. Замяната гарантира видим цвят/текстура.
        for (const cg of this.componentGroups) {
            const meshes = t.componentMeshes[cg.lineId];
            const vis = this._selectedColorForLine(cg.lineId);
            if (!meshes || !meshes.length || !vis) continue;
            // Картинка (Мотив/декор) има приоритет пред плътен цвят.
            if (!vis.image && vis.html_color) {
                const col = new THREE.Color(vis.html_color);
                for (const m of meshes) {
                    m.material = new THREE.MeshPhongMaterial({
                        color: col, side: THREE.DoubleSide, shininess: 25,
                    });
                }
            } else if (vis.image) {
                const loader = new THREE.TextureLoader();
                loader.load(vis.image, (tex) => {
                    tex.wrapS = THREE.RepeatWrapping;
                    tex.wrapT = THREE.RepeatWrapping;
                    // Среден цвят (за мрежи без UV — напр. крилото F01.glb).
                    let avg = new THREE.Color(0xb8893a);
                    try {
                        const cv = document.createElement("canvas");
                        cv.width = 8; cv.height = 8;
                        const cx = cv.getContext("2d");
                        cx.drawImage(tex.image, 0, 0, 8, 8);
                        const d = cx.getImageData(0, 0, 8, 8).data;
                        let r = 0, g = 0, b = 0, n = 0;
                        for (let i = 0; i < d.length; i += 4) {
                            r += d[i]; g += d[i + 1]; b += d[i + 2]; n++;
                        }
                        avg = new THREE.Color(
                            `rgb(${Math.round(r / n)},${Math.round(g / n)},${Math.round(b / n)})`
                        );
                    } catch (e) { /* CORS/празна — ползвай fallback */ }
                    for (const m of meshes) {
                        const hasUV = !!(m.geometry && m.geometry.attributes
                            && m.geometry.attributes.uv);
                        m.material = new THREE.MeshPhongMaterial(
                            hasUV
                                ? { map: tex, side: THREE.DoubleSide, shininess: 20 }
                                : { color: avg, side: THREE.DoubleSide, shininess: 20 }
                        );
                    }
                });
            }
        }
    }

    async _buildFromBomAssets(assets) {
        const t = this._three;
        // Freeze camera during rebuild to prevent jumps
        const savedAutoRotate = this.ui.autoRotate;
        this.ui.autoRotate = false;

        this._clearModel();
        t.componentMeshes = {};
        const THREE = window.THREE;
        if (!THREE || !THREE.GLTFLoader) {
            console.warn("GLTFLoader not available, falling back");
            this._buildLegacyModel();
            return;
        }
        const loader = new THREE.GLTFLoader();
        // Meshopt-компресия (gltfpack) за slab GLB-тата — decoder в lib/three.
        if (window.MeshoptDecoder && loader.setMeshoptDecoder) {
            loader.setMeshoptDecoder(window.MeshoptDecoder);
        }
        let frameBox = null;
        let componentIndex = 0;

        for (const component of assets) {
            // Избран „Мотив" → статичен slab GLB (геометрията на дизайна F01-F41).
            // Иначе variant override или дефолтния компонентен GLB.
            const motifUrl = this._motifGlbUrlForLine(component.bom_line_id);
            const overrideAssets = (this._variantOverrides || {})[component.product_id];
            let glbList, texList;
            if (motifUrl) {
                glbList = [{ url: motifUrl, name: "motif.glb" }];
                texList = [];
            } else {
                glbList = overrideAssets ? overrideAssets.models_3d : component.assets.models_3d;
                texList = overrideAssets ? overrideAssets.textures : component.assets.textures;
            }
            for (const glb of glbList) {
                try {
                    const url = glb.url || `/web/content/${glb.id}?download=true`;
                    const gltf = await new Promise((resolve, reject) => {
                        loader.load(url, resolve, undefined, reject);
                    });

                    const scene = gltf.scene;

                    // ИЗБРАН цвят/декор за този компонент (от конфигуратора) —
                    // прилага се при ЗАРЕЖДАНЕ, с ПРИОРИТЕТ пред основната текстура.
                    let applied = false;
                    const chosen = this._selectedColorForLine(component.bom_line_id);
                    if (chosen && !chosen.image && chosen.html_color) {
                        const col = new THREE.Color(chosen.html_color);
                        scene.traverse(c => {
                            if (c.isMesh) c.material = new THREE.MeshPhongMaterial({
                                color: col, side: THREE.DoubleSide, shininess: 25,
                            });
                        });
                        applied = true;
                    } else if (chosen && chosen.image) {
                        const tx = await new Promise(r =>
                            new THREE.TextureLoader().load(
                                chosen.image, r, undefined, () => r(null)));
                        if (tx) {
                            tx.wrapS = THREE.RepeatWrapping;
                            tx.wrapT = THREE.RepeatWrapping;
                            let avg = new THREE.Color(0xb8893a);
                            try {
                                const cv = document.createElement("canvas");
                                cv.width = 8; cv.height = 8;
                                const cx = cv.getContext("2d");
                                cx.drawImage(tx.image, 0, 0, 8, 8);
                                const d = cx.getImageData(0, 0, 8, 8).data;
                                let r = 0, g = 0, b = 0, n = 0;
                                for (let i = 0; i < d.length; i += 4) {
                                    r += d[i]; g += d[i + 1]; b += d[i + 2]; n++;
                                }
                                avg = new THREE.Color(
                                    `rgb(${Math.round(r / n)},${Math.round(g / n)},${Math.round(b / n)})`);
                            } catch (e) { /* CORS/празна */ }
                            scene.traverse(c => {
                                if (!c.isMesh) return;
                                const hasUV = !!(c.geometry && c.geometry.attributes
                                    && c.geometry.attributes.uv);
                                c.material = new THREE.MeshPhongMaterial(
                                    hasUV
                                        ? { map: tx, side: THREE.DoubleSide, shininess: 20 }
                                        : { color: avg, side: THREE.DoubleSide, shininess: 20 });
                            });
                            applied = true;
                        }
                    }

                    // Иначе: основна текстура (coating) / компонентна / дефолтен цвят.
                    const mainTex = (this.props.mainProductAssets?.textures || []);
                    const compTex = texList;
                    const textures = mainTex.length > 0 ? mainTex : compTex;
                    if (!applied && textures.length > 0) {
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
                    } else if (!applied) {
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

                    // Запомни мрежите на компонента → пребоядисване при избор на цвят.
                    if (!t.componentMeshes) t.componentMeshes = {};
                    const _cm = [];
                    scene.traverse(child => { if (child.isMesh) _cm.push(child); });
                    if (component.bom_line_id) {
                        t.componentMeshes[component.bom_line_id] = _cm;
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

                        const opening = this._getOpeningDirection();
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
                this._refWidth = this._getParamByRole("width")
                    || this._getParamByLabel("Width (mm)") || 900;
                this._refHeight = this._getParamByRole("height")
                    || this._getParamByLabel("Height (mm)") || 2100;
                this._refWallWidth = this._getParamByRole("wall_width")
                    || this._getParamByLabel("Wall Width (mm)") || 100;

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
        this._refWidth = this._getParamByRole("width")
            || this._getParamByLabel("Width (mm)") || 900;
        this._refHeight = this._getParamByRole("height")
            || this._getParamByLabel("Height (mm)") || 2100;
        this._refWallWidth = this._getParamByRole("wall_width")
            || this._getParamByLabel("Wall Width (mm)") || 100;
        const code = this.props.definitionCode;
        if (code === "bags") this._buildBag();
        else if (code === "security_door") this._buildSecurityDoor();
        else if (code === "roller_door") this._buildRollerDoor();
        else if (code === "interior_door") this._buildInteriorDoor();
        else if (code === "corrugated") this._buildBox();
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
            // D3: освободи ЦЯЛАТА сцена (не само renderer-а) — GPU leak fix
            this._clearModel();
            if (t.scene) this._disposeObject(t.scene);
            t.scene = null;
            t.group = null;
            if (t.renderer) {
                const canvas = t.renderer.domElement;
                if (canvas && this._onCtxLost) {
                    canvas.removeEventListener("webglcontextlost", this._onCtxLost);
                    canvas.removeEventListener("webglcontextrestored", this._onCtxRestored);
                }
                t.renderer.dispose();
            }
            t.renderer = null;
            if (this._resizeObserver) this._resizeObserver.disconnect();
            // Clean up window event listeners added in _initThree
            if (this._onMouseUp) window.removeEventListener("mouseup", this._onMouseUp);
            if (this._onMouseMove) window.removeEventListener("mousemove", this._onMouseMove);
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
            const hidden = this._roleOf(def.string) === "hide_in_description"
                || (def.string?.includes("Wall") || def.string?.includes("Lip")
                    || def.string?.includes("Каса"));
            if (def.type === "float" && def.string?.includes("mm") && !hidden) {
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
        // Два източника: (1) вариант-аксесоари с definitionParamKey (стар път,
        // снимка от texture attachment); (2) явни material choices от BoM реда
        // с choiceKey (стойност = product.id, директен imageUrl).
        return (this.props.accessoryVariants || [])
            .filter(g => g.definitionParamKey || g.choiceKey)
            .map(group => {
                const paramKey = group.choiceKey || group.definitionParamKey;
                const selectedVal = this.params[paramKey];
                return {
                    ...group,
                    paramKey,
                    variants: group.variants.map(v => {
                        const variantStr = group.choiceKey
                            ? String(v.variant_id)
                            : v.ptav_name;
                        const imageUrl = v.imageUrl
                            || (v.textures && v.textures[0]
                                ? `/web/content/${v.textures[0].id}?download=true`
                                : "");
                        return {
                            ...v,
                            variantStr,
                            imageUrl,
                            selected: String(selectedVal) === variantStr,
                        };
                    }),
                };
            });
    }

    // ── Accessory chips (floating bar over 3D) ───────────────────────────
    // Двата вида аксесоари като chip-бутони върху 3D картината:
    //   toggles → boolean екстри/електроника (вкл/изкл);
    //   groups  → вариант-избори (дръжка/обков...) със снимка.
    get accessoryChips() {
        // Аксесоарите идват от бекенда (props.accessoryToggles + accessoryVariants).
        // Монтажите вече са ОПЕРАЦИИ → скриват се от Екстри toggle-ите.
        const isMontage = (lbl) => {
            // D1: роля operation (данни) first; префикс-сетът остава fallback.
            if (this._roleOf(lbl) === "operation") return true;
            const s = (lbl || "");
            return s.startsWith("Монтаж") || s.startsWith("Метален монтаж")
                || s.startsWith("Дърводелски монтаж") || s.startsWith("Дем.")
                || ["Измазване", "Пяна", "Метална конструкция"].includes(s);
        };
        return {
            toggles: (this.props.accessoryToggles || [])
                .filter(t => !isMontage(t.label))
                .map(t => ({
                    name: t.param_name,
                    label: t.label,
                    active: !!this.params[t.param_name],
                    readonly: false,
                })),
            groups: this.overlayGroups,
        };
    }

    toggleAccessoryChip(ev) {
        const key = ev.currentTarget.dataset.param;
        if (ev.currentTarget.dataset.readonly === "1") return;
        this.onParamChange(key, !this.params[key]);
    }

    // Избор на операции за извършване (work centers) — toggle.
    // Операциите групирани по работен център (РЦ Фрезоване / Монтажи / ...).
    get operationGroups() {
        const byWc = {};
        const order = [];
        for (const op of (this.props.operationChoices || [])) {
            const wc = op.wcName || _t("Other");
            if (!byWc[wc]) { byWc[wc] = []; order.push(wc); }
            byWc[wc].push({
                opKey: op.opKey,
                name: op.name,
                active: !!this.params["op_" + op.opKey],
            });
        }
        return order.map(wc => ({ wcName: wc, ops: byWc[wc] }));
    }

    toggleOperationChip(ev) {
        const key = "op_" + ev.currentTarget.dataset.op;
        this.onParamChange(key, !this.params[key]);
    }

    // Атрибути на полуфабрикатите (крило/каса/лайсна): цвят се носи от тях.
    // „Цвят" се филтрира по избраното „Покритие" (coating_idx). Всяка секция
    // се рендира според kind: coating(чипове)/color(снимки/квадрати)/
    // image(мотив-карти)/chip(останалите).
    get componentGroups() {
        const comps = this.props.componentAttributes || [];
        return comps.map(comp => {
            const coatingByName = {};
            for (const a of comp.attributes) {
                if (a.isCoating) coatingByName[a.name] = a;
            }
            const sections = comp.attributes.map(a => {
                const key = "cattr_" + comp.bomLineId + "_" + a.attrId;
                const sel = this.params[key];
                let kind = "chip";
                if (a.isCoating) kind = "coating";
                else if (a.isColor) kind = "color";
                else if (a.isMotif || a.name === "Мотив") kind = "image";
                // Филтър на цвета по сдвоеното покритие (вън/вътре).
                let allowedIdx = null;
                if (a.isColor) {
                    // D1: сдвоеното покритие идва явно от бекенда
                    // (pairedCoatingAttrId, при еднозначна двойка); иначе
                    // legacy fallback: „Цвят X" → „Покритие X" (вън/вътре…).
                    let coat = null;
                    if (a.pairedCoatingAttrId) {
                        coat = comp.attributes.find(
                            x => x.attrId === a.pairedCoatingAttrId);
                    }
                    if (!coat) {
                        const coatName = a.name.replace("Цвят", "Покритие");
                        coat = coatingByName[coatName];
                    }
                    if (coat) {
                        const cSel = this.params["cattr_" + comp.bomLineId + "_" + coat.attrId];
                        const cVal = (coat.values || []).find(v => String(v.id) === String(cSel));
                        if (cVal) allowedIdx = cVal.coating_idx;
                    }
                }
                let options = (a.values || []).map(v => ({
                    ptavId: v.id,
                    name: v.name,
                    key,
                    selected: String(sel) === String(v.id),
                    image: v.image,
                    htmlColor: v.html_color,
                    coatingIdx: v.coating_idx,
                })).filter(o =>
                    kind !== "color" || allowedIdx === null
                    || o.coatingIdx === allowedIdx || o.coatingIdx === 6
                );
                // Цветовете се подреждат по азбучен ред (display); покритията
                // запазват смисловата си подредба.
                if (kind === "color") {
                    options = options.sort((o1, o2) =>
                        (o1.name || "").localeCompare(o2.name || "", "bg"));
                }
                return {
                    attrId: a.attrId, name: a.name, kind, key, options,
                    isMedia: kind === "color" || kind === "image",
                };
            });
            return {
                componentName: comp.componentName,
                lineId: comp.bomLineId,
                sections,
            };
        });
    }

    onComponentAttrSelect(ev) {
        const el = ev.currentTarget;
        const key = el.dataset.key;
        const val = el.dataset.value;
        // toggle off ако се кликне същата стойност
        this.params[key] = (String(this.params[key]) === String(val)) ? false : val;
        if (this._isMotifKey(key)) {
            // „Мотив" сменя ГЕОМЕТРИЯТА на крилото → зареди новия slab GLB
            // (пре-билд с fade, ротацията се пази → без подскок).
            this._rebuildModelWithFade();
        } else {
            // Цвят/покритие → пребоядисай на място (само материал, без пре-билд).
            this._applyComponentColors();
        }
        if (this.props.level === "sales" || !this.props.level) {
            this._recomputeCost();
        }
    }

    // Дали ключът cattr_<line>_<attrId> сочи атрибут „Мотив".
    _isMotifKey(key) {
        const m = /^cattr_(\d+)_(\d+)$/.exec(key || "");
        if (!m) return false;
        const lineId = parseInt(m[1]), attrId = parseInt(m[2]);
        const comp = (this.props.componentAttributes || [])
            .find(c => c.bomLineId === lineId);
        if (!comp) return false;
        const attr = (comp.attributes || []).find(a => a.attrId === attrId);
        // D1: isMotif (design_role) first; името е fallback за заварени данни.
        return !!(attr && (attr.isMotif || attr.name === "Мотив"));
    }

    async _rebuildModelWithFade() {
        const canvas = this.canvasRef.el;
        if (canvas) canvas.style.opacity = "0.25";
        try {
            await this._buildModel();
        } finally {
            if (canvas) canvas.style.opacity = "1";
        }
    }

    // ── Computed display helpers ─────────────────────────────────────────

    get show3D() {
        // Само sales (или без зададено ниво) е визуален; technical/production/
        // cost не зареждат 3D/снимки.
        return !["technical", "production", "cost"].includes(this.props.level || "");
    }

    get costMode() {
        // Ниво cost: дясният панел (на мястото на картинката) показва себестойност.
        return (this.props.level || "") === "cost";
    }

    _buildDesignContext() {
        // Жив design контекст: {param_string: value} от текущите параметри
        // + явните избори на материал (choice_<key>), за да влязат в цената.
        const ctx = {};
        for (const def of (this.props.paramDefinition || [])) {
            ctx[def.string] = this.params[def.name];
        }
        for (const [k, v] of Object.entries(this.params)) {
            if (k.startsWith("choice_")) ctx[k] = v;
        }
        return ctx;
    }

    async _recomputeCost() {
        // Тече и на sales (жива калкулация в левия панел), не само на cost ниво.
        if (this.props.level === "technical" || this.props.level === "production") {
            return;
        }
        try {
            const res = await this.orm.call(
                "mrp.bom", "simulate_cost_for_product",
                [this.props.productId, this._buildDesignContext(), 1.0,
                 this.props.existingLotId || false]
            );
            // D1 hook: без mrp_design_matrix_cost стубът връща
            // {available:false} → крием калкулацията изцяло.
            this.cost.data = res && res.available === false ? null : res;
        } catch (e) {
            this.cost.data = { error: e.message || String(e) };
        }
    }

    get displayParams() {
        // Exclude child component params (shown in their own "Fine Tuning" section).
        // Изключваме и по name (UUID), И по string (етикет): merge-ът на child
        // дефинициите в full_design_params_definition дедупира по string, докато
        // тук guard-ът беше само по name → при разминаване (raw vs full child def)
        // същият параметър (напр. „Height (mm)") се показваше и в главния панел, и
        // в „Fine Tuning". Изключването по string затваря дупката.
        const childDefs = (this.props.childComponents || [])
            .flatMap(c => (c.paramDefinition || []));
        const childNames = new Set(childDefs.map(d => d.name));
        const childStrings = new Set(childDefs.map(d => d.string).filter(Boolean));
        const level = this.props.level || "";
        const levels = this.props.paramLevels || {};
        return this.props.paramDefinition
            .filter(def => !childNames.has(def.name) && !childStrings.has(def.string))
            .filter(def => this._levelVisible(def, level, levels))
            .map(def => ({
                ...def,
                value: this.params[def.name],
                _levelReadonly: this._levelReadonly(def, level, levels),
            }));
    }

    /**
     * Generic per-level visibility. Empty level → full configurator.
     *   sales      → sales params (+ unlabelled);
     *   technical  → everything except production;
     *   production → everything (review + correction).
     */
    _levelVisible(def, level, levels) {
        if (!level) return true;
        const pl = levels[def.string];
        if (level === "production") return true;
        if (level === "technical") return pl !== "production";
        if (level === "sales") return !pl || pl === "sales";
        return true;
    }

    /** In technical mode the confirmed sales params are shown read-only. */
    _levelReadonly(def, level, levels) {
        if (level === "technical") return levels[def.string] === "sales";
        return false;
    }

    get childDisplayParams() {
        // Returns child component params with current values for Fine Tuning
        const children = this.props.childComponents || [];
        return children.map(child => ({
            ...child,
            params: (child.paramDefinition || []).map(def => ({
                ...def,
                value: this.params[def.name] !== undefined
                    ? this.params[def.name]
                    : (def.type === 'float' ? (parseFloat(def.default) || 0) : (def.default || '')),
            })),
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
