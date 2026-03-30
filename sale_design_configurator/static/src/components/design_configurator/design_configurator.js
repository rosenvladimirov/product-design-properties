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
        bomAssets: { type: Array, optional: true },
        mainProductAssets: { type: Object, optional: true },
        childComponents: { type: Array, optional: true },
        accessoryVariants: { type: Array, optional: true },
        modelVariants: { type: Object, optional: true },
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

        // Initialize accessory selections in params (two-way binding with overlay)
        for (const group of (this.props.accessoryVariants || [])) {
            const key = `_acc_${group.bomProductId}`;
            this.params[key] = String(group.bomProductId);
        }

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
            this._initThree();
            this._buildModel();
            this._validate();
            this._updateDescription();
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
        Object.assign(this.params, lot.design_params || {});
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
        this._updateDescription();

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

        // Structural changes that need full rebuild
        const rebuildParams = ["Leaf Type", "Construction"];
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
        const oldHingeX = opening === "right" ? t.hingeLeftX : t.hingeRightX;

        // Move pivot to new hinge
        t.leafPivot.position.x = newHingeX;

        // Restore original child positions then offset for new hinge
        const deltaX = newHingeX - oldHingeX;
        t.leafPivot.children.forEach((child, i) => {
            const baseX = t.leafChildrenBaseX[i];
            if (baseX !== undefined) {
                // baseX was relative to the original hinge (left)
                // For right hinge, shift by -(right - left)
                child.position.x = baseX - (newHingeX - t.hingeLeftX);
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
        // All params go into design_params (Properties field)
        // Width/Height/Thickness are now part of Properties via base_dimensions inheritance
        const designParams = { ...this.params };
        designParams._description = this.ui.description;
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
        window.addEventListener("mouseup", (e) => {
            // Detect click (not drag): small movement + short duration
            if (clickStart && !t.leafAnimating) {
                const dx = Math.abs(e.clientX - clickStart.x);
                const dy = Math.abs(e.clientY - clickStart.y);
                const dt = Date.now() - clickStart.time;
                if (dx < 5 && dy < 5 && dt < 300 && t.leafPivot) {
                    // Raycast to check if leaf was clicked
                    const rect = canvas.getBoundingClientRect();
                    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
                    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
                    t.raycaster.setFromCamera(mouse, t.camera);

                    // Check leaf click
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
        });
        window.addEventListener("mousemove", (e) => {
            if (!t.drag) return;
            t.rotY += (e.clientX - t.prevX) * 0.008;
            t.rotX += (e.clientY - t.prevY) * 0.008;
            t.rotX = Math.max(-1.2, Math.min(1.2, t.rotX));
            t.prevX = e.clientX; t.prevY = e.clientY;
        });

        const animate = () => {
            t.animId = requestAnimationFrame(animate);
            if (this.ui.autoRotate && !t.drag) t.rotY += 0.003;
            t.group.rotation.x = t.rotX;
            t.group.rotation.y = t.rotY;
            // Smooth leaf open/close animation
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

    _trySwapModelVariant(paramKey, selectedValue) {
        const mv = this.props.modelVariants || {};
        for (const [productId, variants] of Object.entries(mv)) {
            const match = variants.find(v => v.ptav_name === selectedValue);
            if (match) {
                this._variantOverrides = this._variantOverrides || {};
                this._variantOverrides[parseInt(productId)] = match.assets;
                // Save camera state, rebuild, camera restores via preserved rotX/rotY
                this._buildModel();
                return true;
            }
        }
        return false;
    }

    _buildModel() {
        const bomAssets = this.props.bomAssets || [];
        const glbAssets = bomAssets.filter(a => a.assets.models_3d.length > 0);

        if (glbAssets.length > 0) {
            this._buildFromBomAssets(glbAssets);
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
        const t = this._three;
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
        for (const group of (this.props.accessoryVariants || [])) {
            const paramKey = `_acc_${group.bomProductId}`;
            const selVal = this.params[paramKey];
            const variant = group.variants.find(v => String(v.variant_id) === selVal);
            if (variant) parts.push(`${group.componentName}: ${variant.ptav_name}`);
        }
        this.ui.description = parts.join(" | ");
    }

    get overlayGroups() {
        return (this.props.accessoryVariants || []).map(group => {
            const paramKey = `_acc_${group.bomProductId}`;
            const selectedVal = this.params[paramKey];
            return {
                ...group,
                paramKey,
                variants: group.variants.map(v => ({
                    ...v,
                    variantStr: String(v.variant_id),
                    imageUrl: `/web/content/${v.textures[0].id}?download=true`,
                    selected: String(v.variant_id) === selectedVal,
                })),
            };
        });
    }

    // ── Computed display helpers ─────────────────────────────────────────

    get displayParams() {
        return this.props.paramDefinition.map((def) => ({
            ...def,
            value: this.params[def.name],
        }));
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

    get accessoryDisplayParams() {
        return (this.props.accessoryVariants || []).map(group => ({
            paramKey: `_acc_${group.bomProductId}`,
            componentName: group.componentName,
            options: group.variants.map(v => [String(v.variant_id), v.ptav_name]),
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
