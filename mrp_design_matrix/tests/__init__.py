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
# 🚨 e59e50a изключи ВСИЧКИ импорти освен един („temporarily disable test imports
# to unblock demo upgrade") и това стоя ~2 месеца. Тест, който не се импортира, не
# може да падне — новите T3 тестове бяха мъртви при първото пускане.
# test_matrix_moves е върнат заедно с поправката за двойните workorders (ADR-0010).
# 🔲 test_design_context и test_ptav_resolution остават изключени — не са проверявани.
from . import test_attribute_roles
from . import test_matrix_moves
from . import test_lot_prefix_combination
from . import test_shop_context
