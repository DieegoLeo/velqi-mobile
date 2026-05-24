import asyncio
import base64
import os
import traceback
import flet as ft
import yt_dlp

from .constants import BG, CARD, SURFACE, SURFACE2, TEXT, TEXT_SEC, ACCENT
from .audio import AudioPlayer


class VelqiApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.audio = AudioPlayer()
        self.is_playing = False
        self.is_paused = False
        self.search_data = []
        self._seeking = False
        self._progress_task = None
        self._audio_vol = 0.8
        self._log_lines = []
        self._current_song = None
        self._prev_page = "home"

        self.cache_path = os.path.join(os.path.expanduser("~"), ".velqi_cache")
        os.makedirs(self.cache_path, exist_ok=True)

        self.downloads_path = os.path.join(os.path.expanduser("~"), ".velqi_downloads")
        os.makedirs(self.downloads_path, exist_ok=True)
        self.downloaded_songs = []
        self._load_downloads()
        self.downloading_songs = {}  # Track downloading songs: {video_id: {"progress": 0, "title": "..."}}
        
        # Configuración de usuario
        self.settings_path = os.path.join(os.path.expanduser("~"), ".velqi_settings.json")
        self.user_settings = self._load_settings()

        self._android = self._detect_android()
        self.ffmpeg_available = self._check_ffmpeg()
        self.cookies_file = self._find_cookies()

        self._log("Iniciando Velqi Mobile...")
        self._log(f"Caché: {self.cache_path}")
        self._log(f"Descargas: {self.downloads_path}")
        self._log("Miniaturas: usando URL directa de YouTube")
        self._log(f"Cookies: {self.cookies_file or 'no encontradas'}")
        self._log(f"FFmpeg: {'disponible' if self.ffmpeg_available else 'no encontrado'}")

        self._build_ui()
        self.nav_bar.selected_index = 0
        asyncio.create_task(self._run_splash())

    def _detect_android(self):
        try:
            from java import jclass
            jclass("android.os.Build")
            return True
        except Exception:
            return False

    def _check_ffmpeg(self):
        if self._android:
            self._log("Android: ffmpeg no disponible desde Python")
            return None
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
            path = get_ffmpeg_exe()
            self._log(f"FFmpeg encontrado: {path}")
            return path
        except Exception as e:
            self._log(f"FFmpeg no disponible: {e}")
            return None

    def _find_cookies(self):
        candidates = []
        bundled = os.path.join(os.path.dirname(__file__), "resources", "cookies.txt")
        if os.path.exists(bundled):
            candidates.append(bundled)
        cached = os.path.join(self.cache_path, "cookies.txt")
        if os.path.exists(cached):
            candidates.append(cached)
        try:
            import importlib.resources
            ref = importlib.resources.files("velqimobile.resources").joinpath("cookies.txt")
            with importlib.resources.as_file(ref) as path:
                if path.exists():
                    candidates.append(str(path))
        except Exception:
            pass
        for path in candidates:
            if self._valid_cookies(path):
                return path
        return ""

    def _valid_cookies(self, path):
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "\t" in line:
                        return True
            return False
        except Exception:
            return False

    def _thumb_url(self, video_id):
        return f"https://img.youtube.com/vi/{video_id}/default.jpg"

    # ---------- UI build ----------

    def _build_splash(self):
        logo_path = os.path.join(os.path.dirname(__file__), "resources", "logo.jpg")
        b64 = ""
        try:
            with open(logo_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
        except Exception:
            pass
        src = f"data:image/jpeg;base64,{b64}" if b64 else "logo.jpg"
        logo = ft.Image(src=src, width=240, height=240, fit="contain", filter_quality="high", anti_alias=True)

        self.splash = ft.Container(
            content=ft.Column(
                [ft.Container(expand=True), logo, ft.Container(expand=True)],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor="#000000",
            expand=True,
            opacity=0,
            animate_opacity=800,
        )

    async def _run_splash(self):
        await asyncio.sleep(0.1)
        try:
            self.splash.opacity = 1
            self.page.update()
            await asyncio.sleep(2.5)
            self.splash.opacity = 0
            self.page.update()
            await asyncio.sleep(0.6)
            self.page.controls.clear()
            self.page.bgcolor = BG
            self.page.add(
                ft.Column(
                    [self.content_area, self.miniplayer, self.nav_bar],
                    expand=True,
                    spacing=0,
                )
            )
            self.page.update()
            asyncio.create_task(self._animate_dashboard())
        except Exception:
            pass

    def _build_ui(self):
        self.page.title = "Velqi Mobile"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = "#000000"
        self.page.padding = 0
        self.page.window_width = 420
        self.page.window_height = 780

        self._build_nav_bar()
        self._build_player_bar()
        self._build_player_view()
        self._build_home_view()
        self._build_search_view()
        self._build_downloads_view()
        self._build_settings_view()

        self.content_area = ft.Container(content=self.home_view, expand=True, bgcolor=BG, animate_opacity=300)

        self._build_splash()

        self.page.add(self.splash)
        self.page.update()

    def _build_nav_bar(self):
        self.nav_bar = ft.NavigationBar(
            selected_index=0,
            on_change=self._on_nav_change,
            destinations=[
                ft.NavigationBarDestination(icon=ft.icons.Icons.DASHBOARD_OUTLINED, selected_icon=ft.icons.Icons.DASHBOARD, label="Dashboard"),
                ft.NavigationBarDestination(icon=ft.icons.Icons.DOWNLOAD_OUTLINED, selected_icon=ft.icons.Icons.DOWNLOAD_DONE_ROUNDED, label="Descargas"),
                ft.NavigationBarDestination(icon=ft.icons.Icons.SEARCH_OUTLINED, selected_icon=ft.icons.Icons.SEARCH, label="Buscar"),
                ft.NavigationBarDestination(icon=ft.icons.Icons.SETTINGS_OUTLINED, selected_icon=ft.icons.Icons.SETTINGS, label="Ajustes"),
            ],
            bgcolor=SURFACE,
            indicator_color=SURFACE2,
            height=56,
            label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
        )

    def _on_nav_change(self, e):
        if e.control.selected_index == 0:
            self._show_page("home")
        elif e.control.selected_index == 1:
            self._show_page("downloads")
        elif e.control.selected_index == 2:
            self._show_page("search")
        else:
            self._show_page("settings")
        
    def _build_home_view(self):
        title = ft.Text("Dashboard", size=22, weight=ft.FontWeight.BOLD, color=TEXT)

        credits = ft.Card(
            bgcolor=CARD,
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Credits", size=14, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Container(height=6),
                    ft.Text("SalvAmigos — Developer", size=11, color=TEXT_SEC),
                    ft.Text("it's_d4nnyx — Contributor", size=11, color=TEXT_SEC),
                    ft.Text("AdrianCrak30 — Contributor", size=11, color=TEXT_SEC),
                    ft.Text("Val — Contributor", size=11, color=TEXT_SEC),
                ], spacing=1),
                padding=12,
            ),
        )

        version_card = ft.Card(
            bgcolor=CARD,
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Version", size=14, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Container(height=6),
                    ft.Text("v1.0", size=12, color=TEXT_SEC),
                ], spacing=1, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=12,
            ),
        )

        row1 = ft.Row(
            [ft.Container(content=credits, expand=2), ft.Container(content=version_card, expand=1)],
            spacing=8,
        )

        updates = ft.Card(
            bgcolor=CARD,
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Latest Update", size=14, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Container(height=6),
                    ft.Text("• Initial release", size=11, color=TEXT_SEC),
                    ft.Text("• YouTube search & playback", size=11, color=TEXT_SEC),
                    ft.Text("• Dark theme with white contrast", size=11, color=TEXT_SEC),
                    ft.Text("• Splash screen with logo", size=11, color=TEXT_SEC),
                ], spacing=1),
                padding=12,
            ),
        )

        self.dash_title = ft.Container(
            content=title,
            opacity=0,
            offset=(0, 0.3),
            animate_opacity=600,
            animate_offset=600,
        )

        self.dash_row1 = ft.Container(
            content=row1,
            opacity=0,
            offset=(0, 0.3),
            animate_opacity=600,
            animate_offset=600,
        )

        self.dash_updates = ft.Container(
            content=updates,
            opacity=0,
            offset=(0, 0.3),
            animate_opacity=600,
            animate_offset=600,
        )

        self.home_view = ft.Container(
            content=ft.Column(
                [
                    ft.Container(height=20),
                    self.dash_title,
                    ft.Container(height=12),
                    self.dash_row1,
                    ft.Container(height=8),
                    self.dash_updates,
                ],
                scroll=ft.ScrollMode.AUTO,
            ),
            bgcolor=BG,
            expand=True,
            padding=16,
        )

    async def _animate_dashboard(self):
        await asyncio.sleep(0.1)
        self.dash_title.opacity = 1
        self.dash_title.offset = (0, 0)
        self.page.update()
        await asyncio.sleep(0.3)
        self.dash_row1.opacity = 1
        self.dash_row1.offset = (0, 0)
        self.page.update()
        await asyncio.sleep(0.3)
        self.dash_updates.opacity = 1
        self.dash_updates.offset = (0, 0)
        self.page.update()

    def _build_search_view(self):
        self.search_input = ft.TextField(
            hint_text="Buscar canciones...",
            on_submit=self._on_search_submit,
            border_radius=28,
            filled=True,
            bgcolor=SURFACE,
            color=TEXT,
            hint_style=ft.TextStyle(color=TEXT_SEC),
            prefix_icon=ft.icons.Icons.SEARCH,
            expand=True,
            height=48,
            text_size=15,
            content_padding=ft.Padding(left=20, right=20, top=0, bottom=0),
        )
        self.search_btn = ft.Container(
            content=ft.IconButton(
                icon=ft.icons.Icons.ARROW_FORWARD,
                icon_size=22,
                icon_color=BG,
                bgcolor=ACCENT,
                on_click=self._on_search_submit,
            ),
            border_radius=28,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )
        self.search_status = ft.Text(
            "",
            size=12,
            color=TEXT_SEC,
            text_align=ft.TextAlign.CENTER,
            visible=False,
            selectable=True,
        )
        search_row = ft.Container(
            content=ft.Row(
                [self.search_input, self.search_btn],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            padding=ft.Padding(left=16, right=16, top=24, bottom=8),
        )

        self.results_list = ft.ListView(spacing=8, padding=ft.Padding(left=12, right=12, top=4, bottom=12), expand=True)

        self.search_spinner = ft.ProgressRing(width=24, height=24, visible=False, color=ACCENT)

        self.search_view = ft.Container(
            content=ft.Column(
                [search_row, self.search_spinner, self.search_status, self.results_list],
                expand=True,
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=BG,
            expand=True,
        )

    def _build_player_bar(self):
        self.player_thumb = ft.Container(
            width=44,
            height=44,
            border_radius=8,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            bgcolor=SURFACE2,
        )

        self.song_label = ft.Text("Ninguna cancion", size=13, color=TEXT, weight=ft.FontWeight.W_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)

        self.play_btn = ft.IconButton(
            icon=ft.icons.Icons.PLAY_ARROW_ROUNDED,
            icon_size=24,
            icon_color=TEXT,
            on_click=self._on_toggle_play,
        )

        self.close_btn = ft.IconButton(
            icon=ft.icons.Icons.CLOSE,
            icon_size=18,
            icon_color=TEXT_SEC,
            on_click=self._on_stop,
        )

        self.miniplayer = ft.Container(
            content=ft.Row(
                [
                    self.player_thumb,
                    ft.Container(content=self.song_label, expand=True, padding=ft.Padding(left=4, right=4, top=0, bottom=0)),
                    self.play_btn,
                    self.close_btn,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
            ),
            padding=ft.Padding(left=12, right=4, top=8, bottom=8),
            bgcolor=CARD,
            border_radius=12,
            border=ft.border.Border(
                ft.border.BorderSide(0.5, SURFACE2),
                ft.border.BorderSide(0.5, SURFACE2),
                ft.border.BorderSide(0.5, SURFACE2),
                ft.border.BorderSide(0.5, SURFACE2),
            ),
            margin=ft.Margin(left=12, right=12, bottom=0, top=0),
            visible=False,
            animate_opacity=300,
            animate=300,
            on_click=self._open_player_view,
        )

    def _build_player_view(self):
        self.player_art = ft.Container(
            width=180,
            height=180,
            border_radius=16,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            bgcolor=SURFACE2,
        )

        self.player_title = ft.Text("", size=17, weight=ft.FontWeight.BOLD, color=TEXT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, text_align=ft.TextAlign.CENTER)
        self.player_artist = ft.Text("", size=12, color=TEXT_SEC, text_align=ft.TextAlign.CENTER)

        self.player_seeker = ft.Slider(
            min=0,
            max=100,
            value=0,
            on_change_start=self._on_seek_start,
            on_change_end=self._on_seek_end,
            active_color=ACCENT,
            inactive_color=SURFACE2,
            thumb_color=ACCENT,
            expand=True,
            height=32,
        )

        self.player_time = ft.Text("0:00 / 0:00", size=11, color=TEXT_SEC)

        self.player_play_btn = ft.IconButton(
            icon=ft.icons.Icons.PLAY_ARROW_ROUNDED,
            icon_size=48,
            icon_color=BG,
            bgcolor=ACCENT,
            on_click=self._on_toggle_play,
        )

        self.player_vol_slider = ft.Slider(
            min=0,
            max=100,
            value=int(self._audio_vol * 100),
            on_change=self._on_volume_change,
            active_color=ACCENT,
            inactive_color=SURFACE2,
            thumb_color=ACCENT,
            width=120,
            height=20,
        )

        back_btn = ft.IconButton(
            icon=ft.icons.Icons.ARROW_BACK,
            icon_size=22,
            icon_color=TEXT,
            on_click=self._close_player_view,
        )

        self.player_view = ft.Container(
            content=ft.Column(
                [
                    ft.Row([back_btn], alignment=ft.MainAxisAlignment.START),
                    ft.Container(height=8),
                    ft.Row([self.player_art], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Container(height=16),
                    self.player_title,
                    ft.Container(height=2),
                    self.player_artist,
                    ft.Container(height=12),
                    self.player_seeker,
                    ft.Row([self.player_time], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Container(height=10),
                    ft.Row([self.player_play_btn], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Container(height=12),
                    ft.Row(
                        [ft.Text("Vol", size=11, color=TEXT_SEC), self.player_vol_slider],
                        alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=BG,
            expand=True,
            padding=ft.Padding(left=24, right=24, top=8, bottom=16),
        )

    # ---------- Page switching ----------

    def _log(self, msg):
        print(f"[Velqi] {msg}")
        self._log_lines.append(msg)
        if len(self._log_lines) > 50:
            self._log_lines = self._log_lines[-50:]

    def _show_page(self, page_name):
        self.content_area.opacity = 0
        self.page.update()
        if page_name == "home":
            self.dash_title.opacity = 0
            self.dash_title.offset = (0, 0.3)
            self.dash_row1.opacity = 0
            self.dash_row1.offset = (0, 0.3)
            self.dash_updates.opacity = 0
            self.dash_updates.offset = (0, 0.3)
            self.content_area.content = self.home_view
            self.nav_bar.selected_index = 0
        elif page_name == "downloads":
            self.content_area.content = self.downloads_view
            self.nav_bar.selected_index = 1
            self._refresh_downloads()
        elif page_name == "search":
            self.content_area.content = self.search_view
            self.nav_bar.selected_index = 2
        else:  # settings
            self.content_area.content = self.settings_view
            self.nav_bar.selected_index = 3
        self.content_area.opacity = 1
        if not self.page.web:
            self.page.update()
        if page_name == "home":
            asyncio.create_task(self._animate_dashboard())

    def _open_player_view(self, e=None):
        if not self._current_song:
            return
        idx = self.nav_bar.selected_index
        self._prev_page = "home" if idx == 0 else ("downloads" if idx == 1 else ("search" if idx == 2 else "settings"))
        self.player_play_btn.icon = ft.icons.Icons.PAUSE_ROUNDED if self.is_playing else ft.icons.Icons.PLAY_ARROW_ROUNDED
        self.content_area.content = self.player_view
        self.content_area.opacity = 1
        self.nav_bar.visible = False
        self.miniplayer.visible = False
        self.page.update()

    def _close_player_view(self, e=None):
        self.nav_bar.visible = True
        self.miniplayer.visible = bool(self._current_song)
        if self._prev_page == "home":
            self.content_area.content = self.home_view
        elif self._prev_page == "downloads":
            self.content_area.content = self.downloads_view
            self._refresh_downloads()
        elif self._prev_page == "search":
            self.content_area.content = self.search_view
        else:  # settings
            self.content_area.content = self.settings_view
        self.content_area.opacity = 1
        self.page.update()

    # ---------- Search ----------

    def _on_search_submit(self, e):
        query = self.search_input.value.strip()
        if query:
            self._log(f"Buscando: {query}")
            self.search_status.value = "Buscando..."
            self.search_status.visible = True
            self.search_spinner.visible = True
            self.results_list.controls.clear()
            self.results_list.update()
            self.page.update()
            asyncio.create_task(self._do_search(query))

    async def _do_search(self, query):
        try:
            ydl_opts = {
                "format": "bestaudio/best",
                "quiet": True,
                "no_warnings": True,
                "extract_flat": "in_playlist",
            }
            if self.cookies_file:
                ydl_opts["cookiefile"] = self.cookies_file
                self._log(f"Usando cookies: {self.cookies_file}")
            else:
                self._log("Sin cookies - puede fallar")

            loop = asyncio.get_event_loop()
            self._log("Ejecutando yt-dlp search...")
            info = await loop.run_in_executor(None, self._run_ydl_search, ydl_opts, query)
            entries = info.get("entries", [])
            self._log(f"Resultados: {len(entries)} encontrados")

            if not entries:
                self.search_status.value = "Sin resultados. Intenta otra busqueda."
                self.search_status.visible = True
                self.search_spinner.visible = False
                self.page.update()
                return

            self.search_data = [
                {
                    "id": e.get("id"),
                    "title": e.get("title", "Unknown"),
                    "uploader": e.get("uploader", "Unknown"),
                    "duration": e.get("duration", 0),
                }
                for e in entries
            ]

            self._log("Generando miniaturas (URL directa)...")
            for song in self.search_data:
                song["thumb"] = self._thumb_url(song["id"])
            self._log(f"Miniaturas listas para {len(self.search_data)} canciones")

            self.search_status.visible = False
            self.search_spinner.visible = False
            self._update_results()
            self._log("Busqueda completada")
        except yt_dlp.utils.DownloadError as e:
            self.search_spinner.visible = False
            emsg = str(e)
            self._log(f"Error de descarga: {emsg}")
            if "HTTP Error 403" in emsg or "Sign in" in emsg or "cookie" in emsg:
                self._show_error("YouTube bloqueo la busqueda.\nTus cookies pueden haber expirado.\nActualiza resources/cookies.txt")
            else:
                self._show_error(f"Error de conexion:\n{emsg}")
        except Exception as e:
            self.search_spinner.visible = False
            tb = traceback.format_exc()
            self._log(f"Error: {e}")
            self._log(tb)
            self._show_error(f"Error al buscar:\n{e}")

    def _run_ydl_search(self, opts, query):
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(f"ytsearch15:{query}", download=False)

    def _update_results(self):
        self.results_list.controls.clear()
        for i, song in enumerate(self.search_data):
            card = self._build_card(song, i)
            self.results_list.controls.append(card)
        self.results_list.update()
        self.page.update()

    def _build_card(self, song, index):
        thumb_path = song.get("thumb")
        dur = song.get("duration", 0) or 0
        dur_int = int(dur)
        dur_str = f"{dur_int//60}:{dur_int%60:02d}" if dur_int else "?"

        dur_badge = ft.Container(
            content=ft.Text(dur_str, size=9, color="#ffffff", weight=ft.FontWeight.W_600),
            bgcolor=ft.Colors.with_opacity(0.8, "#000000"),
            border_radius=4,
            padding=ft.Padding(left=4, right=4, top=2, bottom=2),
        )

        thumb = ft.Stack(
            [
                ft.Container(
                    width=56,
                    height=56,
                    border_radius=10,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    content=ft.Image(src=thumb_path, fit="cover") if thumb_path else ft.Container(bgcolor=SURFACE2),
                ),
                ft.Container(
                    content=dur_badge,
                    alignment=ft.alignment.Alignment(1, 1),
                    padding=ft.Padding(right=3, bottom=3, left=0, top=0),
                ),
            ],
            width=56,
            height=56,
        )

        title = ft.Text(song["title"], size=14, color=TEXT, weight=ft.FontWeight.W_600, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)
        subtitle = ft.Row(
            [
                ft.Icon(ft.icons.Icons.PERSON_OUTLINE, size=10, color=TEXT_SEC),
                ft.Text(song["uploader"], size=11, color=TEXT_SEC, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        info = ft.Column([title, subtitle], spacing=3, expand=True)

        vid = song.get("id", "")
        already_dl = any(d.get("id") == vid for d in self.downloaded_songs)
        is_downloading = vid in self.downloading_songs
        
        if is_downloading:
            # Mostrar indicador de progreso
            progress = self.downloading_songs[vid].get("progress", 0)
            dl_btn = ft.Container(
                content=ft.Column([
                    ft.ProgressRing(width=20, height=20, value=progress/100, color=ACCENT),
                    ft.Text(f"{int(progress)}%", size=8, color=TEXT_SEC)
                ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=2,
            )
        elif already_dl:
            # Ya descargada
            dl_btn = ft.Container(
                content=ft.IconButton(
                    icon=ft.icons.Icons.DONE,
                    icon_size=20,
                    icon_color=TEXT_SEC,
                    on_click=lambda _, idx=index: self._on_download_click(idx),
                ),
            )
        else:
            # Disponible para descargar
            dl_btn = ft.Container(
                content=ft.IconButton(
                    icon=ft.icons.Icons.DOWNLOAD_OUTLINED,
                    icon_size=20,
                    icon_color="#777777",
                    on_click=lambda _, idx=index: self._on_download_click(idx),
                ),
            )

        play_btn = ft.Container(
            content=ft.IconButton(
                icon=ft.icons.Icons.PLAY_ARROW_ROUNDED,
                icon_size=28,
                icon_color=BG,
                bgcolor=ACCENT,
                on_click=lambda _, idx=index: self._on_card_play(idx),
            ),
            border_radius=28,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

        card = ft.Container(
            content=ft.Row(
                [thumb, info, dl_btn, play_btn],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
            bgcolor=CARD,
            border_radius=12,
            padding=ft.Padding(left=10, top=8, right=4, bottom=8),
            border=ft.border.Border(
                ft.border.BorderSide(0.5, SURFACE2),
                ft.border.BorderSide(0.5, SURFACE2),
                ft.border.BorderSide(0.5, SURFACE2),
                ft.border.BorderSide(0.5, SURFACE2),
            ),
            ink=True,
            animate_opacity=400,
        )
        return card

    # ---------- Downloads ----------

    def _on_download_click(self, index):
        if index >= len(self.search_data):
            return
        song = self.search_data[index]
        vid = song.get("id", "")
        if any(d.get("id") == vid for d in self.downloaded_songs):
            return
        if vid in self.downloading_songs:
            return  # Ya se está descargando
        asyncio.create_task(self._download_song(song, index))

    async def _download_song(self, song, card_index):
        vid = song.get("id", "")
        self._log(f"Descargando: {song['title']}")
        
        # Agregar a la lista de descargas en progreso
        self.downloading_songs[vid] = {
            "progress": 0,
            "title": song.get("title", "Unknown"),
            "card_index": card_index
        }
        self._update_results()  # Actualizar para mostrar indicador de progreso
        
        video_url = f"https://www.youtube.com/watch?v={vid}"
        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio*/best",
            "outtmpl": os.path.join(self.downloads_path, f"{vid}.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "max_filesize": 50_000_000,
            "progress_hooks": [self._create_progress_hook(vid)],
        }
        if self.cookies_file:
            ydl_opts["cookiefile"] = self.cookies_file
        if self.ffmpeg_available:
            ydl_opts["ffmpeg_location"] = self.ffmpeg_available
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
            }]
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._run_ydl_download_with_progress, video_url, ydl_opts)
            entry = {
                "id": vid,
                "title": song.get("title", "Unknown"),
                "uploader": song.get("uploader", "Unknown"),
                "duration": song.get("duration", 0),
                "thumb": song.get("thumb", ""),
            }
            self.downloaded_songs.append(entry)
            self._save_downloads()
            self._log(f"Descargado: {song['title']}")
            
            # Remover de descargas en progreso
            if vid in self.downloading_songs:
                del self.downloading_songs[vid]
            
            self._update_results()
        except Exception as e:
            self._log(f"Error descargando: {e}")
            # Remover de descargas en progreso en caso de error
            if vid in self.downloading_songs:
                del self.downloading_songs[vid]
            self._update_results()

    def _save_downloads(self):
        import json
        path = os.path.join(self.downloads_path, "metadata.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.downloaded_songs, f, ensure_ascii=False)
        except Exception:
            pass

    def _load_downloads(self):
        import json
        path = os.path.join(self.downloads_path, "metadata.json")
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    self.downloaded_songs = json.load(f)
        except Exception:
            self.downloaded_songs = []

    def _load_settings(self):
        import json
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        # Configuración por defecto
        return {
            "theme": "dark"
        }

    def _save_settings(self):
        import json
        try:
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(self.user_settings, f, ensure_ascii=False)
        except Exception:
            pass

    # ---------- Settings handlers ----------
    
    def _on_theme_change(self, e):
        theme = "light" if e.control.value else "dark"
        self.user_settings["theme"] = theme
        self._save_settings()
        
        # Aplicar tema
        self.page.theme_mode = ft.ThemeMode.LIGHT if theme == "light" else ft.ThemeMode.DARK
        
        # Actualizar colores según el tema
        if theme == "light":
            self.page.bgcolor = "#FFFFFF"
            if hasattr(self, 'content_area'):
                self.content_area.bgcolor = "#FFFFFF"
            if hasattr(self, 'home_view'):
                self.home_view.bgcolor = "#FFFFFF"
            if hasattr(self, 'downloads_view'):
                self.downloads_view.bgcolor = "#FFFFFF"
            if hasattr(self, 'search_view'):
                self.search_view.bgcolor = "#FFFFFF"
            if hasattr(self, 'settings_view'):
                self.settings_view.bgcolor = "#FFFFFF"
        else:
            self.page.bgcolor = "#000000"
            if hasattr(self, 'content_area'):
                self.content_area.bgcolor = BG
            if hasattr(self, 'home_view'):
                self.home_view.bgcolor = BG
            if hasattr(self, 'downloads_view'):
                self.downloads_view.bgcolor = BG
            if hasattr(self, 'search_view'):
                self.search_view.bgcolor = BG
            if hasattr(self, 'settings_view'):
                self.settings_view.bgcolor = BG
        
        self.page.update()
        self._log(f"Tema cambiado a: {theme}")

    def _on_export_now(self, e):
        # Debug: verificar que el botón funciona
        self._log("DEBUG: Botón Exportar ahora clickeado")
        print(f"DEBUG: Botón Exportar clickeado, downloaded_songs: {len(self.downloaded_songs)}")
        
        # Mostrar diálogo de confirmación
        self._show_export_confirmation()
    
    def _show_export_confirmation(self):
        """Mostrar diálogo de confirmación para exportar"""
        self._log("DEBUG: Mostrando diálogo de confirmación")
        
        export_path = self.export_path_input.value.strip()
        if not export_path:
            # En Android, usar ruta de almacenamiento externo
            if self._android:
                export_path = "/storage/emulated/0/Music/Velqi"
            else:
                export_path = os.path.join(os.path.expanduser("~"), "Music", "Velqi")
            
            self.export_path_input.value = export_path
            self.export_path_input.update()
        
        self._log(f"DEBUG: Ruta de exportación: {export_path}")
        self._log(f"DEBUG: Canciones para exportar: {len(self.downloaded_songs)}")
        
        # Crear diálogo de confirmación
        self.export_dialog = ft.AlertDialog(
            title=ft.Text("Confirmar exportación"),
            content=ft.Column([
                ft.Text(f"¿Exportar {len(self.downloaded_songs)} canciones a:"),
                ft.Text(export_path, size=12, color=TEXT_SEC, selectable=True),
                ft.Text("¿Continuar?", size=14, weight=ft.FontWeight.W_500),
            ], tight=True, spacing=12),
            actions=[
                ft.TextButton("Cancelar", on_click=self._close_export_dialog),
                ft.TextButton("Exportar", on_click=self._start_export, style=ft.ButtonStyle(color=ACCENT)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.dialog = self.export_dialog
        self.export_dialog.open = True
        self.page.update()
        self._log("DEBUG: Diálogo mostrado")
    
    def _close_export_dialog(self, e):
        self.export_dialog.open = False
        self.page.update()
    
    def _start_export(self, e):
        self._log("DEBUG: Iniciando exportación desde diálogo")
        self.export_dialog.open = False
        self.page.update()
        asyncio.create_task(self._export_all_songs())

    async def _export_all_songs(self):
        """Exportar todas las canciones descargadas a la carpeta especificada"""
        self._log("DEBUG: _export_all_songs() llamado")
        print(f"DEBUG: Iniciando exportación, Android: {self._android}")
        
        # Si estamos en proyección (desarrollo), mostrar mensaje informativo
        if not self._android:
            self._log("DEBUG: Modo desarrollo/proyección detectado")
            self.search_status.value = "⚠️ En modo desarrollo:\nCompila como APK para exportar\n\nRuta simulada: ~/Music/Velqi/"
            self.search_status.visible = True
            self.page.update()
            await asyncio.sleep(5)
            self.search_status.visible = False
            self.page.update()
            return
        
        # Obtener ruta del campo de entrada
        export_dir = self.export_path_input.value.strip()
        if not export_dir:
            # En Android, usar ruta de almacenamiento externo
            export_dir = "/storage/emulated/0/Music/Velqi"
            self.export_path_input.value = export_dir
            self.export_path_input.update()
        
        self._log(f"DEBUG: Ruta de exportación: {export_dir}")
        self._log(f"DEBUG: Canciones descargadas: {len(self.downloaded_songs)}")
        
        # Verificar si hay canciones para exportar
        if not self.downloaded_songs:
            self._log("DEBUG: No hay canciones para exportar")
            self.search_status.value = "No hay canciones descargadas para exportar"
            self.search_status.visible = True
            self.page.update()
            await asyncio.sleep(3)
            self.search_status.visible = False
            self.page.update()
            return
        
        try:
            # Crear directorio si no existe
            os.makedirs(export_dir, exist_ok=True)
            
            exported_count = 0
            failed_count = 0
            
            self._log(f"Iniciando exportación a: {export_dir}")
            self.search_status.value = f"Exportando a: {export_dir}..."
            self.search_status.visible = True
            self.page.update()
            
            for song in self.downloaded_songs:
                vid = song.get("id", "")
                source_file = None
                
                # Buscar el archivo de audio
                for fname in os.listdir(self.downloads_path):
                    if fname.startswith(vid) and not fname.endswith(".json"):
                        source_file = os.path.join(self.downloads_path, fname)
                        break
                
                if source_file and os.path.exists(source_file):
                    # Crear nombre de archivo seguro
                    title = song.get("title", "Unknown")
                    # Reemplazar caracteres problemáticos
                    safe_title = "".join(c for c in title if c.isalnum() or c in " .-_")
                    safe_title = safe_title[:80]  # Limitar longitud
                    
                    if not safe_title.strip():
                        safe_title = f"cancion_{vid}"
                    
                    # Determinar extensión del archivo
                    ext = os.path.splitext(source_file)[1]
                    if not ext:
                        ext = ".mp3"
                    
                    dest_file = os.path.join(export_dir, f"{safe_title}{ext}")
                    
                    # Si el archivo ya existe, agregar número
                    counter = 1
                    base_dest_file = dest_file
                    while os.path.exists(dest_file):
                        name, ext = os.path.splitext(base_dest_file)
                        dest_file = f"{name} ({counter}){ext}"
                        counter += 1
                    
                    try:
                        import shutil
                        shutil.copy2(source_file, dest_file)
                        exported_count += 1
                        self._log(f"✓ Exportado: {title}")
                    except Exception as ex:
                        failed_count += 1
                        self._log(f"✗ Error exportando {title}: {ex}")
                else:
                    failed_count += 1
                    self._log(f"✗ Archivo no encontrado para: {song.get('title', 'Unknown')}")
            
            # Mostrar resultado
            if exported_count > 0:
                result_msg = f"✅ Exportadas {exported_count} canciones a:\n{export_dir}"
                if failed_count > 0:
                    result_msg += f"\n({failed_count} fallidas)"
            else:
                result_msg = f"❌ No se pudo exportar ninguna canción"
            
            self._log(result_msg)
            
            # Mostrar notificación en la interfaz
            self.search_status.value = result_msg
            self.search_status.visible = True
            self.page.update()
            
            # Mantener el mensaje visible por 5 segundos
            await asyncio.sleep(5)
            self.search_status.visible = False
            self.page.update()
            
        except Exception as e:
            error_msg = f"Error al exportar: {str(e)}"
            self._log(error_msg)
            self.search_status.value = error_msg
            self.search_status.visible = True
            self.page.update()
            await asyncio.sleep(3)
            self.search_status.visible = False
            self.page.update()

    def _create_progress_hook(self, video_id):
        def progress_hook(d):
            if d['status'] == 'downloading':
                # Actualizar progreso
                if video_id in self.downloading_songs:
                    if 'total_bytes' in d and d['total_bytes']:
                        progress = (d.get('downloaded_bytes', 0) / d['total_bytes']) * 100
                        self.downloading_songs[video_id]["progress"] = progress
                        self._update_results()
                    elif 'total_bytes_estimate' in d and d['total_bytes_estimate']:
                        progress = (d.get('downloaded_bytes', 0) / d['total_bytes_estimate']) * 100
                        self.downloading_songs[video_id]["progress"] = progress
                        self._update_results()
            elif d['status'] == 'finished':
                # Descarga completada, ahora procesando
                if video_id in self.downloading_songs:
                    self.downloading_songs[video_id]["progress"] = 100
                    self._update_results()
        return progress_hook

    def _run_ydl_download_with_progress(self, url, opts):
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)

    def _refresh_downloads(self):
        if not hasattr(self, "downloads_list"):
            return
        self.downloads_list.controls.clear()
        if not self.downloaded_songs:
            self.downloads_list.controls.append(
                ft.Container(
                    content=ft.Text("No hay descargas", size=13, color=TEXT_SEC, text_align=ft.TextAlign.CENTER),
                    padding=40,
                )
            )
        else:
            for i, song in enumerate(self.downloaded_songs):
                self.downloads_list.controls.append(self._build_downloaded_card(song, i))
        # Solo actualizar si el control está montado en la página
        try:
            # Verificar si el control está montado sin acceder a .page directamente
            self.downloads_list.update()
        except RuntimeError:
            # El control no está montado aún, no hacer update
            pass

    def _build_downloaded_card(self, song, index):
        thumb_path = song.get("thumb")
        dur = song.get("duration", 0) or 0
        dur_int = int(dur)
        dur_str = f"{dur_int//60}:{dur_int%60:02d}" if dur_int else "?"

        thumb = ft.Container(
            width=48,
            height=48,
            border_radius=8,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Image(src=thumb_path, fit="cover") if thumb_path else ft.Container(bgcolor=SURFACE2),
        )

        title = ft.Text(song.get("title", "Unknown"), size=13, color=TEXT, weight=ft.FontWeight.W_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        subtitle = ft.Text(f"{song.get('uploader', '')}  {dur_str}", size=11, color=TEXT_SEC)
        info = ft.Column([title, subtitle], spacing=1, expand=True)

        play_btn = ft.Container(
            content=ft.IconButton(
                icon=ft.icons.Icons.PLAY_ARROW_ROUNDED,
                icon_size=28,
                icon_color=BG,
                bgcolor=ACCENT,
                on_click=lambda _, idx=index: self._on_downloaded_play(idx),
            ),
            border_radius=28,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

        return ft.Container(
            content=ft.Row([thumb, info, play_btn], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            bgcolor=CARD,
            border_radius=10,
            padding=ft.Padding(left=10, top=8, right=6, bottom=8),
            border=ft.border.Border(
                ft.border.BorderSide(0.5, SURFACE2),
                ft.border.BorderSide(0.5, SURFACE2),
                ft.border.BorderSide(0.5, SURFACE2),
                ft.border.BorderSide(0.5, SURFACE2),
            ),
        )

    def _on_downloaded_play(self, index):
        if index >= len(self.downloaded_songs):
            return
        song = self.downloaded_songs[index]
        vid = song.get("id", "")
        filepath = None
        for fname in os.listdir(self.downloads_path):
            if fname.startswith(vid) and not fname.endswith(".json"):
                filepath = os.path.join(self.downloads_path, fname)
                break
        if not filepath:
            self._log(f"Archivo no encontrado para {song['title']}")
            return
        self._current_song = song
        thumb_path = song.get("thumb")
        if thumb_path:
            self.player_thumb.content = ft.Image(src=thumb_path, fit="cover")
        else:
            self.player_thumb.content = ft.Container(bgcolor=SURFACE2)
        if self._progress_task and not self._progress_task.done():
            self._progress_task.cancel()
            self._progress_task = None
        self.miniplayer.visible = True
        self.song_label.value = song.get("title", "Sin título")
        self.play_btn.icon = ft.icons.Icons.PLAY_ARROW_ROUNDED
        self.page.update()
        try:
            dur_ms = (song.get("duration", 0) or 0) * 1000
            self.audio.play(filepath, dur_ms)
            self.is_playing = True
            self.is_paused = False
            self.play_btn.icon = ft.icons.Icons.PAUSE_ROUNDED
            self.player_play_btn.icon = ft.icons.Icons.PAUSE_ROUNDED
            self.song_label.value = song.get("title", "Sin título")
            self.player_title.value = song.get("title", "Sin título")
            self.player_artist.value = song.get("uploader", "")
            if thumb_path:
                self.player_art.content = ft.Image(src=thumb_path, fit="cover")
            else:
                self.player_art.content = ft.Container(bgcolor=SURFACE2)
            dur = song.get("duration", 0) or 0
            if dur > 0:
                self.player_seeker.max = dur * 1000
            self.page.update()
            if self._progress_task and not self._progress_task.done():
                self._progress_task.cancel()
            self._progress_task = asyncio.create_task(self._progress_loop())
        except Exception as e:
            self._log(f"Error reproduciendo descarga: {e}")
            self.song_label.value = "Error al reproducir"
            self.page.update()

    def _build_downloads_view(self):
        self.downloads_list = ft.ListView(spacing=6, padding=12, expand=True)
        self.downloads_view = ft.Container(
            content=ft.Column(
                [
                    ft.Container(height=16),
                    ft.Text("Descargas", size=20, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Container(height=12),
                    self.downloads_list,
                ],
                expand=True,
                spacing=0,
            ),
            bgcolor=BG,
            expand=True,
            padding=16,
        )

    def _build_settings_view(self):
        title = ft.Text("Ajustes", size=22, weight=ft.FontWeight.BOLD, color=TEXT)
        
        # Selector de tema
        theme_label = ft.Text("Tema claro/oscuro", size=16, weight=ft.FontWeight.W_500, color=TEXT)
        self.theme_switch = ft.Switch(
            value=self.user_settings.get("theme", "dark") == "light",
            on_change=self._on_theme_change,
            active_track_color=ACCENT,
            active_color=BG,
        )
        theme_row = ft.Row(
            [theme_label, ft.Container(expand=True), self.theme_switch],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        
        # Exportar música
        export_label = ft.Text("Exportar música", size=16, weight=ft.FontWeight.W_500, color=TEXT)
        export_desc = ft.Text(
            "Exporta las canciones descargadas a una carpeta de tu elección",
            size=12,
            color=TEXT_SEC,
        )
        
        # Campo para ruta de exportación
        self.export_path_input = ft.TextField(
            hint_text="Ruta donde guardar las canciones...",
            value=os.path.join(os.path.expanduser("~"), "Music", "Velqi"),
            expand=True,
            height=40,
            border_radius=8,
            filled=True,
            bgcolor=SURFACE,
            color=TEXT,
        )
        
        export_now_btn = ft.ElevatedButton(
            "Exportar ahora",
            on_click=self._on_export_now,
            bgcolor=ACCENT,
            color=BG,
            height=44,
            width=200,
        )
        
        self.settings_view = ft.Container(
            content=ft.Column(
                [
                    ft.Container(height=20),
                    title,
                    ft.Container(height=24),
                    theme_row,
                    ft.Container(height=24),
                    ft.Divider(height=1, color=SURFACE2),
                    ft.Container(height=24),
                    export_label,
                    ft.Container(height=4),
                    export_desc,
                    ft.Container(height=16),
                    ft.Text("Ruta de destino:", size=14, color=TEXT_SEC),
                    self.export_path_input,
                    ft.Container(height=20),
                    ft.Row([export_now_btn], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Container(expand=True),
                ],
                scroll=ft.ScrollMode.AUTO,
            ),
            bgcolor=BG,
            expand=True,
            padding=16,
        )

    # ---------- Playback ----------

    def _on_card_play(self, index):
        if index >= len(self.search_data):
            return
        song = self.search_data[index]
        self._current_song = song

        thumb_path = song.get("thumb")
        if thumb_path:
            self.player_thumb.content = ft.Image(src=thumb_path, fit="cover")
        else:
            self.player_thumb.content = ft.Container(bgcolor=SURFACE2)

        if self._progress_task and not self._progress_task.done():
            self._progress_task.cancel()
            self._progress_task = None

        self.miniplayer.visible = True
        self.play_btn.icon = ft.icons.Icons.PLAY_ARROW_ROUNDED
        self.page.update()
        
        # Verificar si la canción ya está descargada
        vid = song.get("id", "")
        downloaded_song = next((d for d in self.downloaded_songs if d.get("id") == vid), None)
        
        if downloaded_song:
            # Reproducir desde descargas
            asyncio.create_task(self._play_from_downloads(downloaded_song))
        else:
            # Descargar y reproducir
            self.song_label.value = "Cargando..."
            self.page.update()
            asyncio.create_task(self._do_play(song))

    async def _play_from_downloads(self, song):
        """Reproducir una canción ya descargada"""
        try:
            vid = song.get("id", "")
            filepath = None
            for fname in os.listdir(self.downloads_path):
                if fname.startswith(vid) and not fname.endswith(".json"):
                    filepath = os.path.join(self.downloads_path, fname)
                    break
            
            if not filepath:
                self._log(f"Archivo no encontrado para {song['title']}")
                self.song_label.value = "Archivo no encontrado"
                self.page.update()
                return
            
            self.song_label.value = song.get("title", "Sin título")
            self.player_title.value = song.get("title", "Sin título")
            self.player_artist.value = song.get("uploader", "")
            song_thumb = song.get("thumb")
            if song_thumb:
                self.player_art.content = ft.Image(src=song_thumb, fit="cover")
            else:
                self.player_art.content = ft.Container(bgcolor=SURFACE2)
            
            dur_ms = (song.get("duration", 0) or 0) * 1000
            self.audio.play(filepath, dur_ms)
            self.is_playing = True
            self.is_paused = False
            self.play_btn.icon = ft.icons.Icons.PAUSE_ROUNDED
            self.player_play_btn.icon = ft.icons.Icons.PAUSE_ROUNDED
            
            dur = song.get("duration", 0) or 0
            if dur > 0:
                self.player_seeker.max = dur * 1000
            
            self.page.update()
            
            if self._progress_task and not self._progress_task.done():
                self._progress_task.cancel()
            self._progress_task = asyncio.create_task(self._progress_loop())
            
        except Exception as e:
            self._log(f"Error reproduciendo descarga: {e}")
            self.song_label.value = "Error al reproducir"
            self.page.update()

    async def _do_play(self, song):
        try:
            video_id = song["id"]
            video_url = f"https://www.youtube.com/watch?v={video_id}"

            ydl_opts = {
                "format": "bestaudio[ext=m4a]/bestaudio*/best",
                "outtmpl": os.path.join(self.cache_path, f"{video_id}.%(ext)s"),
                "quiet": True,
                "no_warnings": True,
                "max_filesize": 50_000_000,
            }
            if self.cookies_file:
                ydl_opts["cookiefile"] = self.cookies_file
            if self.ffmpeg_available:
                ydl_opts["ffmpeg_location"] = self.ffmpeg_available
                ydl_opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                }]
            else:
                self._log("Sin ffmpeg - el audio puede no reproducirse")

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._run_ydl_download, video_url, ydl_opts)

            files = [f for f in os.listdir(self.cache_path) if f.startswith(video_id)]
            if not files:
                raise Exception("No se pudo descargar el audio")

            filepath = os.path.join(self.cache_path, files[0])
            dur_ms = (song.get("duration", 0) or 0) * 1000
            self.audio.play(filepath, dur_ms)
            self.is_playing = True
            self.is_paused = False
            self.play_btn.icon = ft.icons.Icons.PAUSE_ROUNDED
            self.player_play_btn.icon = ft.icons.Icons.PAUSE_ROUNDED
            self.song_label.value = song.get("title", "Sin título")
            self.player_title.value = song.get("title", "Sin título")
            self.player_artist.value = song.get("uploader", "")
            song_thumb = song.get("thumb")
            if song_thumb:
                self.player_art.content = ft.Image(src=song_thumb, fit="cover")
            else:
                self.player_art.content = ft.Container(bgcolor=SURFACE2)

            dur = song.get("duration", 0) or 0
            if dur > 0:
                self.player_seeker.max = dur * 1000
            else:
                try:
                    dur = self.audio.get_duration()
                    if dur > 0:
                        self.player_seeker.max = dur
                except Exception:
                    pass

            self.page.update()

            if self._progress_task and not self._progress_task.done():
                self._progress_task.cancel()
            self._progress_task = asyncio.create_task(self._progress_loop())
        except yt_dlp.utils.DownloadError as e:
            emsg = str(e)
            if "HTTP Error 403" in emsg or "Sign in" in emsg:
                self._show_error("YouTube bloqueo la descarga. Cookies expiradas.")
            else:
                self._show_error(f"Error de descarga: {emsg}")
            self.song_label.value = "Error al reproducir"
            self.page.update()
        except Exception as e:
            tb = traceback.format_exc()
            self._show_error(f"Error al reproducir: {e}")
            self.song_label.value = "Error al reproducir"
            self.page.update()

    def _run_ydl_download(self, url, opts):
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)

    async def _progress_loop(self):
        try:
            while self.is_playing or self.is_paused:
                if not self._seeking:
                    try:
                        pos = int(self.audio.get_pos() or 0)
                        dur = int(self.audio.get_duration() or 0)
                        if pos >= 0 and dur > 0:
                            self.player_seeker.max = dur
                            self.player_seeker.value = pos
                            m, s = pos // 60000, pos % 60000 // 1000
                            dm, ds = dur // 60000, dur % 60000 // 1000
                            self.player_time.value = f"{m}:{s:02d} / {dm}:{ds:02d}"
                        elif pos >= 0:
                            m, s = pos // 60000, pos % 60000 // 1000
                            self.player_time.value = f"{m}:{s:02d} / ?:??"
                        if dur > 0 and pos >= dur and self.is_playing:
                            self.audio.stop()
                            self.is_playing = False
                            self.is_paused = False
                            self.play_btn.icon = ft.icons.Icons.PLAY_ARROW_ROUNDED
                            self.player_play_btn.icon = ft.icons.Icons.PLAY_ARROW_ROUNDED
                            self.miniplayer.visible = False
                            self.page.update()
                            break
                        self.page.update()
                    except Exception:
                        pass
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass

    # ---------- Player controls ----------

    def _on_toggle_play(self, e):
        if not self.is_playing and not self.is_paused:
            return
        if self.is_playing:
            self.audio.pause()
            self.is_playing = False
            self.is_paused = True
            self.play_btn.icon = ft.icons.Icons.PLAY_ARROW_ROUNDED
            self.player_play_btn.icon = ft.icons.Icons.PLAY_ARROW_ROUNDED
            self.page.update()
        elif self.is_paused:
            self.audio.resume()
            self.is_playing = True
            self.is_paused = False
            self.play_btn.icon = ft.icons.Icons.PAUSE_ROUNDED
            self.player_play_btn.icon = ft.icons.Icons.PAUSE_ROUNDED
            self.page.update()
            if self._progress_task and not self._progress_task.done():
                self._progress_task.cancel()
            self._progress_task = asyncio.create_task(self._progress_loop())

    def _on_stop(self, e):
        self.audio.stop()
        self.is_playing = False
        self.is_paused = False
        self.play_btn.icon = ft.icons.Icons.PLAY_ARROW_ROUNDED
        self.player_play_btn.icon = ft.icons.Icons.PLAY_ARROW_ROUNDED
        self.player_seeker.value = 0
        self.player_time.value = "0:00 / 0:00"
        self.miniplayer.visible = False
        self._current_song = None
        if self._progress_task and not self._progress_task.done():
            self._progress_task.cancel()
            self._progress_task = None
        if not self.nav_bar.visible:
            self._close_player_view()
        self.page.update()

    def _on_seek_start(self, e):
        self._seeking = True

    def _on_seek_end(self, e):
        pos_ms = self.player_seeker.value
        if self.is_playing or self.is_paused:
            self.audio.seek(pos_ms)
        self._seeking = False

    def _on_volume_change(self, e):
        self._audio_vol = self.player_vol_slider.value / 100.0
        self.audio.set_volume(self._audio_vol)

    def _show_error(self, msg):
        self._log(f"ERROR: {msg}")
        self.search_status.value = msg
        self.search_status.visible = True
        self.page.update()


async def main(page: ft.Page):
    VelqiApp(page)


if __name__ == "__main__":
    ft.run(main=main)
