"""
SiloServer: the server object Uno's plexnet object model and screens talk to. query() answers the Plex paths they
ask for from Silo's API, as Plex-shaped XML, so plexnet's classes keep working. A path not mapped yet answers an
empty container (logged once): each port phase maps the paths its screens need.
"""

from xml.etree import ElementTree

from . import home
from .client import log
from .errors import SiloError

# Silo library types to the Plex section types plexlibrary knows; mixed libraries wait for a later phase
SECTION_TYPES = {'movies': 'movie', 'series': 'show'}


class SiloConnection:
    """A Silo server's one connection, its base URL: what plexnet reads of PlexServer.activeConnection."""

    def __init__(self, address):
        self.address = address


def container(children=()):
    root = ElementTree.Element('MediaContainer', {'size': str(len(children))})
    root.extend(children)
    return root


class SiloServer:
    offline = False
    suspect = False
    gone = False
    owned = True
    platform = 'silo'
    pendingReachabilityRequests = 0  # Plex's connection tests; a Silo server has one address

    def __init__(self, stored, client):
        self.stored = stored
        self.client = client
        self.uuid = stored.serverId
        self.name = stored.name or stored.baseUrl
        self.activeConnection = SiloConnection(client.baseUrl)
        self._unmapped = set()
        self._routes = {'/library/sections': self._sections}
        self._homeCapabilities = None

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

    def updateReachability(self, force=True, allowFallback=False):
        pass  # no connection to test: a request that fails says so itself

    def dropIdleConnections(self):
        pass  # requests' session opens new connections itself after a sleep

    def hubs(self, section=None, count=None, search_query=None, section_ids=None, continue_watching_count=None):
        """Home's rows from Silo's home layout (silonet.home), in Silo's order. A library's rows and search aren't
        mapped yet: none. Silo's home rows aren't per library, so section_ids doesn't narrow them."""
        if section or search_query:
            return []
        from plexnet import plexlibrary, plexobjects, video  # noqa: F401 (video registers the item types)

        try:
            rows = home.homeRows(self.client, count, continue_watching_count, self.homeCapabilities())
        except SiloError as e:
            log(f'home layout failed: {e.status} {e.type}')
            return []
        root = container(rows)
        hubsContainer = plexobjects.PlexContainer(root, initpath='/hubs', server=self, address='/hubs')
        return [plexlibrary.Hub(elem, server=self, container=hubsContainer) for elem in root]

    def homeCapabilities(self):
        """What this Silo's home layout accepts (/api/v2/home/capabilities), asked once; {} while it can't answer."""
        if self._homeCapabilities is None:
            try:
                self._homeCapabilities = self.client.request('GET', '/api/v2/home/capabilities') or {}
            except SiloError as e:
                log(f'home capabilities failed: {e.status} {e.type}')
                return {}
        return self._homeCapabilities

    def playlists(self):
        return []  # Silo has no playlists

    def library(self):
        from plexnet import plexlibrary

        return plexlibrary.Library(self.query('/library/'), server=self)
