1.  Upload attachments on the product form (Design tab).  The mimetype
    determines the asset type:

    - `model/gltf-binary` → 3D models (GLB)
    - `image/svg+xml` → SVG profile templates
    - `image/jpeg`, `image/png` → textures
    - `application/dxf` → 2D technical drawings

2.  Call RPC methods from the configurator:

    ```python
    # All assets of a variant grouped by type
    assets = product.get_design_assets_by_type(product_id)

    # Variants with only textures (accessory swatches)
    variants = product.get_template_variant_assets(product_id)

    # Variants with 3D models (slab-swap GLB set)
    variants = product.get_template_variant_all_assets(product_id)
    ```
