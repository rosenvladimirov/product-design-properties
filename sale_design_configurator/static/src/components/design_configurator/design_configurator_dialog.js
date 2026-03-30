/** @odoo-module **/
// Copyright 2026 Rosen Vladimirov <vladimirov.rosen@gmail.com>
// License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

/**
 * DesignConfiguratorDialog
 * ------------------------
 * Wraps DesignConfiguratorWidget in an Odoo dialog.
 * Loads the definition, validation rules, and SVG profiles from server
 * before rendering the widget.
 */

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { DesignConfiguratorWidget } from "./design_configurator";

export class DesignConfiguratorDialog extends Component {
    static components = { Dialog, DesignConfiguratorWidget };
    static template = "sale_design_configurator.DesignConfiguratorDialog";

    static props = {
        productId: { type: Number },
        definitionId: { type: Number },
        existingLotId: { type: [Number, Boolean], optional: true },
        onLotCreated: { type: Function, optional: true },
        close: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            definitionCode: "",
            paramDefinition: [],
            validationRules: [],
            profiles: [],
            bomAssets: [],
            mainProductAssets: { models_3d: [], profiles_svg: [], textures: [] },
            childComponents: [],
            accessoryVariants: [],
            modelVariants: {},
        });
        this._loadDefinition();
    }

    async _loadDefinition() {
        const [def] = await this.orm.read(
            "design.param.definition",
            [this.props.definitionId],
            ["code", "full_design_params_definition", "validation_rules"]
        );
        if (def) {
            this.state.definitionCode = def.code;
            this.state.paramDefinition = def.full_design_params_definition || [];
            this.state.validationRules = def.validation_rules || [];
        }

        // Fetch SVG profiles for this definition
        const profiles = await this.orm.searchRead(
            "design.param.profile",
            [["definition_id", "=", this.props.definitionId]],
            ["name", "svg_content", "profile_definition", "extrude_depth", "camera_distance"],
            { order: "sequence, id" }
        );
        this.state.profiles = profiles;

        // Fetch design assets: main product variant + BoM components
        try {
            // Main product variant assets (coating textures, GLB, SVG)
            const mainAssets = await this.orm.call(
                "product.product", "get_design_assets_by_type", [this.props.productId]
            );
            this.state.mainProductAssets = mainAssets;

            const boms = await this.orm.searchRead(
                "mrp.bom",
                [
                    ["product_tmpl_id.product_variant_ids", "in", [this.props.productId]],
                    ["active", "=", true],
                ],
                ["id"],
                { limit: 1 }
            );
            if (boms.length) {
                const bomAssets = await this.orm.call(
                    "mrp.bom", "get_bom_design_assets", [boms[0].id]
                );
                this.state.bomAssets = bomAssets;

                // Load child component definitions (e.g., door leaf with its own params)
                const childComponents = [];
                for (const comp of bomAssets) {
                    // Check if the product has its own design_param_definition_id
                    const [pp] = await this.orm.read(
                        "product.product", [comp.product_id],
                        ["design_param_definition_id"]
                    );
                    if (pp && pp.design_param_definition_id) {
                        const defId = pp.design_param_definition_id[0];
                        // Skip if same as main definition
                        if (defId === this.props.definitionId) continue;
                        const [childDef] = await this.orm.read(
                            "design.param.definition", [defId],
                            ["code", "name", "design_params_definition"]
                        );
                        if (childDef) {
                            childComponents.push({
                                productId: comp.product_id,
                                productName: comp.product_name,
                                definitionId: defId,
                                definitionCode: childDef.code,
                                definitionName: childDef.name,
                                paramDefinition: childDef.design_params_definition || [],
                            });
                        }
                    }
                }
                this.state.childComponents = childComponents;

                // Load all variant textures for accessory components (no 3D)
                const accessoryVariants = [];
                for (const comp of bomAssets) {
                    if (comp.assets.models_3d.length === 0 && comp.assets.textures.length > 0) {
                        const variants = await this.orm.call(
                            "product.product", "get_template_variant_assets",
                            [comp.product_id]
                        );
                        if (variants.length > 0) {
                            // Extract clean component name (before parenthesis)
                            const name = comp.product_name.replace(/\s*\(.*\)$/, "");
                            accessoryVariants.push({
                                bomProductId: comp.product_id,
                                componentName: name,
                                variants: variants,
                            });
                        }
                    }
                }
                this.state.accessoryVariants = accessoryVariants;

                // Load all variant 3D assets for components with GLB models
                const modelVariants = {};
                for (const comp of bomAssets) {
                    if (comp.assets.models_3d.length > 0) {
                        const allVariants = await this.orm.call(
                            "product.product", "get_template_variant_all_assets",
                            [comp.product_id]
                        );
                        if (allVariants.length > 1) {
                            modelVariants[comp.product_id] = allVariants;
                        }
                    }
                }
                this.state.modelVariants = modelVariants;
            }
        } catch (e) {
            console.warn("Could not load BoM design assets:", e.message);
        }

        this.state.loading = false;
    }

    onLotCreated(lotId, params) {
        if (this.props.onLotCreated) {
            this.props.onLotCreated(lotId, params);
        }
        this.props.close();
    }

    onClose() {
        this.props.close();
    }
}
