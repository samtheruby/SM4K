"""
lib/watch_together: a watch party (decision D26) keeps Kodi's player with its room. The room's transport commands
run at their execute_at on the server's clock (a late one projected forward, an in-step player left alone); reports
go out while the room's item plays (attach first, then state reports, marked ready while the room waits); a pause or
seek here becomes the room's request, or is undone for a guest the host hasn't given control; the end of the room
stops its item. The player and the room socket are stand-ins.
"""

from kodienv import ENV

ENV.abort_requested = True
from lib import watch_together

from .base import KodiTestCase

PLAYING = {
    'room_id': 'r1',
    'phase': 'playing',
    'playback_state': 'playing',
    'selection_revision': 2,
    'selected_content_id': 'movie-tmdb-238',
    'selected_file_id': 4711,
    'anchor_position_seconds': 0,
    'generation': 5,
    'self_role': 'guest',
    'self_can_control_transport': False,
    'members': [{'profile_id': 'p1', 'is_self': True, 'is_ready': False}],
}


class FakePlayer:
    def __init__(self, key=None, position=0.0, paused=False):
        self.key, self.at, self.paused = key, position, paused
        self.calls, self.notes = [], []

    def playingKey(self):
        return self.key

    def position(self):
        return self.at

    def isPaused(self):
        return self.paused

    def seek(self, seconds):
        self.calls.append(('seek', round(seconds, 2)))
        self.at = seconds

    def setPaused(self, paused):
        self.calls.append(('paused', paused))
        self.paused = paused

    def stop(self):
        self.calls.append(('stop',))
        self.key = None

    def sessionId(self, key):
        return 'sess-1' if key == 'movie-tmdb-238' else None

    def notify(self, text):
        self.notes.append(text)


class FakeLink:
    def __init__(self, now=1000.0):
        self.sent, self.now = [], now

    def send(self, message):
        self.sent.append(message)
        return True

    def serverTime(self, now=None):
        return self.now


def party(snapshot=PLAYING, player=None, now=1000.0, **changes):
    p = watch_together.Party(
        dict(snapshot, **changes), player or FakePlayer(), FakeLink(now), later=lambda delay, fn: fn()
    )
    p.clock = lambda: now
    return p


def command(action, position, state='playing', at='1970-01-01T00:16:38Z', cid='c1'):
    # 00:16:38 is 998 s after the epoch: two seconds before the room's clock in these tests (1000)
    return {
        'type': 'transport_command',
        'command': {
            'command_id': cid,
            'selection_revision': 2,
            'action': action,
            'position_seconds': position,
            'execute_at': at,
            'playback_state': state,
        },
    }


class PartyCommandsTest(KodiTestCase):
    def test_a_late_play_runs_projected_forward(self):
        p = party(player=FakePlayer('movie-tmdb-238', position=50.0, paused=True))

        p.onMessage(command('play', 100.0))

        self.assertEqual(p.player.calls, [('seek', 102.0), ('paused', False)])

    def test_a_pause_lands_where_the_room_is(self):
        p = party(player=FakePlayer('movie-tmdb-238', position=100.4))

        p.onMessage(command('pause', 100.0, state='paused'))

        self.assertEqual(p.player.calls, [('paused', True)])  # within a second: no seek

    def test_a_seek_always_moves(self):
        p = party(player=FakePlayer('movie-tmdb-238', position=99.8, paused=True))

        p.onMessage(command('seek', 100.0, state='waiting'))

        self.assertEqual(p.player.calls, [('seek', 100.0)])

    def test_nothing_runs_while_another_item_plays(self):
        p = party(player=FakePlayer('movie-other', position=5.0))

        p.onMessage(command('play', 100.0))

        self.assertEqual(p.player.calls, [])


