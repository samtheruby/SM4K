from __future__ import absolute_import

import hashlib
import os

from kodi_six import xbmcgui, xbmcvfs

from lib import util
from . import kodigui


QR_PREFIX = 'silomod_qr_'


def qrImage(text):
    """A PNG of text's QR code in Kodi's temp folder, for the card's image; the one before it is deleted. Each text
    gets its own name, as Kodi caches an image by its path."""
    import segno

    folder = xbmcvfs.translatePath('special://temp')
    name = QR_PREFIX + hashlib.sha1(text.encode('utf-8')).hexdigest()[:12] + '.png'
    for old in os.listdir(folder):
        if old.startswith(QR_PREFIX) and old != name:
            os.remove(os.path.join(folder, old))
    path = os.path.join(folder, name)
    segno.make_qr(text).save(path, scale=10, border=2)
    return path


class PinLoginWindow(kodigui.BaseWindow):
    xmlFile = 'script-plex-pin_login.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'
    res = '1080i'
    width = 1920
    height = 1080

    USERNAME_ID = 201
    PASSWORD_ID = 202
    SIGN_IN_ID = 203

    # what the user did on the card, read by lib/silo.py's signIn() while it waits
    abort = submitted = False
    username = password = ''

    def setOptions(self, options, address, username):
        """The server's name and subtitle (silonet.server_info.LoginOptions), its address and the last username."""
        self.username = username
        self.setProperty('server.name', options.name or util.T(32460, 'Sign In'))
        self.setProperty('subtitle', options.subtitle)
        self.setProperty('address', address)
        self.setProperty('username', username)
        self.setProperty('password.enabled', '1' if options.password else '')

    def showError(self, message):
        """A failed password sign-in: the message, and the password to type again."""
        self.password = ''
        self.setProperty('password', '')
        self.setProperty('error', message)

    def setCode(self, code):
        """Silo's sign-in code (silonet.auth.DeviceCode): eight digits and the page to enter them on."""
        from silonet.auth import formatUserCode
        self.setProperty('heading', util.T(32460, 'Sign In'))
        self.setProperty('instructions', util.T(35243, 'On a phone or computer, open {link} and enter this code:').format(
            link=code.verificationUri))
        self.setProperty('pin', formatUserCode(code.userCode))
        self.setProperty('qr', qrImage(code.verificationUriComplete))

    def onClick(self, controlID):
        if controlID == self.USERNAME_ID:
            self.username = xbmcgui.Dialog().input(util.T(35301, 'Username'), self.username) or self.username
            self.setProperty('username', self.username)
        elif controlID == self.PASSWORD_ID:
            self.password = xbmcgui.Dialog().input(util.T(35302, 'Password'), option=xbmcgui.ALPHANUM_HIDE_INPUT)
            self.setProperty('password', '\N{BULLET}' * len(self.password))
        elif controlID == self.SIGN_IN_ID:
            self.submitted = True

    def onAction(self, action):
        try:
            if action == xbmcgui.ACTION_NAV_BACK or action == xbmcgui.ACTION_PREVIOUS_MENU:
                self.abort = True
        except:
            util.ERROR()

        kodigui.BaseWindow.onAction(self, action)
