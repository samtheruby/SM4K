"""
Watch together (decision D26): a watch party on a Silo server, kept in step over the room socket (silonet.room).

Party is the room as this device takes part in it: the room's transport commands run on Kodi's player at their
execute_at (on the server's clock, a late one projected forward; a player within a second of the room is left alone),
reports go out while the room's item plays (its playback session attached first, then a state report every 1.5 s,
marked ready while the room waits), and a pause or seek here becomes the room's request, or is undone for a guest the
host hasn't given control. The server corrects whoever drifts; this device only follows its commands.

The host starts a party from an item's pre-play screen (hostItem()); a guest joins one by its code from the user
menu (joinParty()) and plays whatever the room plays, until the room ends or they leave.
"""

import threading
import time

from kodi_six import xbmc

from lib import util
from lib.i18n import T

ECHO = 1.5  # seconds after a command runs in which the player's own events are its, not the user's
IN_STEP = 1.0  # seconds from the room within which a command doesn't seek
REPORT_EVERY, READY_EVERY = 1.5, 0.5  # seconds

# the party this add-on is in, if any (one at a time)
PARTY = None


def _timer(delay, fn):
    t = threading.Timer(delay, fn)
    t.daemon = True
    t.start()


class Party:
    def __init__(self, snapshot, player, link=None, later=_timer):
        self.snapshot = dict(snapshot)
        self.player, self.link, self.later = player, link, later
        self.clock = time.time
        self.lastCommand, self.lastTarget = None, None
        self.ended = None
        self.changed = threading.Event()
        self._echoUntil = 0.0
        self._stop = threading.Event()

    # the room
    @property
    def selected(self):
        return self.snapshot.get('selected_content_id')

    @property
    def isHost(self):
        return self.snapshot.get('self_role') == 'host'

    def selection(self):
        """What the room plays, (content id, file id, where it is now in seconds); None while it plays nothing."""
        if self.snapshot.get('phase') != 'playing' or not self.selected:
            return None
        position = float(self.snapshot.get('anchor_position_seconds') or 0)
        if self.snapshot.get('playback_state') == 'playing' and not self.snapshot.get('is_paused'):
            from silonet.room import epoch

            anchored = epoch(self.snapshot.get('anchor_updated_at'))
            if anchored is not None and self.link is not None:
                position += max(0.0, self.link.serverTime() - anchored)
        return self.selected, self.snapshot.get('selected_file_id'), position

    def _selfReady(self):
        return any(m.get('is_ready') for m in self.snapshot.get('members') or [] if m.get('is_self'))

    def _roomItemPlaying(self):
        return self.selected is not None and self.player.playingKey() == self.selected

    # the room socket's frames
    def onMessage(self, message):
        kind = message.get('type')
        if kind == 'snapshot' and message.get('room'):
            room = message['room']
            if room.get('generation', 0) >= self.snapshot.get('generation', 0):
                self.snapshot = room
            self.changed.set()
        elif kind == 'transport_command' and message.get('command'):
            self._schedule(message['command'])
        elif kind == 'room_closed':
            self._end(message.get('reason') or 'room_closed', T(35265, 'The watch party has ended'))
        elif kind == 'connection_replaced':
            self._end('connection_replaced', T(35266, 'This profile joined the watch party on another device'))
        elif kind == 'error' and message.get('code') in ('not_found', 'gone'):
            self._end(message['code'], T(35265, 'The watch party has ended'))

    def _schedule(self, command):
        from silonet.room import epoch

        executeAt = epoch(command.get('execute_at'))
        delay = 0.0 if executeAt is None or self.link is None else executeAt - self.link.serverTime()
        self.later(max(0.0, delay), lambda: self._apply(command))

    def _apply(self, command):
        if not self._roomItemPlaying():
            self.lastCommand, self.lastTarget = command, None
            return
        playing = command.get('playback_state') == 'playing'
        target = float(command.get('position_seconds') or 0)
        if playing and self.link is not None:
            from silonet.room import epoch

            executeAt = epoch(command.get('execute_at'))
            if executeAt is not None:
                target += max(0.0, self.link.serverTime() - executeAt)
        self._echoUntil = self.clock() + ECHO
        if command.get('action') == 'seek' or abs(self.player.position() - target) > IN_STEP:
            self.player.seek(target)
        if self.player.isPaused() == playing:
            self.player.setPaused(not playing)
        self.lastCommand, self.lastTarget = command, target

    # reports
    def tick(self):
        """One report: the playback session attached first, then where the player is. Nothing while the room's
        item isn't playing here."""
        if self.link is None or not self._roomItemPlaying():
            return
        session = self.player.sessionId(self.selected)
        if not session:
            return
        if self.snapshot.get('attached_session_id') != session:
            self.link.send({'type': 'attach_session', 'session_id': session})
            return
        position = round(self.player.position(), 3)
        report = {
            'type': 'state_report',
            'session_id': session,
            'position_seconds': position,
            'is_paused': self.player.isPaused(),
        }
        if self.lastCommand:
            report['command_id'] = self.lastCommand.get('command_id')
            if (
                self.snapshot.get('playback_state') == 'waiting'
                and not self._selfReady()
                and self.lastTarget is not None
                and abs(position - self.lastTarget) <= IN_STEP
            ):
                report['is_ready'] = True
        self.link.send(report)

    def waitingForMe(self):
        return self.snapshot.get('playback_state') == 'waiting' and not self._selfReady()

    def run(self):
        """Report until the party ends or is left (its own thread: start())."""
        while not self._stop.is_set() and self.ended is None:
            try:
                self.tick()
            except Exception:  # noqa: BLE001 - one failed report must not end the party's reports
                util.ERROR()
            self._stop.wait(READY_EVERY if self.waitingForMe() else REPORT_EVERY)

    def start(self):
        threading.Thread(target=self.run, name='silo.party', daemon=True).start()

    def stop(self):
        self._stop.set()
        self.changed.set()

    # the player's own events
    def _echo(self):
        return self.clock() < self._echoUntil

    def onLocalPause(self, paused):
        if self._echo() or not self._roomItemPlaying() or self.link is None:
            return
        position = round(self.player.position(), 3)
        if self.snapshot.get('self_can_control_transport'):
            self.link.send(
                {
                    'type': 'transport_request',
                    'action': 'pause' if paused else 'play',
                    'position_seconds': position,
                    'is_paused': paused,
                }
            )
            return
        self._echoUntil = self.clock() + ECHO
        self.player.setPaused(not paused)
        self.player.notify(T(35267, 'Only the host controls playback'))

    def onLocalSeek(self, position):
        if self._echo() or not self._roomItemPlaying() or self.link is None:
            return
        if self.snapshot.get('self_can_control_transport'):
            self.link.send(
                {
                    'type': 'transport_request',
                    'action': 'seek',
                    'position_seconds': round(position, 3),
                    'is_paused': self.player.isPaused(),
                }
            )
            return
        if self.lastTarget is not None:
            self._echoUntil = self.clock() + ECHO
            self.player.seek(self.lastTarget)
        self.player.notify(T(35267, 'Only the host controls playback'))

    def onLocalStart(self):
        """Something started playing: anything but the room's item is stopped for a guest (the host picks)."""
        key = self.player.playingKey()
        if key and key != self.selected and not self.isHost:
            self.player.stop()
            self.player.notify(T(35268, 'In a watch party, the host picks what plays'))

    def _end(self, reason, text):
        self.ended = reason
        if self._roomItemPlaying():
            self.player.stop()
        self.player.notify(text)
        self._stop.set()
        self.changed.set()