class PartyReportsTest(KodiTestCase):
    def test_its_session_is_attached_first(self):
        p = party(player=FakePlayer('movie-tmdb-238', position=3.0))

        p.tick()

        self.assertEqual(p.link.sent, [{'type': 'attach_session', 'session_id': 'sess-1'}])

    def test_then_it_reports_where_it_is(self):
        p = party(player=FakePlayer('movie-tmdb-238', position=3.0), attached_session_id='sess-1')
        p.onMessage(command('play', 1.0, cid='c7'))
        p.link.sent.clear()

        p.tick()

        self.assertEqual(
            p.link.sent,
            [
                {
                    'type': 'state_report',
                    'session_id': 'sess-1',
                    'position_seconds': 3.0,
                    'is_paused': False,
                    'command_id': 'c7',
                }
            ],
        )

    def test_while_the_room_waits_it_says_it_is_ready(self):
        p = party(
            player=FakePlayer('movie-tmdb-238', position=0.0, paused=True),
            attached_session_id='sess-1',
            playback_state='waiting',
        )
        p.onMessage(command('seek', 0.0, state='waiting', cid='c8'))
        p.link.sent.clear()

        p.tick()

        self.assertTrue(p.link.sent[0]['is_ready'])
        self.assertEqual(p.link.sent[0]['command_id'], 'c8')

    def test_no_reports_without_the_rooms_item(self):
        p = party(player=FakePlayer(None))

        p.tick()

        self.assertEqual(p.link.sent, [])


class PartyLocalActionsTest(KodiTestCase):
    def test_the_host_pausing_pauses_the_room(self):
        p = party(
            player=FakePlayer('movie-tmdb-238', position=42.0, paused=True),
            self_role='host',
            self_can_control_transport=True,
        )

        p.onLocalPause(True)

        self.assertEqual(
            p.link.sent, [{'type': 'transport_request', 'action': 'pause', 'position_seconds': 42.0, 'is_paused': True}]
        )

    def test_a_seek_here_asks_the_room(self):
        p = party(player=FakePlayer('movie-tmdb-238', position=600.0), self_can_control_transport=True)

        p.onLocalSeek(600.0)

        self.assertEqual(p.link.sent[0]['action'], 'seek')
        self.assertEqual(p.link.sent[0]['position_seconds'], 600.0)

    def test_what_a_command_did_is_not_sent_back(self):
        p = party(player=FakePlayer('movie-tmdb-238', position=100.0), self_can_control_transport=True)
        p.onMessage(command('pause', 100.0, state='paused'))
        p.link.sent.clear()

        p.onLocalPause(True)

        self.assertEqual(p.link.sent, [])

    def test_a_guest_without_control_is_put_back(self):
        p = party(player=FakePlayer('movie-tmdb-238', position=10.0, paused=True))
        p.onMessage(command('play', 10.0, at='1970-01-01T00:16:40Z'))
        p.player.calls.clear()
        p.clock = lambda: 1010.0  # well after the command

        p.onLocalPause(True)

        self.assertEqual(p.link.sent, [])
        self.assertEqual(p.player.calls, [('paused', False)])
        self.assertEqual(len(p.player.notes), 1)


class PartyEndTest(KodiTestCase):
    def test_the_room_closing_stops_its_item(self):
        p = party(player=FakePlayer('movie-tmdb-238'))

        p.onMessage({'type': 'room_closed', 'reason': 'host_left'})

        self.assertEqual(p.player.calls, [('stop',)])
        self.assertEqual(p.ended, 'host_left')

    def test_another_item_starting_is_stopped(self):
        p = party(player=FakePlayer('movie-next-episode'))

        p.onLocalStart()

        self.assertEqual(p.player.calls, [('stop',)])
        self.assertEqual(len(p.player.notes), 1)

    def test_the_rooms_selection(self):
        p = party(anchor_position_seconds=61.5)

        self.assertEqual(p.selection(), ('movie-tmdb-238', 4711, 61.5))
        self.assertIsNone(party(phase='lobby').selection())
