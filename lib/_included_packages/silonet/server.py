"""
SiloServer: the server object Uno's plexnet object model and screens talk to. query() answers the Plex paths they
ask for from Silo's API, as Plex-shaped XML, so plexnet's classes keep working. A path not mapped yet answers an
empty container (logged once): each port phase maps the paths its screens need.
"""

import functools
import re
from urllib.parse import parse_qsl
from xml.etree import ElementTree

from . import home
from .client import log
from .errors import SiloError
from .items import itemElements

# Silo library types to the Plex section types plexlibrary knows; mixed libraries wait for a later phase
SECTION_TYPES = {'movies': 'movie', 'series': 'show'}
# a library's grid (plexlibrary.LibrarySection.all()): /library/sections/<library id>/all
LIBRARY_ALL = re.compile(r'^/library/sections/([^/]+)/all$')
# the most items /api/v2/catalog answers a request
CATALOG_PAGE_MAX = 200


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
        route, _, queryString = path.partition('?')
        route = route.rstrip('/') or '/'
        handler = self._routes.get(route)
        if handler is None and route.startswith(home.ROW_PATH):
            handler = functools.partial(
                self._homeRow, route[len(home.ROW_PATH) :], kwargs.get('offset'), kwargs.get('limit')
            )
        libraryAll = LIBRARY_ALL.match(route) if handler is None else None
        if libraryAll:
            handler = functools.partial(
                self._libraryItems,
                libraryAll.group(1),
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

    def _homeRow(self, sectionId, offset=None, limit=None):
        """A Home row's items for its See more grid: totalSize is what Silo answers of the row, and a page (offset,
        limit) is cut from that; limit 0 asks for the count alone."""
        items = home.rowItems(self.client, sectionId, self.homeCapabilities())
        start = offset or 0
        page = [] if limit == 0 else items[start : None if limit is None else start + limit]
        root = container(page)
        root.set('totalSize', str(len(items)))
        return root

    def _libraryItems(self, libraryId, args, offset=None, limit=None):
        """
        A library's grid (plexlibrary.LibrarySection.all()) from Silo's catalog: its count (size 0: totalSize alone) or
        a chunk. A chunk is Silo's explicit window jump (seek=start, limit=size), as the grid asks for chunks out of
        order; one past CATALOG_PAGE_MAX is asked in pieces. No size: the whole library.
        """
        start = int(args.get('X-Plex-Container-Start', offset or 0) or 0)
        size = args.get('X-Plex-Container-Size', limit)
        size = None if size is None else int(size)
        query = {'source': 'query', 'library_id': libraryId}
        if size == 0:
            answer = self.client.request('GET', '/api/v2/catalog', params=dict(query, limit=1)) or {}
            root = container()
            root.set('totalSize', str(answer.get('total') or 0))
            return root

        elements, total, position = [], 0, start
        while size is None or position < start + size:
            want = CATALOG_PAGE_MAX if size is None else min(start + size - position, CATALOG_PAGE_MAX)
            answer = self.client.request('GET', '/api/v2/catalog', params=dict(query, seek=position, limit=want)) or {}
            items = answer.get('items') or []
            total = answer.get('total') or 0
            elements += itemElements(items)
            position += len(items)
            if len(items) < want or position >= total:
                break
        for element in elements:
            element.set('librarySectionID', libraryId)
        root = container(elements)
        root.set('totalSize', str(total))
        root.set('offset', str(start))
        return root

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

    def close(self):
        """The add-on is ending (plexapp.App.preShutdown()): its connections to the server close."""
        self.client.session.close()

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
