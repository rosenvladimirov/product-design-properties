Industry sub-module for roller shutter manufacturers (tailored for
Teolino product line).  Parameters include slat type, drive type
(manual / electric), box size, rail type, width and height.

Provides matrix templates for both manual and electric roller
variants.  T2 material table drives slat quantity based on aperture
height; T3 operation table adds the motor fitting workorder only when
`drive_type == "electric"`.
