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

// Three.js is loaded via assets bundle (see __manifest__.py)
// window.THREE is available after page load.

export class DesignConfiguratorWidget extends Component {
    static template = "sale_design_configurator.DesignConfiguratorWidget";

    /**
     * Props:
     *   productId          (Number)  - product.product id
     *   definitionId       (Number)  - design.param.definition id
     *   definitionCode     (String)  - e.g. "security_door" | "interior_door"
     *   paramDefinition    (Array)   - PropertiesDefinition entries from server
     *   existingLotId      (Number?) - if editing an existing design lot
     *   onLotCreated       (Function) - callback(lotId, params)
     *   onClose            (Function) - callback to close dialog
     */
    static props = {
        productId: { type: Number },
        definitionId: { type: Number },
        definitionCode: { type: String },
        paramDefinition: { type: Array },
        existingLotId: { type: [Number, Boolean], optional: true },
        onLotCreated: { type: Function },
        onClose: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");

        this.canvasRef = useRef("canvas");

        // Design parameter state
        // Initialised from paramDefinition defaults; overridden if editing.
        this.params = useState(
            this._buildInitialParams(this.props.paramDefinition)
        );

        // UI state
        this.ui = useState({
            saving: false,
            validErrors: [],
            validWarns: [],
        });

        // Three.js handles
        this._three = {
            renderer: null,
            scene: null,
            camera: null,
            group: null,
            animId: null,
            rotX: 0.3,
            rotY: 0.4,
            drag: false,
            prevX: 0,
            prevY: 0,
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

    // -- Param initialisation -----------------------------------------------

    _buildInitialParams(definition) {
        const p = {};
        for (const prop of definition || []) {
            // prop = {name, string, type, default, selection, ...}
            if (prop.type === "boolean") {
                p[prop.name] = prop.default === "true" || prop.default === true;
            } else if (prop.type === "float") {
                p[prop.name] = parseFloat(prop.default) || 0.0;
            } else {
                // char / selection: first option value or default
                if (
                    prop.type === "selection" &&
                    !prop.default &&
                    prop.selection?.length
                ) {
                    p[prop.name] = prop.selection[0][0];
                } else {
                    p[prop.name] = prop.default || "";
                }
            }
        }
        return p;
    }

    async _loadExistingLot(lotId) {
        const [lot] = await this.orm.read("stock.lot", [lotId], [
            "design_params",
            "width",
            "height",
            "thickness",
        ]);
        if (!lot) return;
        Object.assign(this.params, lot.design_params || {});
        if (lot.width) this.params.width = lot.width;
        if (lot.height) this.params.height = lot.height;
        if (lot.thickness) this.params.thickness = lot.thickness;
    }

    // -- Validation (mirrors T0 constraint logic) ---------------------------

    _validate() {
        const errs = [],
            warns = [];
        const code = this.props.definitionCode;
        const p = this.params;

        if (code === "bags") {
            if (p.bag_type === "sheet" && p.has_tie) {
                warns.push(
                    "Sheet + tie: the slitting operation will be skipped."
                );
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
            const requiredThick = minThick[rc] || 0;
            if ((p.sheet_thickness || 0) < requiredThick) {
                // T1 force - auto-correct, show info
                warns.push(
                    `${rc}: minimum thickness is ${requiredThick}mm. Value has been corrected.`
                );
                this.params.sheet_thickness = requiredThick;
            }
        }

        if (code === "interior_door") {
            if (p.leaf_type === "double" && p.opening !== "none") {
                errs.push(
                    "Double leaf door: the 'opening direction' must be 'none'."
                );
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

    // -- User interaction ---------------------------------------------------

    onParamChange(key, value) {
        this.params[key] = value;
        this._validate();
        this._buildModel();
    }

    onRangeChange(key, event) {
        const val = parseFloat(event.target.value);
        this.onParamChange(key, val);
    }

    onBoolChange(key, event) {
        this.onParamChange(key, event.target.checked);
    }

    onSelectionChange(key, value) {
        this.onParamChange(key, value);
    }

    // -- Save to Odoo -------------------------------------------------------

    async onConfirm() {
        if (this.hasErrors) {
            this.notification.add(
                "Invalid configuration. Please correct the errors.",
                { type: "danger" }
            );
            return;
        }
        this.ui.saving = true;
        try {
            const lotId = await this._saveDesignLot();
            this.notification.add("Design lot created successfully.", {
                type: "success",
            });
            this.props.onLotCreated(lotId, { ...this.params });
            this.props.onClose();
        } catch (e) {
            this.notification.add(`Error: ${e.message}`, { type: "danger" });
        } finally {
            this.ui.saving = false;
        }
    }

    async _saveDesignLot() {
        // Separate physical dimensions (real fields) from design_params (Properties)
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

        // Generate lot name via sequence (server-side)
        const lotName = await this.orm.call(
            "stock.lot",
            "generate_design_lot_name",
            [this.props.productId]
        );

        const vals = {
            name: lotName,
            product_id: this.props.productId,
            design_param_definition_id: this.props.definitionId,
            design_params: designParams,
            ...realVals,
        };

        if (this.props.existingLotId) {
            await this.orm.write(
                "stock.lot",
                [this.props.existingLotId],
                vals
            );
            return this.props.existingLotId;
        } else {
            const [lotId] = await this.orm.create("stock.lot", [vals]);
            return lotId;
        }
    }

    // -- Three.js -----------------------------------------------------------

    _initThree() {
        const THREE = window.THREE;
        if (!THREE) {
            console.error("Three.js not loaded");
            return;
        }
        const canvas = this.canvasRef.el;
        const t = this._three;

        t.renderer = new THREE.WebGLRenderer({
            canvas,
            antialias: true,
            alpha: true,
        });
        t.renderer.setClearColor(0x000000, 0);
        t.renderer.setPixelRatio(window.devicePixelRatio);

        t.scene = new THREE.Scene();
        t.camera = new THREE.PerspectiveCamera(45, 1, 0.1, 500);
        t.camera.position.set(0, 0, 4);

        t.scene.add(new THREE.AmbientLight(0xffffff, 0.6));
        const dir = new THREE.DirectionalLight(0xffffff, 0.8);
        dir.position.set(3, 4, 5);
        t.scene.add(dir);
        const dir2 = new THREE.DirectionalLight(0xffffff, 0.3);
        dir2.position.set(-3, 1, -2);
        t.scene.add(dir2);

        t.group = new THREE.Group();
        t.scene.add(t.group);

        // Resize handler
        this._resizeObserver = new ResizeObserver(() => this._resize());
        this._resizeObserver.observe(canvas.parentElement);
        this._resize();

        // Drag to rotate
        canvas.addEventListener("mousedown", (e) => {
            t.drag = true;
            t.prevX = e.clientX;
            t.prevY = e.clientY;
        });
        window.addEventListener("mouseup", () => {
            t.drag = false;
        });
        window.addEventListener("mousemove", (e) => {
            if (!t.drag) return;
            t.rotY += (e.clientX - t.prevX) * 0.008;
            t.rotX += (e.clientY - t.prevY) * 0.008;
            t.rotX = Math.max(-1.2, Math.min(1.2, t.rotX));
            t.prevX = e.clientX;
            t.prevY = e.clientY;
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
        const mat = new THREE.MeshPhongMaterial({
            color,
            opacity,
            transparent: opacity < 1,
            side: THREE.DoubleSide,
            shininess: 30,
        });
        return new THREE.Mesh(geo, mat);
    }

    _buildModel() {
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
        const THREE = window.THREE;
        const t = this._three;
        const p = this.params;
        const W = (p.width || 600) / 800;
        const H = (p.height || 800) / 800;
        const T = Math.max(0.015, (p.thickness || 25) / 2000);
        const COL_MAP = {
            black: 0x222222,
            green: 0x2d7a2d,
            white: 0xeeeeee,
            blue: 0x1a4a9a,
        };
        const col = COL_MAP[p.color] || 0x222222;

        const depth = p.bag_type === "sleeve" ? T * 2 : T;
        const body = this._makeMesh(
            new THREE.BoxGeometry(W, H, depth),
            col
        );
        t.group.add(body);

        const edges = new THREE.LineSegments(
            new THREE.EdgesGeometry(body.geometry),
            new THREE.LineBasicMaterial({
                color: 0x000000,
                opacity: 0.12,
                transparent: true,
            })
        );
        t.group.add(edges);

        if (p.has_tie) {
            const band = this._makeMesh(
                new THREE.BoxGeometry(W * 0.6, 0.03, depth + 0.002),
                0xcc3333
            );
            band.position.y = H / 2 + 0.02;
            t.group.add(band);
            const knot = this._makeMesh(
                new THREE.SphereGeometry(0.025, 8, 6),
                0xcc3333
            );
            knot.position.y = H / 2 + 0.04;
            t.group.add(knot);
        }
        if (p.has_print) {
            const ink = this._makeMesh(
                new THREE.BoxGeometry(W * 0.5, H * 0.3, depth + 0.003),
                0x334488,
                0.9
            );
            ink.position.set(0, 0, depth / 2 + 0.002);
            t.group.add(ink);
        }
        t.group.position.set(0, -H * 0.1, 0);
    }

    _buildSecurityDoor() {
        this._clearModel();
        const THREE = window.THREE;
        const t = this._three;
        const p = this.params;
        const W = (p.width || 900) / 2000;
        const H = (p.height || 2100) / 2000;
        const T = Math.max(0.04, (p.sheet_thickness || 2) / 50);
        const FW = 0.04;
        const FINISH_COL = { RAL: 0x5c3d55, galv: 0x8899aa, ss: 0xc0c8d0 };
        const panelCol = FINISH_COL[p.finish] || 0x5c3d55;

        [
            [0, H / 2, W, FW],
            [0, -H / 2, W, FW],
            [-W / 2, 0, FW, H],
            [W / 2, 0, FW, H],
        ].forEach(([x, y, fw, fh]) => {
            const m = this._makeMesh(
                new THREE.BoxGeometry(fw, fh, T),
                0x444444
            );
            m.position.set(x, y, 0);
            t.group.add(m);
        });

        if (p.has_glass) {
            const gH = H * 0.35;
            const gls = this._makeMesh(
                new THREE.BoxGeometry(W * 0.5, gH, 0.008),
                0x88bbdd,
                0.4
            );
            gls.position.set(0, H * 0.15, 0);
            t.group.add(gls);
            const pnl = this._makeMesh(
                new THREE.BoxGeometry(W - FW * 2, H * 0.38, T * 0.8),
                panelCol
            );
            pnl.position.set(0, -H * 0.22, 0);
            t.group.add(pnl);
        } else {
            const pnl = this._makeMesh(
                new THREE.BoxGeometry(W - FW * 2, H - FW * 2, T * 0.8),
                panelCol
            );
            t.group.add(pnl);
        }

        if (p.has_electronic_lock) {
            const el = this._makeMesh(
                new THREE.BoxGeometry(0.04, 0.1, T + 0.015),
                0x334488
            );
            el.position.set(W / 2 - FW * 1.5, 0.05, 0);
            t.group.add(el);
        }
        t.group.position.set(0, -H * 0.45, 0);
    }

    _buildRollerDoor() {
        this._clearModel();
        const THREE = window.THREE;
        const t = this._three;
        const p = this.params;
        const W = (p.width || 2500) / 3000;
        const H = (p.height || 2500) / 3000;
        const SLAT_COL = { AL: 0xc0c8d0, steel: 0x8899aa, PC: 0xaaddee };
        const col = SLAT_COL[p.slat_type] || 0xc0c8d0;
        const slatH = 0.04;
        const slatCount = Math.floor(H / slatH);

        for (let i = 0; i < slatCount; i++) {
            const y = -H / 2 + i * slatH + slatH / 2;
            const slat = this._makeMesh(
                new THREE.BoxGeometry(W, slatH * 0.88, 0.015),
                col
            );
            slat.position.y = y;
            t.group.add(slat);
            if (i % 2 === 0) {
                const line = new THREE.Line(
                    new THREE.BufferGeometry().setFromPoints([
                        new THREE.Vector3(-W / 2, y + slatH / 2, 0.016),
                        new THREE.Vector3(W / 2, y + slatH / 2, 0.016),
                    ]),
                    new THREE.LineBasicMaterial({
                        color: 0x8899aa,
                        opacity: 0.4,
                        transparent: true,
                    })
                );
                t.group.add(line);
            }
        }

        const guide = this._makeMesh(
            new THREE.BoxGeometry(0.025, H, 0.025),
            0x444444
        );
        guide.position.x = -W / 2 - 0.015;
        t.group.add(guide);
        const guide2 = guide.clone();
        guide2.position.x = W / 2 + 0.015;
        t.group.add(guide2);

        if (p.drive_type === "electric") {
            const motor = this._makeMesh(
                new THREE.BoxGeometry(0.15, 0.1, 0.1),
                0x334466
            );
            motor.position.set(0, H / 2 + 0.07, 0);
            t.group.add(motor);
        }
        t.group.position.set(0, -H * 0.05, 0);
    }

    _buildInteriorDoor() {
        this._clearModel();
        const THREE = window.THREE;
        const t = this._three;
        const p = this.params;
        const mult = p.leaf_type === "double" ? 2 : 1;
        const W = ((p.width || 900) / 2000) * mult;
        const H = (p.height || 2100) / 2000;
        const FIN_COL = {
            veneer: 0xd4a852,
            lacquer: 0xf0ead6,
            RAL: 0x5c3d55,
            foil: 0xcccccc,
        };
        const col = FIN_COL[p.finish] || 0xd4a852;
        const T = 0.04;

        const frame = this._makeMesh(
            new THREE.BoxGeometry(W, H, T),
            col
        );
        t.group.add(frame);
        const edges = new THREE.LineSegments(
            new THREE.EdgesGeometry(frame.geometry),
            new THREE.LineBasicMaterial({
                color: 0x000000,
                opacity: 0.15,
                transparent: true,
            })
        );
        t.group.add(edges);

        if (p.has_glass_panel) {
            const gls = this._makeMesh(
                new THREE.BoxGeometry(W * 0.45, H * 0.3, T + 0.005),
                0x88bbdd,
                0.45
            );
            gls.position.set(0, H * 0.2, 0);
            t.group.add(gls);
        }

        const handle = this._makeMesh(
            new THREE.BoxGeometry(0.012, 0.1, 0.012),
            0xaa9944
        );
        handle.position.set(W / 2 - 0.05, 0, T / 2 + 0.006);
        t.group.add(handle);

        if (p.leaf_type === "double") {
            const divider = new THREE.Line(
                new THREE.BufferGeometry().setFromPoints([
                    new THREE.Vector3(0, -H / 2, T / 2 + 0.001),
                    new THREE.Vector3(0, H / 2, T / 2 + 0.001),
                ]),
                new THREE.LineBasicMaterial({
                    color: 0x888888,
                    opacity: 0.4,
                    transparent: true,
                })
            );
            t.group.add(divider);
        }
        t.group.position.set(0, -H * 0.4, 0);
    }

    _buildBox() {
        this._clearModel();
        const THREE = window.THREE;
        const t = this._three;
        const p = this.params;
        const L = (p.box_l || 400) / 600;
        const W = (p.box_w || 300) / 600;
        const D = (p.box_d || 200) / 600;
        const col = 0xd4a852;
        const dark = 0xb8893a;

        const body = this._makeMesh(
            new THREE.BoxGeometry(L, D, W),
            col
        );
        t.group.add(body);
        t.group.add(
            new THREE.LineSegments(
                new THREE.EdgesGeometry(body.geometry),
                new THREE.LineBasicMaterial({
                    color: dark,
                    opacity: 0.4,
                    transparent: true,
                })
            )
        );

        const flap = this._makeMesh(
            new THREE.BoxGeometry(L, D * 0.48, 0.01),
            dark,
            0.85
        );
        flap.position.y = D / 2 + D * 0.24;
        t.group.add(flap);

        if (p.has_print) {
            const ink = this._makeMesh(
                new THREE.BoxGeometry(L * 0.5, D * 0.35, 0.008),
                0x334488,
                0.85
            );
            ink.position.set(0, 0, W / 2 + 0.005);
            t.group.add(ink);
        }
        t.group.position.set(0, -D * 0.4, 0);
    }

    _buildGenericBox() {
        this._clearModel();
        const THREE = window.THREE;
        const t = this._three;
        const box = this._makeMesh(
            new THREE.BoxGeometry(1.2, 1.8, 0.08),
            0x888888
        );
        t.group.add(box);
        t.group.add(
            new THREE.LineSegments(
                new THREE.EdgesGeometry(box.geometry),
                new THREE.LineBasicMaterial({
                    color: 0x444444,
                    opacity: 0.3,
                    transparent: true,
                })
            )
        );
    }

    _destroyThree() {
        const t = this._three;
        if (t.animId) cancelAnimationFrame(t.animId);
        if (t.renderer) t.renderer.dispose();
        if (this._resizeObserver) this._resizeObserver.disconnect();
    }

    // -- Computed display helpers -------------------------------------------

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

// Register as a field widget usable in Odoo forms
registry.category("fields").add("design_configurator", {
    component: DesignConfiguratorWidget,
});
