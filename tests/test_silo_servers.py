"""
lib/silo.py: the Silo servers SM4K knows, stored in the add-on's settings, and the dialog that adds one by its
address after checking that a Silo server answers there.
"""

import json
from collections import deque
from unittest import mock

import requests
from kodienv import ENV
from silonet import errors
from silonet.client import DeviceIdentity
from silonet.discovery import Found

from lib import silo

from .base import KodiTestCase, fixture
from .silonet_fakes import FakeResponse, FakeSession

DEVICE = DeviceIdentity('dev1', 'Living room', 'kodi', '0.4.4')


def silo_answers(serverId='00000000-0000-4000-8000-000000000001'):
    return [
        FakeResponse(200, json.loads(fixture('silonet', 'system_info.json'))),
        FakeResponse(200, {'server_id': serverId}),
        FakeResponse(200, json.loads(fixture('silonet', 'theme_branding.json'))),
    ]


class StoredServersTest(KodiTestCase):
    def test_add_probes_and_stores(self):
        stored = silo.addServer('http://silo.lan:8090', DEVICE, session=FakeSession(*silo_answers()))

        self.assertEqual(
            (stored.baseUrl, stored.serverId, stored.name),
            ('http://silo.lan:8090', '00000000-0000-4000-8000-000000000001', 'Silo'),
        )
        self.assertEqual([s.baseUrl for s in silo.storedServers()], ['http://silo.lan:8090'])

    def test_same_server_new_address_updates(self):
        silo.addServer('http://silo.lan:8090', DEVICE, session=FakeSession(*silo_answers()))
        silo.addServer('https://media.example.com/silo/', DEVICE, session=FakeSession(*silo_answers()))

        self.assertEqual([s.baseUrl for s in silo.storedServers()], ['https://media.example.com/silo'])

    def test_a_bare_host_gets_http(self):
        session = FakeSession(*silo_answers())

        stored = silo.addServer('silo.lan:8090', DEVICE, session=session)

        self.assertEqual(stored.baseUrl, 'http://silo.lan:8090')
        self.assertEqual(session.calls[0]['url'], 'http://silo.lan:8090/api/v2/system/info')

    def test_rejects_unsupported_server(self):
        with self.assertRaises(errors.SiloIncompatible):
            silo.addServer('http://jellyfin.lan:8096', DEVICE, session=FakeSession(FakeResponse(404)))

        self.assertEqual(silo.storedServers(), [])

    def test_remove_server(self):
        silo.addServer('http://silo.lan:8090', DEVICE, session=FakeSession(*silo_answers('s1')))
        silo.addServer('http://other.lan:8090', DEVICE, session=FakeSession(*silo_answers('s2')))

        silo.removeServer('s1')

        self.assertEqual([s.serverId for s in silo.storedServers()], ['s2'])

    def test_unreadable_setting_means_no_servers(self):
        ENV.settings['silo_servers_json'] = 'not json'

        self.assertEqual(silo.storedServers(), [])


class AddServerDialogTest(KodiTestCase):
    def setUp(self):
        super().setUp()
        self.found = []
        patch = mock.patch.object(silo.discovery, 'find', side_effect=lambda: self.found)
        patch.start()
        self.addCleanup(patch.stop)

    def test_servers_found_on_the_network_come_first(self):
        self.found = [Found('Silo', 'http://silo.lan:8090', '00000000-0000-4000-8000-000000000001')]
        ENV.dialog_answers = deque([0])

        stored = silo.addServerDialog(DEVICE, session=FakeSession(*silo_answers()))

        self.assertEqual(stored.baseUrl, 'http://silo.lan:8090')
        select = [c for c in ENV.dialog_calls if c[0] == 'select'][0]
        self.assertEqual(select[1][1], ['Silo (http://silo.lan:8090)', 'Enter address'])
        self.assertFalse([c for c in ENV.dialog_calls if c[0] == 'input'])

    def test_enter_address_from_the_list(self):
        self.found = [Found('Silo', 'http://silo.lan:8090', '00000000-0000-4000-8000-000000000001')]
        ENV.dialog_answers = deque([1, 'silo.lan:8091'])

        stored = silo.addServerDialog(DEVICE, session=FakeSession(*silo_answers()))

        self.assertEqual(stored.baseUrl, 'http://silo.lan:8091')

    def test_dialog_adds_the_server_entered(self):
        ENV.dialog_answers = deque(['silo.lan:8090'])

        stored = silo.addServerDialog(DEVICE, session=FakeSession(*silo_answers()))

        self.assertEqual(stored.baseUrl, 'http://silo.lan:8090')

    def test_unreachable_address_offers_to_try_again(self):
        ENV.dialog_answers = deque(['silo.lan:8090', True, 'silo.lan:8091'])
        session = FakeSession(requests.ConnectionError('refused'), *silo_answers())

        stored = silo.addServerDialog(DEVICE, session=session)

        self.assertEqual(stored.baseUrl, 'http://silo.lan:8091')
        yesno = [c for c in ENV.dialog_calls if c[0] == 'yesno']
        self.assertIn('silo.lan:8090', yesno[0][1][1])

    def test_cancelled_entry_adds_nothing(self):
        ENV.dialog_answers = deque([''])

        self.assertIsNone(silo.addServerDialog(DEVICE))
        self.assertEqual(silo.storedServers(), [])
