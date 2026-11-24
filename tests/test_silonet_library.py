"""
A library's grid from Silo's catalog: SiloServer.query() answers Uno's /library/sections/{key}/all (LibrarySection.all(),
the grid's count and its chunks) from GET /api/v2/catalog?source=query&library_id=... A chunk is Silo's explicit window
jump (seek, limit): the grid asks for chunks out of order, and a chunk past Silo's 200-item page is asked in two.
Responses are written inline in the shape of /api/v2/openapi.json (Silo build-2987).
"""

from plexnet import plexlibrary, video  # noqa: F401 (video registers the item types, as the add-on's imports do)
from silonet.client import Credentials, DeviceIdentity, SiloClient
from silonet.server import SiloServer

from lib.silo import StoredServer

from .base import KodiTestCase, ensure_plex_interface
from .silonet_fakes import FakeResponse, FakeSession, problem

DEVICE = DeviceIdentity('dev1', 'Living room', 'kodi', '0.4.4')
LIBRARIES = FakeResponse(
    200,
    {
        'items': [
            {'id': '2', 'name': '2160p Movies', 'type': 'movies'},
            {'id': '5', 'name': '2160p Shows', 'type': 'series'},
        ]
    },
)


def movie(n):
    return {
        'content_id': f'm{n}',
        'type': 'movie',
        'title': f'Film {n}',
        'year': 2000 + n % 20,
        'poster_url': f'/api/v2/artwork/tmdb/movies/{n}/poster/w500.x',
        'user_state': {'played': False},
    }


def series(n):
    return {
        'content_id': f's{n}',
        'type': 'series',
        'title': f'Show {n}',
        'user_state': {'watched_count': 1, 'unplayed_count': 9},
    }


def page(items, total, start=0):
    return FakeResponse(
        200,
        {
            'items': items,
            'total': total,
            'total_exact': True,
            'page': {'has_more': start + len(items) < total, 'next_cursor': 'opaque'},
        },
    )


def server(session):
    client = SiloClient('http://silo.lan:8090', DEVICE, Credentials(accessToken='A1', profileId='p1'), session=session)
    return SiloServer(StoredServer('http://silo.lan:8090', 'srv-1', 'Silo'), client)


def section(session, index=0):
    return plexlibrary.Library(None, server=server(session)).sections()[index]


class SiloLibraryGridTest(KodiTestCase):
    def setUp(self):
        super().setUp()
        ensure_plex_interface()  # LibrarySection reads the add-on's preferences through plexnet's interface

    def test_the_grids_count_is_silos_total(self):
        session = FakeSession(LIBRARIES, page([movie(0)], 216))

        listing = section(session).all(0, 0)

        self.assertEqual(listing.totalSize.asInt(), 216)
        self.assertEqual(len(listing), 0)
        call = session.calls[1]
        self.assertEqual(call['url'], 'http://silo.lan:8090/api/v2/catalog')
        self.assertEqual((call['params']['source'], call['params']['library_id']), ('query', '2'))

    def test_a_chunk_is_exactly_those_positions(self):
        session = FakeSession(LIBRARIES, page([movie(n) for n in range(100, 150)], 216, 100))

        items = section(session).all(100, 50)

        self.assertEqual([i.title for i in items], [f'Film {n}' for n in range(100, 150)])
        self.assertEqual((session.calls[1]['params']['seek'], session.calls[1]['params']['limit']), (100, 50))
        self.assertEqual(items[0].type, 'movie')
        self.assertEqual(
            items[0].defaultThumb.asTranscodedImageURL(300, 450),
            'http://silo.lan:8090/api/v2/artwork/tmdb/movies/100/poster/w500.x',
        )

    def test_a_chunk_past_silos_page_size_is_asked_in_two(self):
        session = FakeSession(
            LIBRARIES,
            page([movie(n) for n in range(200)], 216),
            page([movie(n) for n in range(200, 216)], 216, 200),
        )

        items = section(session).all(0, 240)

        self.assertEqual([i.title for i in items], [f'Film {n}' for n in range(216)])
        self.assertEqual(
            [(c['params']['seek'], c['params']['limit']) for c in session.calls[1:]], [(0, 200), (200, 40)]
        )

    def test_a_jump_far_down_asks_for_that_window_only(self):
        session = FakeSession(LIBRARIES, page([movie(n) for n in range(4800, 4840)], 4840, 4800))

        items = section(session).all(4800, 240)

        self.assertEqual(len(session.calls), 2)
        self.assertEqual(session.calls[1]['params']['seek'], 4800)
        self.assertEqual(len(items), 40)

    def test_a_series_librarys_items_are_shows(self):
        session = FakeSession(LIBRARIES, page([series(1), series(2)], 2))

        items = section(session, index=1).all(0, 50)

        self.assertEqual([(i.type, i.title) for i in items], [('show', 'Show 1'), ('show', 'Show 2')])
        self.assertEqual(session.calls[1]['params']['library_id'], '5')

    def test_a_listing_silo_cant_answer_is_none(self):
        srv = server(FakeSession(problem(503, 'dependency_unavailable')))

        self.assertIsNone(srv.query('/library/sections/2/all?X-Plex-Container-Start=0&X-Plex-Container-Size=0'))


