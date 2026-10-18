# Copyright 2024-2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)
#      https://www.gnu.org/licenses/agpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the AGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the AGPL-3.0-or-later.
def post_init_hook(env):
    """Закача демо GLB файловете към демо продукта.

    Само ако product_design_assets е инсталиран.
    """
    module = env["ir.module.module"].search(
        [("name", "=", "product_design_assets"), ("state", "=", "installed")]
    )
    if not module:
        return

    try:
        # 19: демото вече няма отделен product.product запис — взимаме
        # автоматично създадения вариант на шаблона
        product = env.ref(
            "mrp_design_matrix_roller_door.product_tmpl_roller_shutter"
        ).product_variant_id
        att1 = env.ref("mrp_design_matrix_roller_door.attachment_rs_component_glb")
        att2 = env.ref("mrp_design_matrix_roller_door.attachment_rs_box_glb")
    except ValueError:
        return

    product.write({"design_asset_ids": [(4, att1.id), (4, att2.id)]})
