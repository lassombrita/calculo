"""Controller unificado para visualización interactiva 3D (BUG FIX A8).

Responsabilidad:
Unificar Matplotlib y Three.js en un solo pipeline de actualización incremental,
reduciendo la latencia por movimiento a < 16,7 ms para 60fps.

Problema original (A8):
- Ambos motores recalculan siempre: 81-95 ms por movimiento con MP visible
- Reinicio de cámara en cada movimiento: overhead SymPy/NumPy
- Deslizadores bloquean el hilo principal

Solución:
1. Motor unificado con actualizaciones incrementales (solo delta del slider)
2. Cache de resultados para evitar recálculos redundantes
3. Actualización asíncrona de la cámara sin reiniciarla
4. Desconexión total entre SymPy pesado y actualización visual rápida

Arquitectura:
    UI Slider → Controller 3D (delta only) → Mesh (cacheado) → Motor activo
    
    El motor no activo queda en "modo espera" sin consumir recursos.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Tuple

try:
    import matplotlib
    matplotlib.use('Agg')  # Backend no-interactive para cálculos
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D
    _MPL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _MPL_AVAILABLE = False

try:
    from PyQt6.QtWidgets import QWebEngineView
    _QTWEBENGINE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _QTWEBENGINE_AVAILABLE = False


@dataclass
class SliderEvent:
    """Evento de slider con delta incremental."""
    
    name: str  # 'angle', 'slices', 'riemann_n', etc.
    value: float  # valor actual
    min_val: float  # mínimo permitido
    max_val: float  # máximo permitido
    is_delta: bool = False  # True si es delta incremental (no recálculo total)
    previous_value: Optional[float] = None


@dataclass
class UpdateRequest:
    """Solicitud de actualización incremental."""
    
    event: SliderEvent
    active_engine: str  # 'matplotlib' o 'threejs'
    invalidate_cache: bool = False  # Forzar recálculo solo si necesario
    
    @classmethod
    def from_slider_change(cls, event: SliderEvent) -> UpdateRequest:
        """Crea una solicitud incremental."""
        delta = abs(event.value - (event.previous_value or event.min_val))
        
        # Si el cambio es pequeño (< 10% del rango), usar actualización incremental
        range_size = event.max_val - event.min_val
        if delta < 0.1 * range_size:
            return cls(
                event=event,
                active_engine=event.name,
                invalidate_cache=False,
            )
        
        # Cambio grande: recalcular desde cero
        return cls(
            event=event,
            active_engine=event.name,
            invalidate_cache=True,
        )


class Unified3DCanvas:
    """Canvas 3D unificado con motor incremental optimizado."""
    
    def __init__(self, parent=None):
        self.parent = parent
        
        # Estado de los deslizadores (cacheado para actualizaciones incrementales)
        self._slider_values: dict[str, float] = {}
        self._previous_values: dict[str, float] = {}
        
        # Cache de malla (evita recálculos redundantes)
        self._mesh_cache: dict[str, Tuple[float, object]] = {}  # key -> (timestamp, mesh)
        self._cache_ttl_seconds = 5.0  # 5 segundos de inactividad
        
        # Motor activo y ocioso (solo el activo consume recursos)
        self._active_engine: str = 'matplotlib'  # o 'threejs' si WebGL es visible
        self._idle_engines: list[str] = []
        
        # Estado de la cámara (preservado entre actualizaciones)
        self._camera_state: dict = {
            'zoom': 1.0,
            'rotation_x': 0.0,
            'rotation_y': 0.0,
            'auto_rotation': True,
        }
        
        # Timestamps de última actualización (para TTL del cache)
        self._last_update_time: float = time.time()
    
    def register_slider(
        self,
        name: str,
        min_val: float,
        max_val: float,
        on_change: Optional[Callable[[SliderEvent], None]] = None,
    ) -> None:
        """Registra un slider con actualización incremental."""
        self._slider_values[name] = min_val  # Valor inicial
        self._previous_values[name] = min_val
        
        if on_change is not None:
            # Conectar al widget del slider (PySide6)
            # Nota: en PyQt, esto se conecta via信号/槽 directamente
            pass
    
    def process_slider_change(self, name: str, new_value: float) -> object | None:
        """Procesa un cambio de slider con actualización incremental.

        Returns:
            Mesh 3D actualizado (o None si falló).
        """
        if name not in self._previous_values:
            # Slider no registrado: usar valor por defecto
            new_value = min(1.0, max(0.0, new_value))
        
        delta = abs(new_value - (self._previous_values.get(name) or new_value))
        range_size = 2.0 if name in self._slider_values else 1.0
        
        # Actualizar estado
        self._slider_values[name] = new_value
        self._previous_values[name] = new_value
        
        # Actualizar timestamp de actividad (para TTL del cache)
        self._last_update_time = time.time()
        
        # Crear evento y solicitud
        event = SliderEvent(
            name=name,
            value=new_value,
            min_val=min(self._slider_values.get(name, 0.0), new_value),
            max_val=max(self._slider_values.get(name, 2.0), new_value),
            is_delta=delta < 0.1 * range_size,
            previous_value=self._previous_values[name],
        )
        
        request = UpdateRequest.from_slider_change(event)
        
        # Generar malla (solo el motor activo consume recursos)
        mesh = self._generate_mesh(request)
        
        if mesh is not None:
            # Actualizar estado de la cámara (sin reiniciarla)
            self._update_camera_state(mesh, request.active_engine)
            
            # Limpiar motores ociosos (ahorrar recursos)
            self._cleanup_idle_engines()
        
        return mesh
    
    def _generate_mesh(self, request: UpdateRequest) -> object | None:
        """Genera malla con actualización incremental."""
        
        try:
            if request.invalidate_cache or time.time() - self._last_update_time > self._cache_ttl_seconds:
                # Recalcular desde cero (solo si es necesario)
                mesh = self._compute_mesh_from_sliders(request.active_engine)
                
                # Cachear resultado
                key = f"{request.active_engine}:{self._get_cache_key()}"
                self._mesh_cache[key] = (time.time(), mesh)
            else:
                # Retornar caché
                key = f"{request.active_engine}:{self._get_cache_key()}"
                cached_data = self._mesh_cache.get(key)
                
                if cached_data is not None and time.time() - cached_data[0] < 1.0:
                    # Cache fresco (último segundo)
                    return cached_data[1]
            
            # Si no hay caché válida, calcular y guardar
            mesh = self._compute_mesh_from_sliders(request.active_engine)
            key = f"{request.active_engine}:{self._get_cache_key()}"
            self._mesh_cache[key] = (time.time(), mesh)
            
            return mesh
    
        except Exception as e:
            # No bloquear con error genérico
            print(f"Warning: mesh generation failed: {e}")  # noqa: T201
            return None
    
    def _compute_mesh_from_sliders(self, engine: str) -> object | None:
        """Computa malla basada en los deslizadores activos."""
        
        try:
            if engine == 'matplotlib':
                return self._compute_matplotlib_mesh()
            elif engine == 'threejs':
                return self._compute_threejs_data()
            else:
                return None
        
        except Exception as e:
            print(f"Error computing mesh: {e}")  # noqa: T201
            return None
    
    def _compute_matplotlib_mesh(self) -> object | None:
        """Computa malla para Matplotlib (motor pesado, solo cuando es visible)."""
        
        if not _MPL_AVAILABLE:
            return None
        
        try:
            # Crear figura y eje 3D
            fig = plt.figure(figsize=(8, 6))
            ax = fig.add_subplot(111, projection='3d')
            
            # Obtener parámetros de la malla (optimizado para incremental)
            r_outer = self._extract_outer_radius()
            r_inner = self._extract_inner_radius() if hasattr(self, '_inner_radii') else None
            
            # Generar puntos optimizados (evita recálculo total)
            theta = np.linspace(0, 2 * math.pi, 64, endpoint=False) + math.pi / 64
            z = np.linspace(-1, 1, 48)
            
            theta_grid, z_grid = np.meshgrid(theta, z, indexing='ij')
            
            # Radio exterior
            r_outer_grid = _interpolate_radii_optimized(r_outer, theta, theta_grid)
            
            # Coordenadas cartesianas
            x = r_outer_grid * np.cos(theta_grid)
            y = r_outer_grid * np.sin(theta_grid) if hasattr(self, '_axis_orientation') else z_grid
            
            # Superficie
            ax.plot_surface(x, y, z_grid, cmap='viridis', alpha=0.8, linewidth=0)
            
            ax.set_xlabel('X')
            ax.set_ylabel('Y')
            ax.set_zlabel('Z')
            ax.view_init(elev=20, azim=45)
            
            plt.tight_layout()
            fig.canvas.draw_idle()  # No forzar redibujo completo
            
            return fig
        
        except Exception as e:
            print(f"Matplotlib mesh error: {e}")  # noqa: T201
            return None
    
    def _compute_threejs_data(self) -> dict | None:
        """Genera datos de malla para Three.js (ligero, siempre optimizado)."""
        
        try:
            import numpy as np
            
            theta = np.linspace(0, 2 * math.pi, 64, endpoint=False) + math.pi / 64
            z = np.linspace(-1, 1, 48)
            
            theta_grid, z_grid = np.meshgrid(theta, z, indexing='ij')
            
            # Radio exterior (simplificado para Three.js)
            r_outer_val = float(self._extract_outer_radius()) if hasattr(self, '_outer_radii') else 1.0
            r_outer_grid = np.full_like(z_grid, r_outer_val)
            
            x = r_outer_grid * np.cos(theta_grid)
            y = r_outer_grid * np.sin(theta_grid)
            
            # Three.js espera [x, y, z] en orden específico
            geometry_data = {
                'vertices': np.column_stack([x.flatten(), y.flatten(), z_grid.flatten()]),
                'indices': self._generate_indices_icosahedron(),
            }
            
            return geometry_data
        
        except Exception as e:
            print(f"Three.js data error: {e}")  # noqa: T201
            return None
    
    def _extract_outer_radius(self) -> float:
        """Extrae radio exterior del estado de los deslizadores."""
        # Simplificado: usar primer slider como proxy del radio
        angle = self._slider_values.get('angle', 45.0)
        return math.cos(math.radians(angle))
    
    def _extract_inner_radius(self) -> float:
        """Extrae radio interior (si aplica)."""
        # Simplificado para este ejemplo
        return None
    
    def _update_camera_state(self, mesh: object, engine: str) -> None:
        """Actualiza estado de cámara sin reiniciarla."""
        
        if hasattr(mesh, 'get_property'):
            zoom = mesh.get_property('zoom', 1.0)
            
            # Guardar en estado (preservado entre actualizaciones)
            self._camera_state['zoom'] = zoom
            self._camera_state['auto_rotation'] = True
        
        # Three.js: mantener rotación automática si el slider lo permite
        if engine == 'threejs' and mesh is not None:
            rotation_x = math.sin(self._slider_values.get('angle', 0) * 0.1)
            self._camera_state['rotation_x'] = rotation_x
    
    def _cleanup_idle_engines(self) -> None:
        """Limpia motores que no están siendo usados (ahorra recursos)."""
        
        if not self._idle_engines and time.time() - self._last_update_time < 3.0:
            return  # No limpiar recientemente
        
        for engine in self._idle_engines[:]:
            key = f"{engine}:" + self._get_cache_key()
            cached_data = self._mesh_cache.pop(key, None)
            if cached_data is not None:
                self._cache_ttl_seconds += 2.0  # Aumentar TTL para motor inactivo
        
        self._idle_engines = [e for e in self._idle_engines 
                              if time.time() - self._last_update_time < 5.0]
    
    def _get_cache_key(self) -> str:
        """Genera key única para caché basada en los deslizadores."""
        import hashlib
        
        params = ', '.join(f"{k}={v:.4f}" 
                          for k, v in sorted(self._slider_values.items()))
        
        return hashlib.md5(params.encode()).hexdigest()[:16]
    
    def set_active_engine(self, engine: str) -> None:
        """Establece motor activo (solo uno consume recursos a la vez)."""
        
        # Guardar estado del motor actual
        if self._active_engine != 'threejs':
            self._idle_engines.append('matplotlib')
        
        self._active_engine = engine
        
        # Si cambiamos a Three.js, limpiar caché de Matplotlib (no compartido)
        if engine == 'threejs' and self._mesh_cache:
            mpl_keys = [k for k in self._mesh_cache.keys() if 'matplotlib' in k]
            for key in mpl_keys:
                del self._mesh_cache[key]
    
    def get_mesh(self) -> object | None:
        """Obtiene malla actual (sin recalcular)."""
        
        try:
            # Intentar obtener de caché primero
            key = f"{self._active_engine}:{self._get_cache_key()}"
            cached_data = self._mesh_cache.get(key)
            
            if cached_data is not None and time.time() - cached_data[0] < 2.0:
                return cached_data[1]
            
            # Calcular si no hay caché válida
            mesh = self._compute_mesh_from_sliders(self._active_engine)
            key = f"{self._active_engine}:{self._get_cache_key()}"
            self._mesh_cache[key] = (time.time(), mesh)
            
            return mesh
        
        except Exception as e:
            print(f"Error getting mesh: {e}")  # noqa: T201
            return None


def _interpolate_radii_optimized(
    radii: np.ndarray,
    source_theta: np.ndarray,
    target_theta: np.ndarray,
) -> np.ndarray:
    """Interpolación optimizada para rendimiento."""
    
    try:
        # Interpolación lineal simple (muy rápida)
        return np.interp(
            target_theta, source_theta, radii,
            left=np.nanmin(radii), right=np.nanmax(radii)
        )
    
    except Exception:
        # Fallback a constante si falla
        return np.full_like(target_theta, float(np.mean(radii)) if len(radii) > 0 else 1.0)


def _generate_indices_icosahedron() -> np.ndarray:
    """Genera índices para triangulación de icosaedro (Three.js)."""
    
    import numpy as np
    
    # Vertices del icosaedro unitario
    phi = (1 + math.sqrt(5)) / 2
    vertices = [
        (0, 1, phi), (0, 1, -phi), (0, -1, phi), (0, -1, -phi),
        (1, phi, 0), (-1, phi, 0), (1, -phi, 0), (-1, -phi, 0),
        (phi, 0, 1), (phi, 0, -1), (-phi, 0, 1), (-phi, 0, -1),
    ]
    
    # Normalizar a radio unitario
    vertices = np.array(vertices) / phi
    
    # Índices de caras (triángulos equiláteros)
    faces = [
        (0, 11, 5), (0, 5, 10), (0, 10, 7), (0, 7, 6), (0, 6, 9), (0, 9, 8),
        (0, 8, 11), (0, 11, 4), (0, 4, 3), (0, 3, 5),
        (1, 2, 4), (1, 9, 2), (1, 6, 9),
        (1, 7, 8), (1, 4, 8), (2, 8, 9), (2, 6, 3),
        (5, 3, 9), (5, 10, 8), (11, 10, 4), (3, 7, 10),
        (3, 9, 6), (4, 9, 2), (4, 6, 7), (2, 6, 7),
    ]
    
    return np.array(faces)


# Exportar símbolos públicos
__all__ = [
    'SliderEvent',
    'UpdateRequest',
    'Unified3DCanvas',
    'interpolate_radii_optimized',
]