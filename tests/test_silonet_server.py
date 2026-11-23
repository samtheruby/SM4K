"""
silonet.server: SiloServer answers the Plex paths Uno's object model and screens ask for, from Silo's API, as
Plex-shaped XML; and SiloServerManager holds the Silo servers the way plexapp.SERVERMANAGER held Plex's.
"""

from kodienv import ENV
from plexnet import plexlibrary
from silonet.client import Credentials, DeviceIdentity, SiloClient
from silonet.server import SiloServer
from silonet.servermanager import SiloServerManager

from lib.silo import StoredServer

from .base import KodiTestCase
from .silonet_fakes import FakeResponse, FakeSession

DEVICE = DeviceIdentity('dev1', 'Living room', 'kodi', '0.4.4')
LIBRARIES = FakeResponse(
    200,
    {
        'items': [
            {
                'id': 'lib-m',
                'name': '1080p Movies',
                'type': 'movies',
                'sort_order': 1,
                'box_sets_enabled': False,
                'poster_url': 'https://silo.lan/posters/lib-m.webp',
            },
            {'id': 'lib-s', 'name': 'Shows', 'type': 'series', 'sort_order': 2, 'box_sets_enabled': False},
            {'id': 'lib-x', 'name': 'test-files', 'type': 'mixed', 'sort_order': 3, 'box_sets_enabled': False},
        ]
    },
)


def server(session):
    client = SiloClient('http://silo.lan:8090', DEVICE, Credentials(accessToken='A1', profileId='p1'), session=session)
    return SiloServer(StoredServer('http://silo.lan:8090', 'srv-1', 'Silo'), client)


class SiloServerTest(KodiTestCase):
    def test_library_sections_come_from_user_libraries(self):
        session = FakeSession(LIBRARIES)

        sections = plexlibrary.Library(None, server=server(session)).sections()

        self.assertEqual(
            [(s.key, s.title, s.type) for s in sections],
            [('lib-m', '1080p Movies', 'movie'), ('lib-s', 'Shows', 'show')],
        )
        self.assertEqual(session.calls[0]['url'], 'http://silo.lan:8090/api/v2/user/libraries')
        self.assertEqual(session.calls[0]['headers']['X-Profile-Id'], 'p1')

    def test_mixed_library_is_left_out(self):
        container = server(FakeSession(LIBRARIES)).query('/library/sections')

        self.assertNotIn('lib-x', [d.get('key') for d in container])

    def test_unmapped_path_returns_empty_container_and_logs_once(self):
        srv = server(FakeSession())

        first = srv.query('/hubs/sections/home')
        srv.query('/hubs/sections/home')

        self.assertEqual(first.tag, 'MediaContainer')
        self.assertEqual(len(list(first)), 0)
        self.assertEqual(sum('/hubs/sections/home' in msg for msg, _ in ENV.log_lines), 1)

    def test_identity_and_urls(self):
        srv = server(FakeSession())

        self.assertEqual((srv.uuid, srv.name), ('srv-1', 'Silo'))
        self.assertEqual(srv.buildUrl('/api/v2/x'), 'http://silo.lan:8090/api/v2/x')
        self.assertEqual(srv.getImageTranscodeURL('https://silo.lan/p.webp', 300, 450), 'https://silo.lan/p.webp')


class SiloServerManagerTest(KodiTestCase):
    def test_holds_the_selected_server(self):
        srv = server(FakeSession())
        manager = SiloServerManager([srv])

        self.assertIs(manager.selectedServer, srv)
        self.assertEqual(manager.getServers(), [srv])
        self.assertIs(manager.getServer('srv-1'), srv)
        self.assertEqual(manager.serversByUuid, {'srv-1': srv})
        self.assertTrue(manager.serversKnown())
