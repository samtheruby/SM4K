"""
SM4K's Silo session: signing in with a code shown on the TV (silonet.auth) through Uno's PIN window.
"""

from silonet import auth

from . import util
from .util import T
from .windows import signin

# how often a wait checks for Back while it sleeps
WAIT_STEP = 0.1

FAILURES = {
    'denied': (35244, 'Sign-in was refused.'),
    'expired': (35245, 'The code expired before it was approved. Please try again.'),
}


def signIn(client):
    """Show Silo's sign-in code until someone approves it: the approved auth.PollResult, or None."""
    window = signin.PinLoginWindow.create()

    def wait(seconds):
        for _ in range(max(1, int(seconds / WAIT_STEP))):
            if window.abort or util.MONITOR.waitForAbort(WAIT_STEP):
                return False
        return not window.abort

    try:
        result = auth.signInWithCode(auth.DeviceLogin(client), client.device.name, window.setCode, wait)
    finally:
        window.doClose()

    if result is None or result.status == 'approved':
        return result
    util.DEBUG_LOG('Silo sign-in ended: {}', result.status)
    msgId, msg = FAILURES.get(result.status, (35246, "Couldn't sign in. Please try again."))
    util.messageDialog(T(32427, 'Failed'), T(msgId, msg))
    return None
