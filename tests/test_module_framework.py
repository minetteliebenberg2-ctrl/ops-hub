import inspect
from pathlib import Path
import sys
import tempfile
import unittest

from framework.base_module import BaseModule
from framework.module_info import ModuleInfo
from framework.module_manager import ModuleManager


MODULE_SOURCE = """
from framework.base_module import BaseModule
from framework.module_info import ModuleInfo

class {class_name}(BaseModule):
    module_info = ModuleInfo({module_id!r}, {name!r}, {description!r}, category="Test", sort_order={sort_order})

    def create_window(self, master):
        return None
"""


class ModuleFrameworkTests(unittest.TestCase):
    def make_package(self, root, modules):
        package = root / "test_modules"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        for folder_name, source in modules.items():
            folder = package / folder_name
            folder.mkdir()
            (folder / "__init__.py").write_text("", encoding="utf-8")
            (folder / "module.py").write_text(source, encoding="utf-8")
        return package

    def test_valid_discovery_order_idempotency_and_no_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = self.make_package(root, {
                "zeta": MODULE_SOURCE.format(class_name="Zeta", module_id="zeta", name="Zeta", description="Zeta", sort_order=20),
                "alpha": MODULE_SOURCE.format(class_name="Alpha", module_id="alpha", name="Alpha", description="Alpha", sort_order=10),
            })
            sys.path.insert(0, str(root))
            try:
                manager = ModuleManager(package, "test_modules")
                first = manager.discover()
                second = manager.discover()
                self.assertEqual(first.final_order, ["alpha", "zeta"])
                self.assertEqual(second.final_order, first.final_order)
                self.assertEqual(len(manager.list_modules()), 2)
            finally:
                sys.path.remove(str(root))

    def test_failure_isolation_and_duplicate_id_reporting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = self.make_package(root, {
                "good": MODULE_SOURCE.format(class_name="Good", module_id="same", name="Good", description="Good", sort_order=1),
                "duplicate": MODULE_SOURCE.format(class_name="Duplicate", module_id="same", name="Duplicate", description="Duplicate", sort_order=2),
                "broken": "raise RuntimeError('broken import')\n",
                "invalid": "class Invalid:\n    pass\n",
                "constructor": "from framework.base_module import BaseModule\nfrom framework.module_info import ModuleInfo\nclass Constructor(BaseModule):\n    module_info = ModuleInfo('constructor', 'Constructor', 'Constructor')\n    def __init__(self): raise RuntimeError('broken constructor')\n",
            })
            sys.path.insert(0, str(root))
            try:
                report = ModuleManager(package, "test_modules").discover()
                stages = {(failure.module_name, failure.stage) for failure in report.failures}
                self.assertIn("same", report.duplicate_ids)
                self.assertIn(("broken", "import"), stages)
                self.assertIn(("invalid", "inspection"), stages)
                self.assertIn(("constructor", "instantiation"), stages)
                self.assertEqual(report.registered_module_ids, ["same"])
            finally:
                sys.path.remove(str(root))

    def test_duplicate_display_names_are_reported_without_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = self.make_package(root, {
                "first": MODULE_SOURCE.format(class_name="First", module_id="first", name="Shared Name", description="First", sort_order=1),
                "second": MODULE_SOURCE.format(class_name="Second", module_id="second", name="Shared Name", description="Second", sort_order=2),
            })
            sys.path.insert(0, str(root))
            try:
                manager = ModuleManager(package, "test_modules")
                report = manager.discover()
                self.assertEqual(report.registered_module_ids, ["first", "second"])
                self.assertEqual(report.duplicate_names, ["Shared Name"])
                self.assertEqual(report.final_order, ["first", "second"])
            finally:
                sys.path.remove(str(root))

    def test_duplicate_instance_is_rejected(self):
        manager = ModuleManager()

        class Example(BaseModule):
            module_info = ModuleInfo("example", "Example", "Example")

        instance = Example()
        manager.register(instance)
        with self.assertRaises(ValueError):
            manager.register(instance)

    def test_disabled_modules_are_reported_and_registered(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = MODULE_SOURCE.replace("sort_order={sort_order}", "sort_order={sort_order}, enabled=False")
            package = self.make_package(root, {"disabled": source.format(class_name="Disabled", module_id="disabled", name="Disabled", description="Disabled", sort_order=1)})
            sys.path.insert(0, str(root))
            try:
                manager = ModuleManager(package, "test_modules")
                report = manager.discover()
                self.assertEqual(report.disabled_module_ids, ["disabled"])
                self.assertFalse(manager.get("disabled").info.enabled)
            finally:
                sys.path.remove(str(root))

    def test_production_registration_and_launcher_contract(self):
        from framework.module_manager import module_manager
        from gui.main_window import MainWindow

        report = module_manager.discover()
        self.assertEqual(
            set(report.registered_module_ids),
            {
                module.info.module_id
                for module in module_manager.list_modules()
            },
        )
        self.assertEqual(
            len(report.registered_module_ids),
            len(set(report.registered_module_ids)),
        )
        self.assertGreater(len(report.registered_module_ids), 0)
        self.assertIn("manager", inspect.signature(MainWindow.__init__).parameters)
        launcher_text = Path(__file__).parents[1].joinpath("launcher.py").read_text(encoding="utf-8")
        self.assertIn("module_manager.discover()", launcher_text)
        self.assertNotIn("from modules.", launcher_text)
        self.assertNotIn("Utility()", launcher_text)


if __name__ == "__main__":
    unittest.main()
