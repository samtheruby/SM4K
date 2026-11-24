"""
The settings screen offers nothing that only a Plex server or plex.tv reads (Phase 9's settings pass): the Network
section - local mode, insecure connections, LAN discovery and GDM, plex.direct mapping, manual connections - set how
the add-on reached Plex servers, and a Silo server is reached at the one address it was added by.

Importing lib.windows.* starts lib.player's monitor thread unless abort_requested is set first.
"""

from kodienv import ENV

ENV.abort_requested = True
from lib.windows import settings

from .base import KodiTestCase

PLEX_CONNECTION = {
    'local_mode',
    'allow_insecure',
    'smart_discover_local',
    'prefer_local',
    'gdm_discovery',
    'handle_plexdirect',
    'force_pd_mapping',
    'manual_ip_0',
    'manual_port_0',
    'manual_ip_1',
    'manual_port_1',
}


class SiloSettingsTest(KodiTestCase):
    def offered(self):
        # a section can hold None for a setting this platform leaves out
        return {s.ID for _, section in settings.Settings.SETTINGS.values() for s in section if s is not None}

    def test_no_network_section(self):
        self.assertNotIn('network', settings.Settings.SECTION_IDS)
        self.assertNotIn('network', settings.Settings.SETTINGS)

    def test_no_plex_connection_settings(self):
        self.assertEqual(set(), PLEX_CONNECTION & self.offered())

    def test_every_section_listed_is_there(self):
        self.assertEqual(set(settings.Settings.SECTION_IDS), set(settings.Settings.SETTINGS))
