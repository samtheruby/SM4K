"""
SM4K's Silo session: signing in with a code shown on the TV (silonet.auth) through Uno's PIN window.
"""

import json

from kodi_six import xbmcgui
from silonet import auth
from silonet.errors import SiloIncompatible, SiloUnavailable
from silonet.server_info import probe

from . import util
from .util import T
from .windows import signin

SERVERS_SETTING = 'silo_servers_json'

# how often a wait checks for Back while it sleeps
WAIT_STEP = 0.1

FAILURES = {
    'denied': (35244, 'Sign-in was refused.'),
    'expired': (35245, 'The code expired before it was approved. Please try again.'),
}


class StoredServer:
    def __init__(self, baseUrl, serverId, name=None):
        self.baseUrl = baseUrl
        self.serverId = serverId
        self.name = name

    def toJson(self):
        return {'base_url': self.baseUrl, 'server_id': self.serverId, 'name': self.name}


def normalizeUrl(address):
    """What people type, as a base URL: http:// unless they said otherwise, no trailing slash."""
    address = address.strip().rstrip('/')
    return address if '://' in address else 'http://' + address


def storedServers():
    try:
        data = json.loads(util.getSetting(SERVERS_SETTING, '') or '[]')
    except ValueError:
        data = []
    return [
        StoredServer(d['base_url'], d['server_id'], d.get('name'))
        for d in data
        if isinstance(d, dict) and d.get('base_url') and d.get('server_id')
    ]


def saveServers(servers):
    util.setSetting(SERVERS_SETTING, json.dumps([s.toJson() for s in servers]))


def addServer(address, device, session=None):
    """Probe the address and store the server; the same server at a new address replaces its old one."""
    baseUrl = normalizeUrl(address)
    info = probe(baseUrl, device, session=session)
    stored = StoredServer(baseUrl, info.serverId, info.name)
    saveServers([s for s in storedServers() if s.serverId != info.serverId] + [stored])
    util.DEBUG_LOG('Silo: stored server {} ({})', stored.name or 'unnamed', info.serverVersion)
    return stored


def removeServer(serverId):
    saveServers([s for s in storedServers() if s.serverId != serverId])


def addServerDialog(device, session=None):
    """Ask for a Silo server's address until one answers or the user gives up: its StoredServer, or None."""
    address = ''
    while True:
        address = xbmcgui.Dialog().input(T(35247, 'Silo server address, for example http://192.168.1.10:8090'), address)
        if not address:
            return None
        try:
            return addServer(address, device, session=session)
        except SiloUnavailable:
            message = T(35248, 'Could not reach a Silo server at {address}.')
        except SiloIncompatible:
            message = T(35249, '{address} is not a Silo server SiloMod can use.')
        if not xbmcgui.Dialog().yesno(
            T(32427, 'Failed'),
            message.format(address=address),
            nolabel=T(32337, 'Cancel'),
            yeslabel=T(35032, 'Try again'),
        ):
            return None


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
