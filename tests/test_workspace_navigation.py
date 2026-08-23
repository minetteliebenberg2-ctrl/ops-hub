import ast
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from gui.module_host import ModuleHost
from gui.duplicate_email_window import _reflow_toolbar


ROOT = Path(__file__).parents[1]


class FakeWidget:
    def __init__(self, master=None, **kwargs):
        self.master = master
        self.kwargs = kwargs
        self.destroy_count = 0
        self.pack_calls = []
        self.focus_count = 0
        self.exists = True

    def pack(self, **kwargs):
        self.pack_calls.append(kwargs)

    def destroy(self):
        self.destroy_count += 1
        self.exists = False

    def winfo_exists(self):
        return self.exists

    def focus_set(self):
        self.focus_count += 1


class FakeToolbar:
    def __init__(self, children):
        self.children = children
        self.configured_columns = []

    def winfo_children(self):
        return self.children

    def grid_columnconfigure(self, column, **kwargs):
        self.configured_columns.append((column, kwargs))


class FakeToolbarButton:
    def __init__(self, name, events):
        self.name = name
        self.events = events

    def pack_forget(self):
        self.events.append(("forget", self.name))

    def grid(self, **kwargs):
        self.events.append(("grid", self.name, kwargs))


class ModuleHostTests(unittest.TestCase):
    def make_host(self):
        host = object.__new__(ModuleHost)
        host.active_frame = None
        host.after_idle = lambda callback: callback()
        return host

    def test_mounts_frame_and_transfers_focus(self):
        host = self.make_host()
        frame = FakeWidget(host)

        self.assertIs(host.mount(lambda master: frame), frame)
        self.assertIs(host.active_frame, frame)
        self.assertEqual(frame.focus_count, 1)
        self.assertEqual(
            frame.pack_calls[0]["padx"],
            ModuleHost.WORKSPACE_PADDING,
        )

    def test_switch_destroys_previous_once_and_resize_does_not_recreate(self):
        host = self.make_host()
        first = FakeWidget(host)
        second = FakeWidget(host)
        factory = MagicMock(side_effect=[first, second])

        host.mount(factory)
        host.mount(factory)

        self.assertEqual(first.destroy_count, 1)
        self.assertEqual(second.destroy_count, 0)
        self.assertEqual(factory.call_count, 2)

    def test_creation_failure_is_contained(self):
        host = self.make_host()
        error_frame = FakeWidget(host)
        host._create_error_frame = MagicMock(return_value=error_frame)

        result = host.mount(
            lambda master: (_ for _ in ()).throw(RuntimeError("failed"))
        )

        self.assertIs(result, error_frame)
        host._create_error_frame.assert_called_once()


class WorkspaceSourceContractTests(unittest.TestCase):
    """Contracts for the workspace chrome. Navigation moved out of
    gui/main_window.py into gui/components/module_nav.py when the sidebar was
    replaced by horizontal top tabs, so the navigation assertions now target
    that file - the behaviours themselves still matter."""

    def setUp(self):
        self.main_source = ROOT.joinpath("gui", "main_window.py").read_text(
            encoding="utf-8"
        )
        self.nav_source = ROOT.joinpath(
            "gui", "components", "module_nav.py"
        ).read_text(encoding="utf-8")

    def test_navigation_label_uses_module_name(self):
        """Tab labels are built from module.info.name, never a raw module_id."""
        self.assertIn("name = module.info.name", self.nav_source)
        tree = ast.parse(self.nav_source)
        returns_using_name = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id == "name"
        ]
        self.assertTrue(returns_using_name)

    def test_textual_icon_metadata_is_mapped_not_printed(self):
        """A module.info.icon like "settings" is a *text* icon name. It must be
        translated through ICON_MAP into a glyph, never concatenated into the
        label raw, which is what produced labels like "settings Settings"."""
        self.assertIn("ICON_MAP", self.nav_source)
        self.assertIn("if raw_icon in cls.ICON_MAP", self.nav_source)

    def test_navigation_avoids_global_event_binds(self):
        """Global bind_all/<MouseWheel> handlers leak across every widget in the
        app and break scrolling inside module views."""
        for source in (self.main_source, self.nav_source):
            self.assertNotIn("bind_all", source)
            self.assertNotIn("<MouseWheel>", source)

    def test_home_and_modules_share_module_host_margins(self):
        self.assertIn("self.content.show_home()", self.main_source)
        self.assertIn(
            "self.content.mount(utility.create_window)",
            self.main_source,
        )

    def test_disabled_and_hidden_contract_is_preserved(self):
        """visible=False means no tab at all; enabled=False means a greyed-out
        tab. Both were silently dropped in the top-tab redesign."""
        self.assertIn("if m.info.visible", self.nav_source)
        self.assertIn(
            '"normal" if module.info.enabled else "disabled"',
            self.nav_source,
        )
        self.assertIn("if not utility.info.enabled", self.main_source)

    def test_treeview_selection_modes_remain_extended(self):
        paths = [
            ROOT / "modules" / "communications" / "windows.py",
            ROOT / "gui" / "duplicate_email_window.py",
            ROOT / "modules" / "crm" / "windows.py",
            ROOT / "modules" / "empty_folder_remover" / "windows.py",
        ]
        for path in paths:
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("bind_all", source, path)
            for node in ast.walk(ast.parse(source)):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "Treeview"
                ):
                    selectmodes = [
                        keyword.value
                        for keyword in node.keywords
                        if keyword.arg == "selectmode"
                    ]
                    self.assertTrue(selectmodes, path)
                    self.assertEqual(selectmodes[0].value, "extended", path)

    def test_communications_wide_tables_have_horizontal_scrollbars(self):
        for path in (
            ROOT / "modules" / "communications" / "windows.py",
            ROOT / "gui" / "duplicate_email_window.py",
        ):
            source = path.read_text(encoding="utf-8")
            self.assertIn('orient="horizontal"', source, path)
            self.assertIn("xscrollcommand=", source, path)

    def test_toolbar_removes_every_pack_before_using_grid(self):
        events = []
        toolbar = FakeToolbar(
            [
                FakeToolbarButton("one", events),
                FakeToolbarButton("two", events),
                FakeToolbarButton("three", events),
            ]
        )

        _reflow_toolbar(toolbar, columns=2)

        self.assertEqual(
            events[:3],
            [
                ("forget", "one"),
                ("forget", "two"),
                ("forget", "three"),
            ],
        )
        self.assertTrue(all(event[0] == "grid" for event in events[3:]))


if __name__ == "__main__":
    unittest.main()
