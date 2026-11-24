"""
SiloServer: the server object Uno's plexnet object model and screens talk to. query() answers the Plex paths they
ask for from Silo's API, as Plex-shaped XML, so plexnet's classes keep working. A path not mapped yet answers an
empty container (logged once): each port phase maps the paths its screens need.
"""

import functools
import re
from urllib.parse import parse_qsl
from xml.etree import ElementTree

from plexnet.signalsmixin import SignalsMixin

from . import detail, home, library, people, playback, related, shows
from .client import log
from .errors import SiloError
from .items import container

# Silo library types to the Plex section types plexlibrary knows; mixed libraries wait for a later phase
SECTION_TYPES = {'movies': 'movie', 'series': 'show'}
# a library's grid (plexlibrary.LibrarySection.all()) and its sort menu: /library/sections/<library id>/all|sorts
LIBRARY_PATH = re.compile(r'^/library/sections/([^/]+)/(all|sorts|firstCharacter|filters|genre|contentRating)$')
# an item's detail (PlexObject.reload())
METADATA_PATH = re.compile(r'^/library/metadata/([^/]+)$')
# a show's seasons or a season's episodes (their key), and a show's every episode (Show.episodes())
CHILDREN_PATH = re.compile(r'^/library/metadata/([^/]+)/(children|allLeaves)$')
# a title's Related row (RelatedMixin.getRelated())
SIMILAR_PATH = re.compile(r'^/library/metadata/([^/]+)/similar$')
# a person, and their titles in the libraries (Role.getDetails(), lib/windows/person.py libraryFilmography())
PEOPLE_PATH = re.compile(r'^/library/people/([^/]+)(/media)?$')
# a collection's titles (plexlibrary.Collection.all(): its key)
COLLECTION_PATH = re.compile(r'^/library/collections/([^/]+)/children$')


class SiloConnection:
    """A Silo server's one connection, its base URL: what plexnet reads of PlexServer.activeConnection."""

    def __init__(self, address):
        self.address = address


