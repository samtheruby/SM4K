"""
An item's detail, GET /api/v2/catalog/items/{id}, as the full Plex element plexnet's reload() reads
(/library/metadata/<ratingKey>): the tile's attributes (silonet.items) plus what the pre-play, show and episode screens
show - summary, tagline, content rating, studio, genres, countries, cast and crew, ratings (as <Rating> with the
image keys Uno has icons for), and each version as Media > Part > Stream. Stream ids and language codes for choosing
tracks are Phase 5's.
"""

from xml.etree import ElementTree

from .items import container, itemElement, ms

# Silo's resolution to Plex's videoResolution, what Uno's resolution badges read
RESOLUTIONS = {'2160p': '4k', '4k': '4k', '1440p': '1080', '1080p': '1080', '1080i': '1080', '720p': '720'}
# crew jobs Uno shows as writers and producers (it has no other crew rows)
WRITER_JOBS = frozenset(('Writer', 'Screenplay', 'Story', 'Teleplay', 'Novel', 'Characters', 'Author'))
PRODUCER_JOBS = frozenset(('Producer',))


def element(tag, attrs):
    """An element with the attributes that have a value, as strings."""
    return ElementTree.Element(tag, {k: str(v) for k, v in attrs.items() if v is not None and v != ''})


def flag(value):
    return '1' if value else '0'


def ratingElements(detail):
    """Silo's ratings as Plex <Rating>s (RatingsMixin.populateRatings()): IMDb, Rotten Tomatoes critic and audience
    (percentages as x/10, fresh from 60), TMDB."""
    ratings = []
    imdb, tmdb = detail.get('rating_imdb'), detail.get('rating_tmdb')
    critic, audience = detail.get('rating_rt_critic'), detail.get('rating_rt_audience')
    if imdb is not None:
        ratings.append(('imdb://image.rating', imdb, 'audience'))
    if critic is not None:
        ratings.append((f'rottentomatoes://image.rating.{"ripe" if critic >= 60 else "rotten"}', critic / 10, 'critic'))
    if audience is not None:
        image = f'rottentomatoes://image.rating.{"upright" if audience >= 60 else "spilled"}'
        ratings.append((image, audience / 10, 'audience'))
    if tmdb is not None:
        ratings.append(('themoviedb://image.rating', tmdb, 'audience'))
    return [
        element('Rating', {'image': image, 'value': f'{value:.1f}', 'type': kind}) for image, value, kind in ratings
    ]


def personElements(detail):
    """Cast as <Role>, crew as <Director>/<Writer>/<Producer>, each with its Silo person id and photo."""
    people = [
        element(
            'Role',
            {'tag': p.get('name'), 'role': p.get('character'), 'id': p.get('person_id'), 'thumb': p.get('photo_url')},
        )
        for p in detail.get('cast') or []
    ]
    for p in detail.get('crew') or []:
        job = p.get('job')
        tag = (
            'Director'
            if job == 'Director'
            else 'Writer'
            if job in WRITER_JOBS
            else ('Producer' if job in PRODUCER_JOBS else None)
        )
        if tag:
            people.append(element(tag, {'tag': p.get('name'), 'id': p.get('person_id'), 'thumb': p.get('photo_url')}))
    return people


def mediaElement(version):
    """One version (a file) as Plex's <Media><Part><Stream/></Part></Media>: what mediaChoice, the resolution badges
    and the audio/subtitle choices read."""
    fileId = version.get('file_id')
    videoTracks = version.get('video_tracks') or []
    audioTracks = version.get('audio_tracks') or []
    video = videoTracks[0] if videoTracks else {}
    mainAudio = next((a for a in audioTracks if a.get('default')), audioTracks[0] if audioTracks else {})
    width, height = video.get('width'), video.get('height')
    duration = ms(version['duration']) if version.get('duration') else None
    media = element(
        'Media',
        {
            'id': fileId,
            'duration': duration,
            'bitrate': version.get('bitrate'),
            'width': width,
            'height': height,
            'aspectRatio': f'{width / height:.2f}' if width and height else None,
            'audioChannels': mainAudio.get('channels'),
            'audioCodec': version.get('codec_audio') or mainAudio.get('codec'),
            'videoCodec': version.get('codec_video') or video.get('codec'),
            'videoResolution': RESOLUTIONS.get(str(version.get('resolution') or '').lower(), 'sd'),
            'container': version.get('container'),
        },
    )
    part = element(
        'Part',
        {
            'id': fileId,
            'key': f'/library/parts/{fileId}/file',
            'duration': duration,
            'size': version.get('file_size'),
            'container': version.get('container'),
        },
    )
    streams = [
        element(
            'Stream',
            {
                'streamType': 1,
                'id': f'{fileId}.v{n}',
                'index': n,
                'codec': v.get('codec'),
                'width': v.get('width'),
                'height': v.get('height'),
                'bitDepth': v.get('bit_depth'),
                'frameRate': v.get('frame_rate'),
                'DOVIPresent': flag(v.get('dolby_vision')),
            },
        )
        for n, v in enumerate(videoTracks)
    ]
    selected = audioTracks.index(mainAudio) if mainAudio in audioTracks else -1
    streams += [
        element(
            'Stream',
            {
                'streamType': 2,
                'id': f'{fileId}.a{n}',
                'index': n,
                'codec': a.get('codec'),
                'channels': a.get('channels'),
                'languageCode': a.get('language'),
                'title': a.get('title'),
                'displayTitle': a.get('title'),
                'default': flag(a.get('default')),
                'selected': flag(n == selected),
            },
        )
        for n, a in enumerate(audioTracks)
    ]
    streams += [
        element(
            'Stream',
            {
                'streamType': 3,
                'id': f'{fileId}.s{s.get("index")}',
                'index': s.get('index'),
                'codec': s.get('codec'),
                'languageCode': s.get('language'),
                'title': s.get('title'),
                'displayTitle': s.get('title'),
                'forced': flag(s.get('forced')),
                'hearingImpaired': flag(s.get('hearing_impaired')),
                'default': flag(s.get('default')),
            },
        )
        for s in version.get('subtitle_tracks') or []
    ]
    part.extend(streams)
    media.append(part)
    return media


def detailElement(detail):
    """The item's full element: its tile's attributes and everything above. None for media Uno has no screens for."""
    root = itemElement(detail)
    if root is None:
        return None
    studios = detail.get('studios') or []
    versions = detail.get('versions') or []
    for name, value in (
        ('summary', detail.get('overview')),
        ('tagline', detail.get('tagline')),
        ('contentRating', detail.get('content_rating')),
        ('studio', studios[0] if studios else None),
        ('duration', ms(versions[0]['duration']) if versions and versions[0].get('duration') else None),
    ):
        if value:
            root.set(name, str(value))
    root.extend(element('Genre', {'tag': genre}) for genre in detail.get('genres') or [])
    root.extend(element('Country', {'tag': country}) for country in detail.get('countries') or [])
    root.extend(element('Studio', {'tag': studio}) for studio in studios)
    root.extend(personElements(detail))
    root.extend(ratingElements(detail))
    root.extend(mediaElement(version) for version in versions)
    return root


def itemDetail(client, contentId):
    """/library/metadata/<id>: the item's detail in a container, as plexnet's reload() reads data[0]."""
    answer = client.request('GET', f'/api/v2/catalog/items/{contentId}') or {}
    root = detailElement(answer)
    return container([root] if root is not None else [])
