"""
A library's menu (the sidebar's context press, LibraryWindow.sectionMenu()): path mapping is one Map path button,
which opens Kodi's folder selector for the Kodi source the library's folder is reached on; Remove path mapping once
it's mapped. The server's own folder (/data/media/...) isn't shown: it means nothing on the Kodi side.
"""

from collections import deque
from unittest import mock

from kodienv import ENV

ENV.abort_requested = True
from plexnet import plexlibrary

from lib.path_mapping import pmm
from lib.windows import library
from lib.windows.dialog import GROUP

from .base import KodiTestCase, ensure_plex_interface
from .silonet_fakes import FakeSession
from .test_silo_path_mapping import LIBRARY_PATHS, SERVER_ROOT
from .test_silonet_detail import server
from .test_silonet_library import LIBRARIES

SHARE = 'smb://ruby/media/radarr-sqp1/'


class MapPathMenuTest(KodiTestCase):
    def setUp(self):
        super().setUp()
        ensure_plex_interface()
        ENV.settings['path_mapping'] = 'true'
        self.section = plexlibrary.Library(None, server=server(FakeSession(LIBRARIES, LIBRARY_PATHS))).sections()[0]
        self.map = {}
        for patch in (
            mock.patch.object(pmm, 'PATH_MAP', self.map),
            mock.patch.object(pmm, 'save', return_value=True),
            mock.patch.object(library.plexapp, 'ACCOUNT', mock.Mock(isAdmin=False)),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        item = mock.Mock(dataSource=self.section)
        item.getProperty = lambda name: '1' if name == 'item' else ''
        self.window = library.LibraryWindow.__new__(library.LibraryWindow)
        self.window.sectionList = mock.Mock(getSelectedItem=lambda: item)
        self.window._rebuildSidebar = mock.Mock()

    def menu(self, *choices):
        """The menu's rows, (key, label), each time it shows while the user chooses choices in turn, then closes it."""
        shown = []

        def picker(heading, options, on_choice=None, **kwargs):
            for choice in choices:
                shown.append([option[:2] for option in options])
                options = on_choice(choice)[0]
            shown.append([option[:2] for option in options])

        with mock.patch.object(library, 'showOptionsDialog', side_effect=picker):
            self.window.sectionMenu()
        return shown

    def test_map_path_is_a_button_and_shows_no_server_folder(self):
        rows = self.menu()[0]

        self.assertIn(('map_path', 'Map path'), rows)
        self.assertNotIn(GROUP, [key for key, _label in rows])
        self.assertFalse([label for _key, label in rows if '/data/media' in label])

    def test_map_path_opens_the_folder_selector_and_maps_the_library(self):
        ENV.dialog_answers = deque([SHARE])

        _before, after = self.menu('map_path')

        browse = next(call for call in ENV.dialog_calls if call[0] == 'browse')
        self.assertEqual(browse[1][1], 'Select Kodi source for 2160p Movies')
        self.assertEqual(self.map, {'Silo': {SHARE: SERVER_ROOT}})
        self.assertIn(('unmap_path', 'Remove path mapping'), after)
        self.assertNotIn(('map_path', 'Map path'), after)

    def test_a_cancelled_selector_maps_nothing(self):
        ENV.dialog_answers = deque([''])

        _before, after = self.menu('map_path')

        self.assertEqual(self.map, {})
        self.assertIn(('map_path', 'Map path'), after)

    def test_remove_path_mapping_unmaps_the_library(self):
        self.map['Silo'] = {SHARE: SERVER_ROOT}

        before, after = self.menu('unmap_path')

        self.assertIn(('unmap_path', 'Remove path mapping'), before)
        self.assertEqual(self.map, {'Silo': {}})
        self.assertIn(('map_path', 'Map path'), after)