class SiloServer(SignalsMixin):
    offline = False
    suspect = False
    gone = False
    owned = True
    platform = 'silo'
    pendingReachabilityRequests = 0  # Plex's connection tests; a Silo server has one address
    # What Plex Uno's media decision engine asks a server (plexnet mediadecisionengine.py). Silo decides each attempt
    # itself (silonet.playback), so these only let the engine pick a version and its tracks.
    supportsVideoTranscoding = True
    supportsVideoRemuxOnly = False
    supportsAudioTranscoding = True
    # the player's playback info panel (seekdialog.py) looks for a Plex transcode session, which Silo has none of
    anyLANConnection = True
    sessions = ()

    def __init__(self, stored, client):
        SignalsMixin.__init__(self)  # the seek dialog's timeline and stream-terminated callbacks
        self.stored = stored
        self.client = client
        self.uuid = stored.serverId
        self.name = stored.name or stored.baseUrl
        self.activeConnection = SiloConnection(client.baseUrl)
        self._unmapped = set()
        self._routes = {'/library/sections': self._sections}
        self._homeCapabilities = None
        self._libraryTypes = {}  # library id -> Plex section type, from the library list (a collection's subtype)
        self.playback = playback.Playback(client, getattr(client.device, 'clientVersion', ''))

    def __repr__(self):
        return f'<SiloServer {self.name}>'

    def query(self, path, method=None, raw=False, **kwargs):
        """The answer to a Plex path as XML; None when Silo couldn't answer (as PlexServer.query returns)."""
        route, _, queryString = path.partition('?')
        route = route.rstrip('/') or '/'
        handler = self._routes.get(route)
        if handler is None and route.startswith(home.ROW_PATH):
            handler = functools.partial(self._row, route, kwargs.get('offset'), kwargs.get('limit'))
        libraryPath = LIBRARY_PATH.match(route) if handler is None else None
        if libraryPath and libraryPath.group(2) == 'sorts':
            handler = library.sortsContainer
        elif libraryPath and libraryPath.group(2) == 'filters':
            handler = functools.partial(library.filtersContainer, libraryPath.group(1))
        elif libraryPath and libraryPath.group(2) in library.FILTER_PARAMS:
            handler = functools.partial(library.filterChoices, self.client, libraryPath.group(1), libraryPath.group(2))
        elif libraryPath and libraryPath.group(2) == 'firstCharacter':
            handler = functools.partial(
                library.jumpBar, self.client, libraryPath.group(1), dict(parse_qsl(queryString))
            )
        elif libraryPath:
            handler = functools.partial(
                library.libraryItems,
                self.client,
                libraryPath.group(1),
                dict(parse_qsl(queryString)),
                kwargs.get('offset'),
                kwargs.get('limit'),
                self._libraryTypes.get(libraryPath.group(1), ''),
            )
        metadataPath = METADATA_PATH.match(route) if handler is None else None
        if metadataPath:
            handler = functools.partial(detail.itemDetail, self.client, metadataPath.group(1), kwargs.get('params'))
        childrenPath = CHILDREN_PATH.match(route) if handler is None else None
        if childrenPath and childrenPath.group(2) == 'children':
            handler = functools.partial(shows.children, self.client, childrenPath.group(1))
        elif childrenPath:
            handler = functools.partial(
                shows.allLeaves, self.client, childrenPath.group(1), kwargs.get('offset'), kwargs.get('limit')
            )
        similarPath = SIMILAR_PATH.match(route) if handler is None else None
        if similarPath:
            count = (kwargs.get('params') or {}).get('count') or dict(parse_qsl(queryString)).get('count')
            handler = functools.partial(
                related.similar, self.client, similarPath.group(1), count, kwargs.get('offset'), kwargs.get('limit')
            )
        peoplePath = PEOPLE_PATH.match(route) if handler is None else None
        if peoplePath:
            handler = functools.partial(
                people.media if peoplePath.group(2) else people.person, self.client, peoplePath.group(1)
            )
        collectionPath = COLLECTION_PATH.match(route) if handler is None else None
        if collectionPath:
            handler = functools.partial(
                library.collectionItems,
                self.client,
                collectionPath.group(1),
                dict(parse_qsl(queryString)),
                kwargs.get('offset'),
                kwargs.get('limit'),
            )
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

    def _row(self, route, offset=None, limit=None):
        """A row's items for its See more grid, a Home row's or a library's (its key, silonet.home/library): totalSize
        is what Silo answers of the row, and a page (offset, limit) is cut from that; limit 0 asks for the count."""
        if route.startswith(library.LIBRARY_ROW_PATH):
            libraryId, _, sectionId = route[len(library.LIBRARY_ROW_PATH) :].partition('/')
            items = library.libraryRowItems(self.client, libraryId, sectionId)
        else:
            items = home.rowItems(self.client, route[len(home.ROW_PATH) :], self.homeCapabilities())
        start = offset or 0
        page = [] if limit == 0 else items[start : None if limit is None else start + limit]
        root = container(page)
        root.set('totalSize', str(len(items)))
        return root

    def _sections(self):
        data = self.client.request('GET', '/api/v2/user/libraries') or {}
        sections = []
        for entry in data.get('items') or []:
            kind = SECTION_TYPES.get(entry.get('type'))
            if kind is None:
                continue
            self._libraryTypes[entry['id']] = kind
            sections.append(
                ElementTree.Element(
                    'Directory',
                    {
                        'key': entry['id'],
                        'uuid': entry['id'],
                        'title': entry.get('name') or '',
                        'type': kind,
                        'thumb': entry.get('poster_url') or '',
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

    def isLocalConnection(self):
        return True  # Silo applies its own local and remote stream limits to each attempt

    def supportsFeature(self, feature):
        return False  # Plex server features (transcoder, BIF indexes); Silo's are asked of it directly

    def startPlayback(
        self, item, part, seconds=0.0, audioIndex=None, subtitleIndex=None, quality='auto', bandwidthCap=None, hdr=True
    ):
        """Starts a Silo attempt for the item's version (part: its Media's Part, whose id is Silo's file id) and
        returns it (silonet.playback.Attempt); PlaybackRefused when Silo decides it can't play."""
        return self.playback.start(
            str(item.ratingKey), part.id, seconds, audioIndex, subtitleIndex, quality, bandwidthCap, hdr
        )

    def findVideoSession(self, sessionId, ratingKey):
        from plexnet import exceptions

        raise exceptions.NotFound  # the panel says the info isn't available

    def reportTimeline(self, params):
        """A player timeline (plexnet nowplayingmanager): progress or stop for the item's attempt."""
        self.playback.timeline(str(params.get('ratingKey')), params.get('state'), params.get('time'))

    def updateReachability(self, force=True, allowFallback=False):
        pass  # no connection to test: a request that fails says so itself

    def close(self):
        """The add-on is ending (plexapp.App.preShutdown()): its connections to the server close."""
        self.client.session.close()

    def dropIdleConnections(self):
        pass  # requests' session opens new connections itself after a sleep

    def hubs(self, section=None, count=None, search_query=None, section_ids=None, continue_watching_count=None):
        """Home's rows from Silo's home layout (silonet.home), or a library's (section: its id) from Silo's rows for it
        (silonet.library), in Silo's order. Search isn't mapped yet: none. Silo's home rows aren't per library, so
        section_ids doesn't narrow them (D8)."""
        if search_query:
            return []
        from plexnet import plexlibrary, plexobjects, video  # noqa: F401 (video registers the item types)

        try:
            if section:
                rows = library.libraryRows(self.client, section, count)
            else:
                rows = home.homeRows(self.client, count, continue_watching_count, self.homeCapabilities())
        except SiloError as e:
            log(f'{"library" if section else "home"} rows failed: {e.status} {e.type}')
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
