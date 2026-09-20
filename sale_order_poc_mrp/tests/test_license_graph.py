# Copyright 2026 Rosen Vladimirov
#
# This file is available under a DUAL LICENSE:
#   1. GNU Lesser General Public License v3.0 or later (LGPL-3.0-or-later)
#      https://www.gnu.org/licenses/lgpl-3.0.html
#   2. A commercial license from Rosen Vladimirov, for use without the obligations
#      of the LGPL. See LICENSE-COMMERCIAL.md. Contact: vladimirov.rosen@gmail.com
#
# Unless you hold a valid commercial license, your use of this file is governed
# by the LGPL-3.0-or-later.
import pathlib

from odoo.modules.module import get_manifest, get_module_path
from odoo.tests import tagged
from odoo.tests.common import BaseCase

MODULE = "sale_order_poc_mrp"
# LGPL гръбнакът не стъпва на AGPL и на собственически модули: на него
# стъпват и OPL, и AGPL листата (ADR sale-order-poc/0005, правило №0)
FORBIDDEN_LICENSES = {"AGPL-3", "OPL-1", "OEEL-1", "Other proprietary"}


@tagged("post_install", "-at_install")
class TestLicenseGraph(BaseCase):
    def _dependency_closure(self):
        """Всички модули, от които ядрото зависи, пряко и непряко."""
        seen = set()
        todo = list(get_manifest(MODULE)["depends"])
        while todo:
            name = todo.pop()
            if name in seen:
                continue
            seen.add(name)
            todo += get_manifest(name).get("depends", [])
        return seen

    def test_manifest_is_lgpl(self):
        self.assertEqual(get_manifest(MODULE)["license"], "LGPL-3")

    def test_no_dependency_on_agpl_or_proprietary(self):
        offenders = {
            name: get_manifest(name).get("license")
            for name in self._dependency_closure()
            if get_manifest(name).get("license") in FORBIDDEN_LICENSES
        }
        self.assertEqual(offenders, {})

    def test_every_file_carries_the_lgpl_header(self):
        root = pathlib.Path(get_module_path(MODULE))
        wrong = []
        for path in sorted(root.rglob("*")):
            if path.suffix not in (".py", ".xml") or "__pycache__" in path.parts:
                continue
            head = path.read_text(encoding="utf-8")[:1000]
            if "LGPL-3.0-or-later" not in head or "Affero" in head:
                wrong.append(str(path.relative_to(root)))
        self.assertEqual(wrong, [])
