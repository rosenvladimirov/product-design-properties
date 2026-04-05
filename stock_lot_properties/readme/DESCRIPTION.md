Adds a `design_params` Properties field on `stock.lot` driven by a
`design_param_definition_id` link.  This lets you store per-lot design
values (the actual dimensions, material choices, etc. for a specific
production run) with the same schema defined once in
`design.param.definition`.

The lot becomes the carrier of the design for a specific manufacturing
order — not the product variant, not the BoM.  Each lot has its own
`design_params` dictionary that the matrix engine reads at MO creation
time to compute moves and workorders.