class SiloLibrarySortTest(KodiTestCase):
    """The grid's sort menu (LibraryWindow.serverSortOptions(): /library/sections/<id>/sorts) offers what Silo's
    catalog sorts by, and a sorted chunk asks Silo for that sort ('field' or '-field')."""

    def setUp(self):
        super().setUp()
        ensure_plex_interface()

    def test_the_menu_offers_what_silo_sorts_by(self):
        sorts = section(FakeSession(LIBRARIES)).listSorts(libtype='movie')

        self.assertEqual(
            [(s.key, s.defaultDirection) for s in sorts],
            [
                ('titleSort', 'asc'),
                ('addedAt', 'desc'),
                ('originallyAvailableAt', 'desc'),
                ('year', 'desc'),
                ('rating', 'desc'),
                ('audienceRating', 'desc'),
                ('contentRating', 'asc'),
                ('duration', 'desc'),
                ('viewOffset', 'desc'),
            ],
        )

    def test_a_sorted_chunk_asks_silo_for_that_sort(self):
        session = FakeSession(LIBRARIES, page([movie(1)], 1))

        section(session).all(0, 50, sort=('addedAt', 'desc'))

        self.assertEqual(session.calls[1]['params']['sort'], '-added_at')

    def test_ascending_is_the_bare_field(self):
        session = FakeSession(LIBRARIES, page([movie(1)], 1))

        section(session).all(0, 50, sort=('titleSort', 'asc'))

        self.assertEqual(session.calls[1]['params']['sort'], 'title')

    def test_a_sort_silo_lacks_leaves_silos_own_order(self):
        session = FakeSession(LIBRARIES, page([movie(1)], 1))

        section(session).all(0, 50, sort=('lastViewedAt', 'desc'))

        self.assertNotIn('sort', session.calls[1]['params'])


def letters(runs, total):
    """POST /api/v2/catalog/letters: runs as (letter, position)."""
    return FakeResponse(200, {'total': total, 'letters': [], 'runs': [{'letter': l, 'position': p} for l, p in runs]})


class SiloLibraryJumpBarTest(KodiTestCase):
    """The grid's A-Z bar (LibrarySection.jumpList(): /library/sections/<id>/firstCharacter) from Silo's letters: one
    entry per block of titles under a letter, in list order, sized so each starts where Silo says it does."""

    def setUp(self):
        super().setUp()
        ensure_plex_interface()

    def test_letters_in_list_order_sized_to_their_positions(self):
        session = FakeSession(LIBRARIES, letters([('#', 0), ('A', 4), ('B', 16), ('C', 19)], 33))

        bar = section(session).jumpList(sort=('titleSort', 'asc'))

        self.assertEqual([(str(j.title), j.size.asInt()) for j in bar], [('#', 4), ('A', 12), ('B', 3), ('C', 14)])
        call = session.calls[1]
        self.assertEqual((call['method'], call['url']), ('POST', 'http://silo.lan:8090/api/v2/catalog/letters'))
        self.assertEqual(call['json'], {'library_id': '2', 'order': 'asc'})

    def test_descending_titles_ask_for_descending_letters(self):
        session = FakeSession(LIBRARIES, letters([('Z', 0), ('A', 5)], 9))

        section(session).jumpList(sort=('titleSort', 'desc'))

        self.assertEqual(session.calls[1]['json']['order'], 'desc')

    def test_a_letter_in_two_blocks_keeps_each_blocks_place(self):
        session = FakeSession(LIBRARIES, letters([('A', 0), ('B', 3), ('A', 5)], 8))

        bar = section(session).jumpList(sort=('titleSort', 'asc'))

        self.assertEqual([(str(j.title), j.size.asInt()) for j in bar], [('A', 3), ('B', 2), ('A', 3)])
        self.assertEqual(len({str(j.key) for j in bar}), 3)

    def test_no_letters_means_no_bar(self):
        bar = section(FakeSession(LIBRARIES, problem(503, 'dependency_unavailable'))).jumpList(
            sort=('titleSort', 'asc')
        )

        self.assertFalse(bar)
