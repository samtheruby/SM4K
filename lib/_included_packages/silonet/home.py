"""
Silo's home rows as Uno's Home reads them: each section of GET /api/v2/home/layout becomes a Plex <Hub> element whose
children are the <Video>/<Directory> elements plexnet builds tiles from (plexlibrary.Hub). The first rows come with
the layout (include_items), the rest from /api/v2/home/sections/{id}/items. Images stay Silo's relative
/api/v2/artwork paths, which SiloServer.buildUrl() makes absolute for Kodi.
"""

from xml.etree import ElementTree

from .client import log
from .errors import SiloError

# section_ids.CONTINUE_WATCHING_ID: Home merges the row with this identifier across servers
CONTINUE_WATCHING = 'continueWatching'
CONTINUE_WATCHING_TYPE = 'continue_watching'
# a Home row's own path, its <Hub> key: SiloServer.query() answers it for the row's See more grid
ROW_PATH = '/hubs/silo/'


def ms(seconds):
    return str(round(seconds * 1000))


def setIf(attrs, key, value):
    if value is not None and value != '':
        attrs[key] = str(value)


def itemElement(item):
    """A Silo catalog item as the Plex element its tile is built from; None for media Uno has no screens for."""
    kind = item.get('type')
    contentId = item.get('content_id')
    if kind not in ('movie', 'episode', 'series', 'season') or not contentId:
        return None
    state = item.get('user_state') or {}
    attrs = {'ratingKey': contentId, 'key': '/library/metadata/' + contentId, 'title': item.get('title') or ''}
    setIf(attrs, 'year', item.get('year'))
    setIf(attrs, 'thumb', item.get('poster_url'))
    setIf(attrs, 'art', item.get('backdrop_url'))
    setIf(attrs, 'originallyAvailableAt', item.get('release_date'))

    if kind in ('movie', 'episode'):
        attrs['type'] = kind
        duration = item.get('duration_seconds') or (item.get('runtime') or 0) * 60
        if duration:
            attrs['duration'] = ms(duration)
        if item.get('position_seconds'):
            attrs['viewOffset'] = ms(item['position_seconds'])
        if state.get('played'):
            attrs['viewCount'] = '1'
        if kind == 'episode':
            setIf(attrs, 'grandparentTitle', item.get('series_title'))
            setIf(attrs, 'grandparentThumb', item.get('series_poster_url'))
            setIf(attrs, 'grandparentRatingKey', item.get('series_id'))
            setIf(attrs, 'parentIndex', item.get('season_number'))
            setIf(attrs, 'index', item.get('episode_number'))
        return ElementTree.Element('Video', attrs)

    watched = state.get('watched_count') or 0
    attrs['leafCount'] = str(watched + (state.get('unplayed_count') or 0))
    attrs['viewedLeafCount'] = str(watched)
    if kind == 'series':
        attrs['type'] = 'show'
    else:
        attrs['type'] = 'season'
        setIf(attrs, 'thumb', item.get('season_poster_url'))
        setIf(attrs, 'parentTitle', item.get('series_title'))
        setIf(attrs, 'parentThumb', item.get('series_poster_url'))
        setIf(attrs, 'parentRatingKey', item.get('series_id'))
        setIf(attrs, 'index', item.get('season_number'))
    return ElementTree.Element('Directory', attrs)


def itemElements(items):
    return [e for e in (itemElement(i) for i in items or []) if e is not None]


def hubElement(section):
    """One home section (with its items) as a Plex <Hub>; its key is the row's own path (SiloServer's route)."""
    items = itemElements(section.get('items'))
    kinds = {e.get('type') for e in items}
    continueWatching = section.get('section_type') == CONTINUE_WATCHING_TYPE
    hub = ElementTree.Element(
        'Hub',
        {
            'hubIdentifier': CONTINUE_WATCHING
            if continueWatching
            else f'silo.{section["section_type"]}.{section["id"]}',
            'title': section.get('title') or '',
            'type': kinds.pop() if len(kinds) == 1 else 'mixed',
            'size': str(len(items)),
            'totalSize': str(section.get('total_count') or len(items)),
            'more': '1' if section.get('has_more') else '0',
            'key': ROW_PATH + section['id'],
        },
    )
    hub.extend(items)
    return hub


def rowLimit(limit, capabilities, name):
    maximum = capabilities.get(name)
    return {'item_limit': min(limit, maximum)} if limit and maximum else None


def homeRows(client, count, continueWatchingCount, capabilities):
    """
    Home's rows in Silo's order, as <Hub> elements: count items each, continueWatchingCount for Continue Watching.
    include_items and item_limit are only sent when /api/v2/home/capabilities reports them. A row that fails is left
    out; a layout that fails raises its SiloError.
    """
    params = {}
    if capabilities.get('include_items_max'):
        params['include_items'] = capabilities['include_items_max']
    params.update(rowLimit(count, capabilities, 'row_item_limit_max') or {})
    layout = client.request('GET', '/api/v2/home/layout', params=params or None) or {}
    included = {s.get('id'): s for s in layout.get('included_sections') or []}

    rows = []
    for section in layout.get('sections') or []:
        continueWatching = section.get('section_type') == CONTINUE_WATCHING_TYPE
        limit = continueWatchingCount if continueWatching and continueWatchingCount else count
        answer = included.get(section['id'])
        if answer is None or (answer.get('has_more') and limit and len(answer.get('items') or []) < limit):
            try:
                answer = client.request(
                    'GET',
                    f'/api/v2/home/sections/{section["id"]}/items',
                    params=rowLimit(limit, capabilities, 'section_item_limit_max'),
                )
            except SiloError as e:
                log(f'home row {section.get("section_type")} failed: {e.status} {e.type}')
                continue
        rows.append(hubElement(dict(section, **(answer or {}))))
    return rows


def rowItems(client, sectionId, capabilities):
    """Every item element of one Home row that Silo answers: from the start, at most section_item_limit_max."""
    limit = capabilities.get('section_item_limit_max')
    answer = client.request(
        'GET',
        f'/api/v2/home/sections/{sectionId}/items',
        params=rowLimit(limit, capabilities, 'section_item_limit_max'),
    )
    return itemElements((answer or {}).get('items'))
