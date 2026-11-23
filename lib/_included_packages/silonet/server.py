"""
SiloServer: the server object Uno's plexnet object model and screens talk to. query() answers the Plex paths they
ask for from Silo's API, as Plex-shaped XML, so plexnet's classes keep working. A path not mapped yet answers an
empty container (logged once): each port phase maps the paths its screens need.
"""

from xml.etree import ElementTree

from .client import log
from .errors import SiloError

# Silo library types to the Plex section types plexlibrary knows; mixed libraries wait for a later phase
SECTION_TYPES = {'movies': 'movie', 'series': 'show'}


def container(children=()):
    root = ElementTree.Element('MediaContainer', {'size': str(len(children))})
    root.extend(children)
    return root


class SiloServer:
    offline = False
    suspect = False
    owned = True
    platform = 'silo'

    def __init__(self, stored, client):
        self.stored = stored
        self.client = client
        self.uuid = stored.serverId
        self.name = stored.name or stored.baseUrl
        self._unmapped = set()
        self._routes = {'/library/sections': self._sections}

    def __repr__(self):
        return f'<SiloServer {self.name}>'

    def query(self, path, method=None, raw=False, **kwargs):
        """The answer to a Plex path as XML; None when Silo couldn't answer (as PlexServer.query returns)."""
        route = path.split('?', 1)[0].rstrip('/') or '/'
        handler = self._routes.get(route)
        if handler is None:
            if route not in self._unmapped:
                self._unmapped.add(route)
                log(f'not mapped yet: {route}')
            return container()
        try:
            return handler()
        except SiloError as e:
            log(f'{route} failed: {e.status} {e.type}')
            return None

    def _sections(self):
        data = self.client.request('GET', '/api/v2/user/libraries') or {}
        sections = []
        for library in data.get('items') or []:
            kind = SECTION_TYPES.get(library.get('type'))
            if kind is None:
                continue
            sections.append(
                ElementTree.Element(
                    'Directory',
                    {
                        'key': library['id'],
                        'uuid': library['id'],
                        'title': library.get('name') or '',
                        'type': kind,
                        'thumb': library.get('poster_url') or '',
                    },
                )
            )
        return container(sections)

    def buildUrl(self, path, includeToken=False):
        return path if '://' in path else self.client.baseUrl + path

    def getImageTranscodeURL(self, path, width, height, **extraOpts):
        return self.buildUrl(path)

    def isReachable(self, onlySupported=True):
        return True

    def library(self):
        from plexnet import plexlibrary

        return plexlibrary.Library(self.query('/library/'), server=self)
