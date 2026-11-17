"""Now-playing info from Windows' own media controls (works with the Spotify desktop app,
no internet or login needed). Runs in a background thread."""
import asyncio
import threading
import time

from PySide6.QtCore import QObject, Signal

import winapi

try:
    from winrt.windows.media.control import \
        GlobalSystemMediaTransportControlsSessionManager as MediaManager
    from winrt.windows.storage.streams import Buffer, DataReader, InputStreamOptions
    HAVE_WINRT = True
except Exception:  # library missing: fall back to media keys only
    HAVE_WINRT = False


def _secs(td):
    try:
        return td.total_seconds()
    except Exception:
        try:
            return int(td.duration) / 10_000_000
        except Exception:
            return 0.0


class MediaWatcher(QObject):
    updated = Signal(dict)

    def __init__(self):
        super().__init__()
        self._loop = None
        self._wake = None
        self._session = None
        self._stop = False
        if HAVE_WINRT:
            threading.Thread(target=self._run, daemon=True).start()

    # ------------------------------------------------------------ thread
    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._wake = asyncio.Event()
        self._loop.run_until_complete(self._main())

    @staticmethod
    def _pick(mgr):
        best = None
        try:
            for s in mgr.get_sessions():
                if "spotify" in (s.source_app_user_model_id or "").lower():
                    return s
        except Exception:
            pass
        try:
            best = mgr.get_current_session()
        except Exception:
            pass
        return best

    async def _read_thumb(self, ref):
        try:
            stream = await ref.open_read_async()
            size = int(stream.size)
            if not size:
                return None
            buf = Buffer(size)
            res = await stream.read_async(buf, size, InputStreamOptions.READ_AHEAD)
            try:
                return bytes(res)
            except Exception:
                reader = DataReader.from_buffer(res)
                arr = bytearray(res.length)
                reader.read_bytes(arr)
                return bytes(arr)
        except Exception:
            return None

    async def _main(self):
        mgr = None
        last_key = None
        thumb = None
        while not self._stop:
            info = {"available": False}
            try:
                if mgr is None:
                    mgr = await MediaManager.request_async()
                s = self._pick(mgr)
                self._session = s
                if s is not None:
                    props = await s.try_get_media_properties_async()
                    pb = s.get_playback_info()
                    title = props.title or ""
                    artist = props.artist or props.album_artist or ""
                    app = s.source_app_user_model_id or ""
                    key = (app, title, artist)
                    if key != last_key:
                        thumb = await self._read_thumb(props.thumbnail) if props.thumbnail else None
                        last_key = key
                    status = int(pb.playback_status) if pb else 0
                    pos = dur = 0.0
                    pos_ts = time.time()
                    try:
                        tl = s.get_timeline_properties()
                        pos = _secs(tl.position)
                        dur = _secs(tl.end_time) - _secs(tl.start_time)
                        try:
                            upd = tl.last_updated_time.timestamp()
                            if abs(time.time() - upd) < max(dur, 1) + 5:
                                pos_ts = upd
                        except Exception:
                            pass
                    except Exception:
                        pass
                    info = {"available": bool(title), "app": app, "title": title,
                            "artist": artist, "album": props.album_title or "",
                            "playing": status == 4, "pos": pos, "dur": dur, "pos_ts": pos_ts,
                            "thumb": thumb, "key": key,
                            "is_spotify": "spotify" in app.lower()}
            except Exception:
                mgr = None
                self._session = None
            self.updated.emit(info)
            try:
                await asyncio.wait_for(self._wake.wait(), 1.0)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()

    async def _do(self, name):
        s = self._session
        try:
            if s is None:
                raise RuntimeError
            if name == "toggle":
                await s.try_toggle_play_pause_async()
            elif name == "next":
                await s.try_skip_next_async()
            elif name == "prev":
                await s.try_skip_previous_async()
        except Exception:
            self._media_key(name)
        await asyncio.sleep(0.25)
        self._wake.set()

    # ------------------------------------------------------------ public
    @staticmethod
    def _media_key(name):
        vk = {"toggle": winapi.VK_MEDIA_PLAY_PAUSE, "next": winapi.VK_MEDIA_NEXT,
              "prev": winapi.VK_MEDIA_PREV}.get(name)
        if vk:
            winapi.press_key(vk)

    def command(self, name):
        if self._loop is None:
            self._media_key(name)
            return
        asyncio.run_coroutine_threadsafe(self._do(name), self._loop)
