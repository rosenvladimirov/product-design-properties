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

// Three.js + SVGLoader loaded via assets bundle (see __manifest__.py)
// window.THREE is available after page load.

export class DesignConfiguratorWidget extends Component {
    static template = "sale_design_configurator.DesignConfiguratorWidget";

    static props = {
        productId: { type: Number },
        definitionId: { type: Number },
        definitionCode: { type: String },
        paramDefinition: { type: Array },
        validationRules: { type: Array, optional: true },
        profiles: { type: Array, optional: true },
        existingLotId: { type: [Number, Boolean], optional: true },
        onLotCreated: { type: Function },
        onClose: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.canvasRef = useRef("canvas");

        this.params = useState(
            this._buildInitialParams(this.props.paramDefinition)
        );

        this.ui = useState({
            saving: false,
            validErrors: [],
            validWarns: [],
        });

        this._three = {
            renderer: null, scene: null, camera: null, group: null,
            animId: null, rotX: 0.3, rotY: 0.4,
            drag: false, prevX: 0, prevY: 0,
        };

        onMounted(async () => {
            if (this.props.existingLotId) {
                await this._loadExistingLot(this.props.existingLotId);
            }
            this._initThree();
            this._buildModel();
            this._validate();
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
            "design_params", "width", "height", "thickness",
        ]);
        if (!lot) return;
        Object.assign(this.params, lot.design_params || {});
        if (lot.width) this.params.width = lot.width;
        if (lot.height) this.params.height = lot.height;
        if (lot.thickness) this.params.thickness = lot.thickness;
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

    // ── User interaction ────────────────────────────────────────────────

    onParamChange(key, value) {
        this.params[key] = value;
        this._validate();
        this._buildModel();
    }

    onRangeChange(key, event) {
        this.onParamChange(key, parseFloat(event.target.value));
    }

    onBoolChange(key, event) {
        this.onParamChange(key, event.target.checked);
    }

    onSelectionChange(key, value) {
        this.onParamChange(key, value);
    }

    // ── Save to Odoo ────────────────────────────────────────────────────

    async onConfirm() {
        if (this.hasErrors) {
            this.notification.add("Invalid configuration. Please correct the errors.", { type: "danger" });
            return;
        }
        this.ui.saving = true;
        try {
            const lotId = await this._saveDesignLot();
            this.notification.add("Design lot created successfully.", { type: "success" });
            this.props.onLotCreated(lotId, { ...this.params });
            this.props.onClose();
        } catch (e) {
            this.notification.add(`Error: ${e.message}`, { type: "danger" });
        } finally {
            this.ui.saving = false;
        }
    }

    async _saveDesignLot() {
        const REAL_FIELDS = ["width", "height", "thickness"];
        const designParams = {};
        const realVals = {};
        for (const [k, v] of Object.entries(this.params)) {
            if (REAL_FIELDS.includes(k)) {
                realVals[k] = v;
            } else {
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
            ...realVals,
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

        canvas.addEventListener("mousedown", (e) => {
            t.drag = true; t.prevX = e.clientX; t.prevY = e.clientY;
        });
        window.addEventListener("mouseup", () => { t.drag = false; });
        window.addEventListener("mousemove", (e) => {
            if (!t.drag) return;
            t.rotY += (e.clientX - t.prevX) * 0.008;
            t.rotX += (e.clientY - t.prevY) * 0.008;
            t.rotX = Math.max(-1.2, Math.min(1.2, t.rotX));
            t.prevX = e.clientX; t.prevY = e.clientY;
        });

        const animate = () => {
            t.animId = requestAnimationFrame(animate);
            if (!t.drag) t.rotY += 0.003;
            t.group.rotation.x = t.rotX;
            t.group.rotation.y = t.rotY;
            t.renderer.render(t.scene, t.camera);
        };
        animate();
    }

    _resize() {
        const t = this._three;
        if (!t.renderer) return;
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

    // ── Model building: SVG profile (primary) or legacy fallback ────────

    _buildModel() {
        const profiles = this.props.profiles || [];
        if (profiles.length > 0 && profiles[0].svg_content && profiles[0].profile_definition) {
            this._buildFromSVGProfile(profiles[0]);
        } else {
            this._buildLegacyModel();
        }
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
        const t = this._three;
        if (t.animId) cancelAnimationFrame(t.animId);
        if (t.renderer) t.renderer.dispose();
        if (this._resizeObserver) this._resizeObserver.disconnect();
    }

    // ── Computed display helpers ─────────────────────────────────────────

    get displayParams() {
        return this.props.paramDefinition.map((def) => ({
            ...def,
            value: this.params[def.name],
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
