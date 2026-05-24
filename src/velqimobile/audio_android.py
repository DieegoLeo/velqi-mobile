"""
Reproductor de audio optimizado para Android
Versión simplificada sin pygame
"""

import os
import time
import threading
from typing import Optional, Callable

class AndroidAudioPlayer:
    """
    Reproductor de audio para Android usando MediaPlayer nativo
    Versión simplificada y robusta
    """
    
    def __init__(self):
        self.player = None
        self.is_playing = False
        self.is_paused = False
        self.current_file = None
        self.duration = 0
        self.position = 0
        self.volume = 0.8
        self._android_available = False
        self._position_thread = None
        self._stop_thread = False
        
        self._init_android()
    
    def _init_android(self):
        """Inicializar Android MediaPlayer si está disponible"""
        try:
            from java import jclass
            # Verificar que estamos en Android
            jclass("android.os.Build")
            self.MediaPlayer = jclass("android.media.MediaPlayer")
            self._android_available = True
            print("✅ MediaPlayer de Android disponible")
        except Exception as e:
            print(f"⚠ No se pudo cargar MediaPlayer de Android: {e}")
            self._android_available = False
    
    def load(self, filepath: str) -> bool:
        """Cargar archivo de audio"""
        if not os.path.exists(filepath):
            print(f"❌ Archivo no encontrado: {filepath}")
            return False
        
        self.stop()
        self.current_file = filepath
        
        if self._android_available:
            try:
                self.player = self.MediaPlayer()
                self.player.setDataSource(filepath)
                self.player.prepare()
                self.duration = self.player.getDuration()
                print(f"✅ Audio cargado: {os.path.basename(filepath)}")
                print(f"   Duración: {self.duration}ms")
                return True
            except Exception as e:
                print(f"❌ Error al cargar audio en Android: {e}")
                self.player = None
                return False
        else:
            # Modo simulado para testing en desktop
            print(f"⚠ Modo simulado (no Android): {os.path.basename(filepath)}")
            self.duration = 180000  # 3 minutos simulado
            self.player = True
            return True
    
    def play(self) -> bool:
        """Reproducir audio"""
        if not self.player:
            print("❌ No hay audio cargado")
            return False
        
        if self._android_available:
            try:
                self.player.start()
                self.is_playing = True
                self.is_paused = False
                self._start_position_tracking()
                print("▶ Reproduciendo...")
                return True
            except Exception as e:
                print(f"❌ Error al reproducir: {e}")
                return False
        else:
            # Modo simulado
            print("▶ Reproduciendo (simulado)...")
            self.is_playing = True
            self.is_paused = False
            return True
    
    def pause(self) -> bool:
        """Pausar reproducción"""
        if not self.is_playing:
            return False
        
        if self._android_available and self.player:
            try:
                self.player.pause()
                self.is_playing = False
                self.is_paused = True
                print("⏸ Pausado")
                return True
            except Exception as e:
                print(f"❌ Error al pausar: {e}")
                return False
        else:
            # Modo simulado
            print("⏸ Pausado (simulado)")
            self.is_playing = False
            self.is_paused = True
            return True
    
    def resume(self) -> bool:
        """Reanudar reproducción"""
        if not self.is_paused:
            return False
        
        if self._android_available and self.player:
            try:
                self.player.start()
                self.is_playing = True
                self.is_paused = False
                print("▶ Reanudando...")
                return True
            except Exception as e:
                print(f"❌ Error al reanudar: {e}")
                return False
        else:
            # Modo simulado
            print("▶ Reanudando (simulado)")
            self.is_playing = True
            self.is_paused = False
            return True
    
    def stop(self) -> bool:
        """Detener reproducción"""
        self._stop_position_tracking()
        
        if self._android_available and self.player:
            try:
                self.player.stop()
                self.player.release()
                self.player = None
                self.is_playing = False
                self.is_paused = False
                self.position = 0
                print("⏹ Detenido")
                return True
            except Exception as e:
                print(f"❌ Error al detener: {e}")
                return False
        else:
            # Modo simulado
            print("⏹ Detenido (simulado)")
            self.player = None
            self.is_playing = False
            self.is_paused = False
            self.position = 0
            return True
    
    def seek(self, position_ms: int) -> bool:
        """Buscar posición específica"""
        if not self.player:
            return False
        
        if self._android_available:
            try:
                self.player.seekTo(position_ms)
                self.position = position_ms
                print(f"↕ Buscando a {position_ms}ms")
                return True
            except Exception as e:
                print(f"❌ Error al buscar: {e}")
                return False
        else:
            # Modo simulado
            self.position = min(position_ms, self.duration)
            print(f"↕ Buscando a {position_ms}ms (simulado)")
            return True
    
    def set_volume(self, volume: float) -> bool:
        """Ajustar volumen (0.0 a 1.0)"""
        self.volume = max(0.0, min(1.0, volume))
        
        if self._android_available and self.player:
            try:
                self.player.setVolume(self.volume, self.volume)
                print(f"🔊 Volumen: {int(self.volume * 100)}%")
                return True
            except Exception as e:
                print(f"❌ Error al ajustar volumen: {e}")
                return False
        else:
            print(f"🔊 Volumen: {int(self.volume * 100)}% (simulado)")
            return True
    
    def get_position(self) -> int:
        """Obtener posición actual"""
        if self._android_available and self.player:
            try:
                self.position = self.player.getCurrentPosition()
                return self.position
            except:
                return self.position
        else:
            # Simular avance en modo desktop
            if self.is_playing and not self.is_paused:
                self.position = min(self.position + 1000, self.duration)
            return self.position
    
    def get_duration(self) -> int:
        """Obtener duración total"""
        return self.duration
    
    def _start_position_tracking(self):
        """Iniciar hilo para trackear posición (solo para UI)"""
        if self._position_thread:
            self._stop_position_tracking()
        
        self._stop_thread = False
        self._position_thread = threading.Thread(target=self._track_position, daemon=True)
        self._position_thread.start()
    
    def _track_position(self):
        """Hilo para actualizar posición periódicamente"""
        while not self._stop_thread and self.is_playing:
            self.get_position()
            time.sleep(0.5)
    
    def _stop_position_tracking(self):
        """Detener hilo de tracking"""
        self._stop_thread = True
        if self._position_thread:
            self._position_thread.join(timeout=1)
            self._position_thread = None
    
    def cleanup(self):
        """Limpiar recursos"""
        self.stop()
        self._stop_position_tracking()


# Función de conveniencia para crear instancia
def create_audio_player():
    """Crear instancia del reproductor de audio"""
    return AndroidAudioPlayer()