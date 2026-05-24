#!/usr/bin/env python3
"""
VELQI LITE - App mínima CORREGIDA
"""

import flet as ft
import yt_dlp
import os
import threading
from pathlib import Path

class VelqiLite:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Velqi Lite"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = "#000000"
        self.page.padding = 0
        
        # Directorio descargas
        self.downloads_dir = Path("/storage/emulated/0/Download/Velqi")
        
        # UI mínima
        self.search_input = ft.TextField(
            hint_text="Buscar canción...",
            expand=True,
            border_radius=20,
            filled=True,
            bgcolor="#1a1a1a",
            color="white"
        )
        
        self.search_btn = ft.ElevatedButton(
            "🔍 Buscar",
            on_click=self.search,
            bgcolor="#6200ee",
            color="white"
        )
        
        self.results = ft.ListView(expand=True, spacing=10)
        
        self.status = ft.Text("Listo", color="gray", size=12)
        
        # Layout simple
        self.page.add(
            ft.Column([
                # Barra búsqueda
                ft.Container(
                    content=ft.Row([
                        self.search_input,
                        self.search_btn
                    ]),
                    padding=20
                ),
                
                # Resultados
                ft.Container(
                    content=self.results,
                    expand=True,
                    padding=10
                ),
                
                # Status
                ft.Container(
                    content=self.status,
                    padding=10
                )
            ])
        )
    
    def search(self, e):
        query = self.search_input.value.strip()
        if not query:
            self.status.value = "Escribe algo"
            self.page.update()
            return
        
        self.status.value = "Buscando..."
        self.page.update()
        
        # Limpiar resultados
        self.results.controls.clear()
        self.page.update()
        
        # Buscar en hilo
        threading.Thread(
            target=self._do_search,
            args=(query,),
            daemon=True
        ).start()
    
    def _do_search(self, query):
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch5:{query}", download=False)
                entries = info.get('entries', [])
                
                for entry in entries:
                    if entry:
                        self._add_result(entry)
                
                self.status.value = f"Encontrados: {len(entries)}"
                self.page.update()
                
        except Exception as e:
            self.status.value = f"Error: {str(e)[:30]}"
            self.page.update()
    
    def _add_result(self, entry):
        video_id = entry.get('id', '')
        title = entry.get('title', 'Sin título')[:40]
        uploader = entry.get('uploader', 'Desconocido')[:20]
        
        # Card simple
        card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text(title, size=14, weight="bold"),
                    ft.Text(uploader, size=12, color="gray"),
                    ft.ElevatedButton(
                        "⬇ Descargar",
                        on_click=lambda e, vid=video_id: self._download(vid),
                        bgcolor="#00c853",
                        color="white"
                    )
                ]),
                padding=10
            )
        )
        
        self.results.controls.append(card)
        self.page.update()
    
    def _download(self, video_id):
        self.status.value = "Descargando..."
        self.page.update()
        
        threading.Thread(
            target=self._do_download,
            args=(video_id,),
            daemon=True
        ).start()
    
    def _do_download(self, video_id):
        try:
            url = f"https://youtube.com/watch?v={video_id}"
            
            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio',
                'outtmpl': '%(title)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            self.status.value = "✅ Descargado"
            self.page.update()
            
        except Exception as e:
            self.status.value = f"❌ Error"
            self.page.update()

def main(page: ft.Page):
    VelqiLite(page)

if __name__ == "__main__":
    ft.run(main)