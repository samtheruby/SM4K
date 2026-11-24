"""
lib/silo.py signIn(): Uno's PIN window showing Silo's sign-in code and link until someone approves it.
"""

from unittest import mock

from kodienv import ENV
from silonet import auth
from silonet.client import Credentials, DeviceIdentity, SiloClient

from lib import silo
from lib.windows import signin

from .base import KodiTestCase
from .silonet_fakes import FakeResponse, FakeSession
from .test_silonet_auth import TOKENS, polled, started

DEVICE = DeviceIdentity('dev1', 'Living room', 'kodi', '0.4.4')


def pinWindow():
    window = signin.PinLoginWindow.__new__(signin.PinLoginWindow)
    window._closing = False
    window._winID = None
    window.windowId = 13001
    window.abort = False
    window.closed = False

    def doClose():
        window.closed = True

    window.doClose = doClose
    return window


class SiloSignInTest(KodiTestCase):
    def signIn(self, session, window):
        client = SiloClient('http://silo.lan:8090', DEVICE, Credentials(), session=session)
        with mock.patch.object(signin.PinLoginWindow, 'create', return_value=window):
            return silo.signIn(client)

    def test_code_window_shows_spaced_code_and_link(self):
        window = pinWindow()

        window.setCode(auth.DeviceCode(started().json()))

        props = ENV.window_props[13001]
        self.assertEqual(props.get('pin'), '4821 7730')
        self.assertIn('http://silo.lan:8090/activate', props.get('instructions'))

    def test_approved_sign_in_returns_the_session(self):
        window = pinWindow()

        result = self.signIn(FakeSession(started(), polled('approved', tokens=TOKENS)), window)

        self.assertEqual(result.status, 'approved')
        self.assertEqual(result.accessToken, 'A1')
        self.assertEqual(ENV.window_props[13001].get('pin'), '4821 7730')
        self.assertTrue(window.closed)

    def test_back_returns_none_and_cancels(self):
        window = pinWindow()
        window.abort = True
        session = FakeSession(started(), FakeResponse(200, {'status': 'canceled'}))

        self.assertIsNone(self.signIn(session, window))

        self.assertTrue(session.calls[-1]['url'].endswith('/api/v2/auth/device/cancel'))
        self.assertTrue(window.closed)

    def test_refused_sign_in_tells_the_user(self):
        with mock.patch.object(silo.util, 'messageDialog') as dialog:
            result = self.signIn(FakeSession(started(), polled('denied')), pinWindow())

        self.assertIsNone(result)
        dialog.assert_called_once()
        self.assertIn('refused', dialog.call_args[0][1])
