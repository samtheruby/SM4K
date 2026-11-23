"""
lib/silo.py init(): SM4K's start-up. With no server it asks for one, with no session it signs in with a code,
and then it hands Uno's screens a SiloAccount and a SiloServerManager through plexapp, the way plex.init() handed
them Plex's.
"""

import json
from collections import deque
from unittest import mock

from kodienv import ENV
from plexnet import plexapp
from plexnet import util as pnUtil
from silonet import auth

from lib import silo

from .base import KodiTestCase, fixture
from .silonet_fakes import FakeResponse, FakeSession, problem

PROFILES = FakeResponse(200, {'items': [{'id': 'p1', 'name': 'Sam', 'has_pin': False, 'is_primary': True}]})
STORED = {'base_url': 'http://silo.lan:8090', 'server_id': 'srv-1', 'name': 'Silo'}


def approved(access='A1'):
    return auth.PollResult(
        {
            'status': 'approved',
            'profile_id': 'p1',
            'profile_token': '',
            'tokens': {'access_token': access, 'refresh_token': 'R1', 'user': {'role': 'admin'}},
        }
    )


def probeAnswers():
    return [
        FakeResponse(200, json.loads(fixture('silonet', 'system_info.json'))),
        FakeResponse(200, {'server_id': 'srv-1'}),
        FakeResponse(200, json.loads(fixture('silonet', 'theme_branding.json'))),
    ]


class SiloStartupTest(KodiTestCase):
    def setUp(self):
        super().setUp()
        self.patches = [
            mock.patch.object(plexapp, 'ACCOUNT', None),
            mock.patch.object(plexapp, 'SERVERMANAGER', None),
            mock.patch.object(pnUtil, 'ACCOUNT', None, create=True),
            mock.patch.object(pnUtil, 'SERVERMANAGER', None, create=True),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_first_run_asks_for_server_then_code(self):
        ENV.dialog_answers = deque(['silo.lan:8090'])
        session = FakeSession(*probeAnswers(), PROFILES)

        with mock.patch.object(silo, 'signIn', return_value=approved()) as signIn:
            self.assertTrue(silo.init(session=session))

        signIn.assert_called_once()
        self.assertEqual([s.serverId for s in silo.storedServers()], ['srv-1'])
        self.assertEqual(plexapp.ACCOUNT.ID, 'p1')
        self.assertTrue(plexapp.ACCOUNT.isAdmin)
        self.assertEqual(plexapp.SERVERMANAGER.selectedServer.uuid, 'srv-1')
        stored = json.loads(ENV.settings[silo.CREDENTIALS_SETTING])
        self.assertEqual((stored['server_id'], stored['access_token'], stored['profile_id']), ('srv-1', 'A1', 'p1'))

    def test_signed_in_single_profile_goes_home(self):
        ENV.settings[silo.SERVERS_SETTING] = json.dumps([STORED])
        ENV.settings[silo.CREDENTIALS_SETTING] = json.dumps(
            {'server_id': 'srv-1', 'access_token': 'A1', 'refresh_token': 'R1', 'profile_id': 'p1'}
        )
        session = FakeSession(PROFILES)

        with mock.patch.object(silo, 'signIn') as signIn:
            self.assertTrue(silo.init(session=session))

        signIn.assert_not_called()
        self.assertEqual(session.calls[0]['headers']['Authorization'], 'Bearer A1')
        self.assertEqual([u.title for u in plexapp.ACCOUNT.homeUsers], ['Sam'])
        self.assertTrue(plexapp.ACCOUNT.isAuthenticated)

    def test_ended_session_signs_in_again(self):
        ENV.settings[silo.SERVERS_SETTING] = json.dumps([STORED])
        ENV.settings[silo.CREDENTIALS_SETTING] = json.dumps(
            {'server_id': 'srv-1', 'access_token': 'OLD', 'refresh_token': 'R0', 'profile_id': 'p1'}
        )
        session = FakeSession(problem(401, 'invalid_token'), problem(401, 'session_expired'), PROFILES)

        with mock.patch.object(silo, 'signIn', return_value=approved('NEW')):
            self.assertTrue(silo.init(session=session))

        self.assertEqual(session.calls[-1]['headers']['Authorization'], 'Bearer NEW')

    def test_credentials_of_another_server_are_ignored(self):
        ENV.settings[silo.SERVERS_SETTING] = json.dumps([STORED])
        ENV.settings[silo.CREDENTIALS_SETTING] = json.dumps({'server_id': 'other', 'access_token': 'X'})

        with mock.patch.object(silo, 'signIn', return_value=approved()) as signIn:
            silo.init(session=FakeSession(PROFILES))

        signIn.assert_called_once()

    def test_no_server_entered_ends_start_up(self):
        ENV.dialog_answers = deque([''])

        self.assertFalse(silo.init(session=FakeSession()))

    def test_unreachable_server_says_so(self):
        ENV.settings[silo.SERVERS_SETTING] = json.dumps([STORED])
        ENV.settings[silo.CREDENTIALS_SETTING] = json.dumps(
            {'server_id': 'srv-1', 'access_token': 'A1', 'refresh_token': 'R1', 'profile_id': 'p1'}
        )
        import requests

        with mock.patch.object(silo.util, 'messageDialog') as dialog:
            self.assertFalse(silo.init(session=FakeSession(requests.ConnectionError('down'))))

        self.assertIn('Silo server', dialog.call_args[0][1])