class KodiPlayer(xbmc.Player):
    """Kodi's player as a party sees it: what plays (Plex Uno's player's item, on the party's server), and its own
    events handed to the party."""

    def __init__(self, server):
        super().__init__()
        self.server = server
        self.party = None

    def playingKey(self):
        from lib import player

        video = player.PLAYER.video if self.isPlayingVideo() else None
        if video is None or getattr(video, 'server', None) is not self.server:
            return None
        return str(video.ratingKey)

    def position(self):
        try:
            return self.getTime()
        except RuntimeError:
            return 0.0

    def isPaused(self):
        return bool(xbmc.getCondVisibility('Player.Paused'))

    def seek(self, seconds):
        self.seekTime(max(0.0, seconds))

    def setPaused(self, paused):
        if self.isPaused() != paused:
            self.pause()

    def sessionId(self, key):
        attempt = self.server.playback.attempts.get(key)
        return attempt.sessionId if attempt is not None else None

    def notify(self, text):
        util.showNotification(text, header=T(35271, 'Watch party'))

    def onAVStarted(self):
        if self.party:
            self.party.onLocalStart()

    def onPlayBackPaused(self):
        if self.party:
            self.party.onLocalPause(True)

    def onPlayBackResumed(self):
        if self.party:
            self.party.onLocalPause(False)

    def onPlayBackSeek(self, time, seekOffset):
        if self.party:
            self.party.onLocalSeek(time / 1000.0)


