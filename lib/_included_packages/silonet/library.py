"""
A library's screens from Silo's catalog (GET /api/v2/catalog?source=query&library_id=...): the grid's count and its
chunks (plexlibrary.LibrarySection.all()) and its sort menu (/library/sections/<id>/sorts), as the Plex elements
plexnet reads.

A chunk is Silo's explicit window jump (seek=<start>&limit=<size>): the grid asks for chunks out of order, which a
cursor chain can't serve, and on the user's server seek windows and the next_cursor chain gave the same items in the
same order (Review Focus #5). One past CATALOG_PAGE_MAX is asked in pieces.
"""

from xml.etree import ElementTree

from .items import container, itemElements

# the most items /api/v2/catalog answers a request
CATALOG_PAGE_MAX = 200

# The sorts Uno's sort menu knows (library_grid.SORT_KEYS) that Silo's catalog sorts by: (Plex key, Silo field, Plex
# default direction, title). Checked on the user's server: Silo refuses rating, random, last_watched, play_count,
# duration and user_rating, so Date Viewed, My Rating, Plays, Resolution and Randomly aren't offered.
SORTS = (
    ('titleSort', 'title', 'asc', 'Title'),
    ('addedAt', 'added_at', 'desc', 'Date Added'),
    ('originallyAvailableAt', 'release_date', 'desc', 'Release Date'),
    ('year', 'year', 'desc', 'Year'),
    ('rating', 'rating_rt_critic', 'desc', 'Critic Rating'),
    ('audienceRating', 'rating_rt_audience', 'desc', 'Audience Rating'),
    ('contentRating', 'content_rating', 'asc', 'Content Rating'),
    ('duration', 'runtime', 'desc', 'Duration'),
    ('viewOffset', 'progress', 'desc', 'Progress'),
)
SILO_FIELDS = {key: field for key, field, _, _ in SORTS}


def catalogSort(plexSort):
    """A grid's sort= ('key:dir', plexlibrary.sortArg()) as Silo's ('field' or '-field'); None for one Silo lacks."""
    if not plexSort:
        return None
    key, _, direction = plexSort.split(',')[0].partition(':')
    field = SILO_FIELDS.get(key)
    if field is None:
        return None
    return '-' + field if direction == 'desc' else field


def sortsContainer():
    """/library/sections/<id>/sorts: one <Directory> per sort Silo has, as Plex's /sorts answers."""
    return container(
        [
            ElementTree.Element('Directory', {'key': key, 'title': title, 'defaultDirection': direction})
            for key, _, direction, title in SORTS
        ]
    )


def libraryItems(client, libraryId, args, offset=None, limit=None):
    """
    A library's grid: its count (size 0: totalSize alone) or a chunk, sorted as asked when Silo sorts by it. No size:
    the whole library.
    """
    start = int(args.get('X-Plex-Container-Start', offset or 0) or 0)
    size = args.get('X-Plex-Container-Size', limit)
    size = None if size is None else int(size)
    query = {'source': 'query', 'library_id': libraryId}
    sort = catalogSort(args.get('sort'))
    if sort:
        query['sort'] = sort
    if size == 0:
        answer = client.request('GET', '/api/v2/catalog', params=dict(query, limit=1)) or {}
        return container(totalSize=answer.get('total') or 0)

    elements, total, position = [], 0, start
    while size is None or position < start + size:
        want = CATALOG_PAGE_MAX if size is None else min(start + size - position, CATALOG_PAGE_MAX)
        answer = client.request('GET', '/api/v2/catalog', params=dict(query, seek=position, limit=want)) or {}
        items = answer.get('items') or []
        total = answer.get('total') or 0
        elements += itemElements(items)
        position += len(items)
        if len(items) < want or position >= total:
            break
    for element in elements:
        element.set('librarySectionID', libraryId)
    return container(elements, totalSize=total, offset=start)
