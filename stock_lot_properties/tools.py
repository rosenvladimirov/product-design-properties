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
"""Сурово четене на поле Properties — поведението на 18.0 в 19.0."""
import copy

from odoo.orm.fields_properties import Property


def stored_properties(record, field_name):
    """Записаният речник на поле Properties (име → стойност), дълбоко копие.

    В 18.0 ``Properties.convert_to_record`` връщаше копие на записания
    речник. В 19.0 връща обект ``Property`` (ORM/fields_properties.py:183,
    810-838), който при обхождане минава през формата за четене:

    - изборът (selection) идва като ЕТИКЕТ, не като ключ;
    - ``0`` / ``""`` идват като ``False``;
    - many2one/many2many идват като записи, tags — като низ с етикети;
    - ключ извън текущата дефиниция изчезва от обхождането.

    Затова ``dict(record.<поле>)`` вече не е записаното. Тук се чете
    суровият речник от ``Property._values`` — точно каквото връщаше 18.0
    (празното е ``{}``, не ``False``; всички извикващи го ползват с
    ``or {}``). Не прави ``sudo`` — правата са грижа на извикващия.
    """
    record.ensure_one()
    value = record[field_name]
    if isinstance(value, Property):
        value = value._values
    return copy.deepcopy(dict(value or {}))
