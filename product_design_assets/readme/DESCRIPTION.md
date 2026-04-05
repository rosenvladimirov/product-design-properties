Links design visual assets (GLB 3D models, SVG profiles, PNG/JPG textures,
DXF drawings) to `product.product` and `product.template` via a M2M to
`ir.attachment`.  These assets are consumed by:

- `sale_design_configurator` — 3D preview of configured products
- Design configurators embedded in e-commerce flows
- Manufacturing documentation exports

The module groups assets by type and exposes RPC methods to fetch them
efficiently, including per-variant asset sets (e.g. different GLB models
for different slab types or different textures per coating).