class Session:
    """The party this add-on is in: its room, the room socket, the party and the player watching it."""

    def __init__(self, server, room):
        from silonet.room import RoomSocket

        self.server, self.room = server, room
        self.player = KodiPlayer(server)
        self.party = Party(room.snapshot, self.player)
        self.player.party = self.party
        self.link = RoomSocket(server.client, room, self.party.onMessage)
        self.party.link = self.link

    def begin(self):
        self.link.start()
        self.party.start()

    def leave(self):
        """Leave the party; the host's leaving ends it for everyone."""
        global PARTY
        self.party.stop()
        self.link.stop()
        self.server.pinnedFiles.pop(self.party.selected or '', None)
        if self.party.isHost and self.party.ended is None:
            from silonet.errors import SiloError

            try:
                self.room.end(self.server.client)
            except SiloError as e:
                util.LOG('Watch party: ending the room failed: {0}', e)
        if PARTY is self:
            PARTY = None

    @property
    def active(self):
        return self.party.ended is None and self.link.ended is None


def current(server=None):
    """The party in progress (on server, when given), or None."""
    if PARTY is None or not PARTY.active:
        return None
    if server is not None and PARTY.server is not server:
        return None
    return PARTY


def _begin(server, room):
    global PARTY
    if PARTY is not None:
        PARTY.leave()
    PARTY = Session(server, room)
    PARTY.begin()
    return PARTY


def hostItem(video, fileId):
    """Play video (its fileId version) for a party this profile hosts: a new one, or the one already in progress. The
    caller plays it from the start once this returns the party; None when Silo refused."""
    from silonet import room as rooms
    from silonet.errors import SiloError

    server = video.getServer()
    session = current(server)
    try:
        if session is None or not session.party.isHost:
            session = _begin(server, rooms.create(server.client))
            fresh = True
        else:
            fresh = False
        session.room.select(server.client, str(video.ratingKey), fileId)
    except SiloError as e:
        util.LOG('Watch party: hosting failed: {0}', e)
        util.showNotification(T(35270, "Couldn't start the watch party"), header=T(35271, 'Watch party'))
        return None
    session.party.snapshot = session.room.snapshot
    server.pinnedFiles[str(video.ratingKey)] = fileId
    util.LOG('Watch party: hosting {0} as room {1}', video.ratingKey, session.room.snapshot.get('code'))
    if fresh:
        util.messageDialog(
            T(35271, 'Watch party'),
            T(35263, 'Party code: {0}[CR]Others join from Silo or SM4K with this code.').format(
                session.room.snapshot.get('code') or ''
            ),
        )
    return session


def joinParty(server, play):
    """Join a party by its code and play what it plays (play(video, seconds) blocks while it plays), until it ends,
    or the user leaves it while it plays nothing."""
    from kodi_six import xbmcgui
    from silonet import room as rooms
    from silonet.errors import SiloError

    code = xbmcgui.Dialog().input(T(35262, 'Party code'))
    if not code or not code.strip():
        return
    try:
        session = _begin(server, rooms.join(server.client, code))
    except SiloError as e:
        util.LOG('Watch party: joining failed: {0}', e)
        util.showNotification(T(35272, 'No watch party has that code'), header=T(35271, 'Watch party'))
        return
    try:
        while session.active:
            selection = _waitForSelection(session)
            if selection is None:
                break
            contentId, fileId, seconds = selection
            revision = session.party.snapshot.get('selection_revision')
            server.pinnedFiles[contentId] = fileId
            play(server.getObject('/library/metadata/' + contentId), seconds)
            if not session.active:
                break
            snapshot = session.party.snapshot
            # stopped here while the room plays on
            stoppedHere = snapshot.get('phase') == 'playing' and snapshot.get('selection_revision') == revision
            if stoppedHere and xbmcgui.Dialog().yesno(T(35271, 'Watch party'), T(35273, 'Leave the watch party?')):
                break
    finally:
        session.leave()


def _waitForSelection(session):
    """What the room plays, waiting with a dialog while it plays nothing; None when the user leaves or it ends."""
    from kodi_six import xbmcgui

    selection = session.party.selection()
    if selection is not None:
        return selection
    dialog = xbmcgui.DialogProgress()
    dialog.create(T(35271, 'Watch party'), T(35264, 'Waiting for the host to start something...'))
    try:
        while session.active:
            if dialog.iscanceled():
                return None
            selection = session.party.selection()
            if selection is not None:
                return selection
            session.party.changed.clear()
            session.party.changed.wait(0.5)
    finally:
        dialog.close()
    return None
