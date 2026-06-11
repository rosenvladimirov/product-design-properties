# Copyright 2024-2026 Rosen Vladimirov
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def post_init_hook(env):
    """Link demo GLB attachments to the demo product if product_design_assets is installed."""
    module = env["ir.module.module"].search(
        [("name", "=", "product_design_assets"), ("state", "=", "installed")]
    )
    if not module:
        return

    try:
        product = env.ref("mrp_design_matrix_roller_door.product_roller_shutter")
        att1 = env.ref("mrp_design_matrix_roller_door.attachment_rs_component_glb")
        att2 = env.ref("mrp_design_matrix_roller_door.attachment_rs_box_glb")
    except ValueError:
        return

    product.write({"design_asset_ids": [(4, att1.id), (4, att2.id)]})
