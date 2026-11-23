"""
silonet.server_info.probe(): telling a Silo server SM4K can talk to from anything else at an address. Fixtures
are the user's Silo (build-2987) answers, with the address and server ID replaced.
"""

import json

import requests
from silonet import errors
from silonet.client import DeviceIdentity
from silonet.server_info import probe

from .base import KodiTestCase, fixture
from .silonet_fakes import FakeResponse, FakeSession

DEVICE = DeviceIdentity('dev1', 'Living room', 'kodi', '0.4.4')


def recorded(name):
    return json.loads(fixture('silonet', name))


class ProbeTest(KodiTestCase):
    def test_probe_reads_identity_and_info(self):
        session = FakeSession(
            FakeResponse(200, recorded('system_info.json')), FakeResponse(200, recorded('system_identity.json'))
        )

        info = probe('http://silo.lan:8090', DEVICE, session=session)

        self.assertEqual(info.serverId, '00000000-0000-4000-8000-000000000001')
        self.assertEqual(info.serverVersion, 'a2ec4094')
        self.assertEqual(info.apiMajor, 2)
        self.assertTrue(info.contractDigest.startswith('e9fc1d87'))
        self.assertEqual(
            [c['url'] for c in session.calls],
            ['http://silo.lan:8090/api/v2/system/info', 'http://silo.lan:8090/api/v2/system/identity'],
        )
        self.assertTrue(all('Authorization' not in c['headers'] for c in session.calls))

    def test_rejects_other_api_major(self):
        answer = dict(recorded('system_info.json'), api_major=3)
        session = FakeSession(FakeResponse(200, answer))

        with self.assertRaises(errors.SiloIncompatible) as caught:
            probe('http://silo.lan:8090', DEVICE, session=session)

        self.assertIn('a2ec4094', caught.exception.detail)

    def test_not_a_silo_server_is_incompatible(self):
        session = FakeSession(FakeResponse(404))

        with self.assertRaises(errors.SiloIncompatible):
            probe('http://jellyfin.lan:8096', DEVICE, session=session)

    def test_unexpected_answer_is_incompatible(self):
        session = FakeSession(FakeResponse(200, {'server_version': 'x'}))

        with self.assertRaises(errors.SiloIncompatible):
            probe('http://silo.lan:8090', DEVICE, session=session)

    def test_unreachable_is_unavailable(self):
        session = FakeSession(requests.ConnectionError('refused'))

        with self.assertRaises(errors.SiloUnavailable):
            probe('http://silo.lan:8090', DEVICE, session=session)
