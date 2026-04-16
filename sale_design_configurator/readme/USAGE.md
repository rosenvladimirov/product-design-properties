1.  Configure the product:

    - Set `design_param_definition_id` on the product template or
      variant.
    - Upload 3D / SVG / texture attachments on the product (see
      `product_design_assets`).

2.  On a sale order, add a line for the configured product.  A small
    _Configure_ button appears next to the product field.

3.  Click _Configure_ — the modal opens.  Adjust parameters with the
    sliders and selection buttons.  The 3D viewport updates live.
    The constraint panel shows errors and warnings in real time.

4.  Click _Create Design Lot_.  The lot is created, attached to the
    SO line, and the modal closes.

5.  Confirm the SO.  The generated MO picks up the design lot
    automatically via `lot_producing_ids`, and
    `_generate_design_matrix_moves` handles the rest.
