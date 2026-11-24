from __future__ import absolute_import

from kodi_six import xbmcgui

from lib import util
from . import kodigui


class PinLoginWindow(kodigui.BaseWindow):
    xmlFile = 'script-plex-pin_login.xml'
    path = util.ADDON.getAddonInfo('path')
    theme = 'Main'
    res = '1080i'
    width = 1920
    height = 1080

    def __init__(self, *args, **kwargs):
        self.abort = False
        kodigui.BaseWindow.__init__(self, *args, **kwargs)

    def setCode(self, code):
        """Silo's sign-in code (silonet.auth.DeviceCode): eight digits and the page to enter them on."""
        from silonet.auth import formatUserCode
        self.setProperty('heading', util.T(32460, 'Sign In'))
        self.setProperty('instructions', util.T(35243, 'On a phone or computer, open {link} and enter this code:').format(
            link=code.verificationUri))
        self.setProperty('pin', formatUserCode(code.userCode))

    def onAction(self, action):
        try:
            if action == xbmcgui.ACTION_NAV_BACK or action == xbmcgui.ACTION_PREVIOUS_MENU:
                self.abort = True
        except:
            util.ERROR()

        kodigui.BaseWindow.onAction(self, action)
