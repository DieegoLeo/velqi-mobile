class AudioPlayer:
    def __init__(self):
        self.player = None
        self._android_jclass = None
        self._duration = 0
        self._seek_offset = 0
        self._setup()

    def _setup(self):
        try:
            from java import jclass
            jclass("android.os.Build")
            self._android_jclass = jclass
        except Exception:
            pass
        if not self._android_jclass:
            try:
                import pygame
                pygame.mixer.init()
            except ImportError:
                pass

    def play(self, filepath, duration_ms=0):
        if self._android_jclass:
            self.stop()
            MediaPlayer = self._android_jclass("android.media.MediaPlayer")
            self.player = MediaPlayer()
            self.player.setDataSource(filepath)
            self.player.prepare()
            self._duration = self.player.getDuration()
            self.player.start()
        else:
            try:
                import pygame
            except ImportError:
                raise Exception("pygame no instalado")
            self.stop()
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            self.player = True
            if duration_ms > 0:
                self._duration = duration_ms
        self._seek_offset = 0

    def stop(self):
        if self._android_jclass and self.player:
            try:
                self.player.stop()
                self.player.release()
            except Exception:
                pass
        elif self.player:
            try:
                import pygame
                pygame.mixer.music.stop()
            except Exception:
                pass
        self.player = None
        self._seek_offset = 0

    def pause(self):
        if self._android_jclass and self.player:
            self.player.pause()
        elif self.player:
            try:
                import pygame
                pygame.mixer.music.pause()
            except Exception:
                pass

    def resume(self):
        if self._android_jclass and self.player:
            self.player.start()
        elif self.player:
            try:
                import pygame
                pygame.mixer.music.unpause()
            except Exception:
                pass

    def get_pos(self):
        if self._android_jclass and self.player:
            return self.player.getCurrentPosition()
        else:
            try:
                import pygame
                return self._seek_offset + (pygame.mixer.music.get_pos() or 0)
            except Exception:
                return 0

    def get_duration(self):
        return self._duration

    def seek(self, pos_ms):
        if self._android_jclass and self.player:
            self.player.seekTo(int(pos_ms))
        else:
            try:
                import pygame
                pos_sec = pos_ms / 1000.0
                pygame.mixer.music.stop()
                pygame.mixer.music.play(start=pos_sec)
                self._seek_offset = pos_ms
            except Exception:
                pass

    def set_volume(self, vol):
        if self._android_jclass and self.player:
            try:
                self.player.setVolume(vol, vol)
            except Exception:
                pass
        else:
            try:
                import pygame
                pygame.mixer.music.set_volume(vol)
            except Exception:
                pass
