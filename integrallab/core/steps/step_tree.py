"""
Árbol de pasos interactivos tipo Photomath.

Módulo del dominio (capa pura) que define la estructura jerárquica para mostrar
desglosos paso a paso de soluciones matemáticas, con soporte para fórmulas renderizadas
y navegación interactiva (clíc en ecuaciones para expandir/colapsar sub-pasos).

Arquitectura:
  - PasoBase: Abstracción base para cualquier tipo de paso.
  - FormulaStep: Paso con fórmula renderizada (LaTeX a PNG o MathJax).
  - TextStep: Paso con explicación textual.
  - StepTree: Árbol jerárquico con nodos raíz, hijos y estado expandible/colapsable.

Separación de capas: Este módulo NO importa PySide6 ni usa SymPy directamente.
"""

from __future__ import annotations
import base64
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any, Union


class StepType(Enum):
    """Tipos de nodos en el árbol de pasos."""
    ROOT = "root"           # Nodo raíz (expansible)
    FORMULA = "formula"     # Fórmula renderizada con clic para expandir hijos
    TEXT = "text"           # Texto plano o Markdown
    RESULT = "result"       # Resultado final


class StepExpandState(Enum):
    """Estados de expansión de un nodo."""
    CLOSED = "closed"       # Colapsado (hijos ocultos)
    EXPANDED = "expanded"   # Expandido (hijos visibles)
    LEAF = "leaf"           # Hoja (sin hijos, siempre visible)


@dataclass
class FormulaMetadata:
    """Metadatos de una fórmula renderizada."""
    latex: str                          # Fórmula en LaTeX
    image_base64: Optional[str] = None  # PNG offline (MathText) o null para MathJax
    width_px: int = 400                 # Ancho original en px
    height_px: int = auto()             # Auto si no proporcionado


def auto() -> Any:
    """Placeholder para evitar syntax error en dataclass. Usar None explícito."""
    return None


@dataclass
class StepBase:
    """Abstracción base para cualquier paso del árbol."""
    step_id: str                      # ID único (UUID v4 recomendado)
    step_type: StepType               # Tipo de nodo
    title: str                        # Título corto del paso
    description: Optional[str] = None # Descripción detallada (Markdown/HTML)
    order: int = 0                    # Orden de presentación en UI

    def to_dict(self) -> Dict[str, Any]:
        """Serialización para JSON/QWebChannel."""
        return {
            "step_id": self.step_id,
            "step_type": self.step_type.value,
            "title": self.title,
            "description": self.description,
            "order": self.order,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StepBase:
        """Deserialización de JSON/QWebChannel."""
        step_type = StepType(data["step_type"])
        if step_type == StepType.FORMULA:
            return FormulaStep.from_dict(data)
        elif step_type == StepType.TEXT:
            return TextStep.from_dict(data)
        else:  # ROOT o RESULT
            return cls(**data)


@dataclass
class FormulaStep(StepBase):
    """Paso con fórmula renderizada (tipo Photomath)."""
    formula_metadata: FormulaMetadata
    children: List[StepBase] = field(default_factory=list)
    is_expanded: bool = False          # Estado de expansión (False=colapsado)

    def to_dict(self) -> Dict[str, Any]:
        """Serialización para JSON/QWebChannel."""
        data = super().to_dict()
        data.update({
            "children": [c.to_dict() for c in self.children],
            "is_expanded": self.is_expanded,
            "formula_metadata": asdict(self.formula_metadata),
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FormulaStep:
        """Deserialización de JSON/QWebChannel."""
        # Extraer step_id y orden padre si existen en datos planos
        meta = data.get("formula_metadata", {})
        if "is_expanded" in data and isinstance(data["is_expanded"], str):
            is_expanded = data["is_expanded"] == "true"
        else:
            is_expanded = data.get("is_expanded", False)
        return cls(
            step_id=data.get("step_id", ""),
            step_type=StepType.FORMULA,
            title=data.get("title", ""),
            description=data.get("description"),
            order=data.get("order", 0),
            formula_metadata=FormulaMetadata(**meta),
            children=[cls.from_dict(c) for c in data.get("children", [])],
            is_expanded=is_expanded,
        )

    def to_json(self) -> str:
        """Serialización compacta para QWebChannel."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> 'FormulaStep':
        """Deserialización de JSON compacto."""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class TextStep(StepBase):
    """Paso con texto plano o Markdown."""
    content: str                      # Contenido textual principal

    def to_dict(self) -> Dict[str, Any]:
        """Serialización para JSON/QWebChannel."""
        return {
            "step_id": self.step_id,
            "step_type": self.step_type.value,
            "title": self.title,
            "description": self.content,  # TextStep usa content como descripción principal
            "order": self.order,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TextStep:
        """Deserialización de JSON/QWebChannel."""
        return cls(
            step_id=data.get("step_id", ""),
            step_type=StepType.TEXT,
            title=data.get("title", ""),
            description=data.get("description"),
            order=data.get("order", 0),
            content=data.get("description", ""),
        )

    def to_json(self) -> str:
        """Serialización compacta para QWebChannel."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> 'TextStep':
        """Deserialización de JSON compacto."""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class StepNode:
    """Nodo raíz del árbol de pasos (expandible)."""
    step_id: str
    children: List[StepBase] = field(default_factory=list)
    is_expanded: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialización completa del árbol para QWebChannel."""
        return {
            "step_id": self.step_id,
            "children": [c.to_dict() for c in self.children],
            "is_expanded": self.is_expanded,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StepNode':
        """Deserialización completa del árbol."""
        return cls(
            step_id=data.get("step_id", ""),
            children=[FormulaStep.from_dict(c) if c["step_type"] == "formula"
                      else (TextStep.from_dict(c) if c["step_type"] == "text" else None)
                      for c in data.get("children", [])],
            is_expanded=data.get("is_expanded", False),
        )

    def to_json(self) -> str:
        """Serialización compacta para QWebChannel."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> 'StepNode':
        """Deserialización compacta de QWebChannel."""
        data = json.loads(json_str)
        return cls.from_dict(data)


class StepTree:
    """
    Árbol jerárquico de pasos para visualización interactiva tipo Photomath.

    Arquitectura:
      - Nodo raíz (expandible): Contiene fórmula inicial (ej: ∫ f(x) dx)
      - Sub-pasos (clíc expandible): Desglose paso a paso
      - Hojas: Resultados finales o explicaciones textuales

    Uso con QWebChannel:
        tree = StepTree(
            step_id="integration-1",
            children=[FormulaStep(...), TextStep(...)],
            is_expanded=False
        )
        json_str = tree.to_json()
        # Enviar a QWebChannel para renderizar en WebEngineView con MathJax

    Métodos:
        - expand(step_id: str) -> bool: Expande el nodo identificado por step_id.
        - collapse(step_id: str) -> bool: Colapsa el nodo.
        - get_all_steps() -> List[StepBase]: Lista plana de todos los pasos.
        - find_step(step_id: str) -> Optional[StepBase]: Busca paso por ID.

    Separación de capas: Este módulo es puro (sin PySide6, sin SymPy directo).
    """

    def __init__(self, root: Union[StepNode, Dict[str, Any], str]):
        """Inicializa el árbol con nodo raíz."""
        if isinstance(root, StepNode):
            self.root = root
        elif isinstance(root, dict):
            self.root = StepNode.from_dict(root)
        else:  # string JSON
            self.root = StepNode.from_json(root)

    def expand(self, step_id: str) -> bool:
        """Expande el nodo identificado por step_id y todos sus padres."""
        current = self._find_node(step_id)
        if current is None or not isinstance(current, StepNode):
            return False
        # Expandir hacia arriba hasta raíz para mantener estructura jerárquica
        while current.parent is not None:
            if not current.parent.is_expanded:
                current.parent.is_expanded = True
            current = current.parent
        current.is_expanded = True
        return True

    def collapse(self, step_id: str) -> bool:
        """Colapsa el nodo identificado por step_id (pero no padres)."""
        current = self._find_node(step_id)
        if current is None or not isinstance(current, StepNode):
            return False
        current.is_expanded = False
        return True

    def _find_node(self, step_id: str) -> Optional[StepBase]:
        """Busca nodo por step_id (recursivo)."""
        if self.root.step_id == step_id:
            return self.root
        for child in self.root.children:
            # Buscar en Fórmula o TextStep (que pueden tener hijos si es expandible)
            if isinstance(child, FormulaStep) and child.is_expanded:
                for grandchild in child.children:
                    result = self._find_node_in_step(grandchild, step_id)
                    if result is not None:
                        return result
            elif isinstance(child, TextStep):
                if child.step_id == step_id:
                    return child
        return None

    def _find_node_in_step(self, node: StepBase, target_id: str) -> Optional[StepBase]:
        """Buscar recursivamente en sub-nodos."""
        if node.step_id == target_id:
            return node
        if isinstance(node, FormulaStep) and node.is_expanded:
            for child in node.children:
                result = self._find_node_in_step(child, target_id)
                if result is not None:
                    return result
        return None

    def get_all_steps(self) -> List[StepBase]:
        """Devuelve lista plana de todos los pasos del árbol."""
        result: List[StepBase] = []
        self._collect_steps(self.root, result)
        return result

    def _collect_steps(self, node: StepBase, container: List[StepBase]):
        """Recolección recursiva de todos los pasos."""
        container.append(node)
        if isinstance(node, FormulaStep) and node.is_expanded:
            for child in node.children:
                self._collect_steps(child, container)

    def find_step(self, step_id: str) -> Optional[StepBase]:
        """Devuelve el paso encontrado por ID o None."""
        return self._find_node(step_id)

    def to_json(self) -> str:
        """Serialización completa del árbol para QWebChannel."""
        return json.dumps(self.root.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> 'StepTree':
        """Deserialización completa desde JSON de QWebChannel."""
        data = json.loads(json_str)
        return cls(data)

    def to_dict(self) -> Dict[str, Any]:
        """Devuelve representación en dict para debugging/introspección."""
        return self.root.to_dict()


def create_sample_photomath_tree() -> StepTree:
    """
    Crea un ejemplo de árbol tipo Photomath para integral.

    Ejemplo visual esperado:
      [√] ∫ x² sin(x) dx (clíc → expandir)
        ├─ Paso 1: Usar integración por partes
        ├─ Paso 2: Identificar u = sin(x), dv = x² dx
        ├─ Paso 3: Calcular du = cos(x)dx, v = x³/3
        ├─ Paso 4: Aplicar fórmula ∫ u dv = uv - ∫ v du
        └─ Paso 5: Simplificar resultado final

    Retorna árbol con nodos raíz y sub-pasos.
    """
    root = StepNode(
        step_id="root-integration",
        children=[],
        is_expanded=False,
    )

    # Paso inicial: fórmula de la integral original
    formula_step_1 = FormulaStep(
        step_id="step-1-original",
        step_type=StepType.FORMULA,
        title="Integral original",
        description=None,  # Fórmula renderizada en imagen LaTeX
        order=0,
        formula_metadata=FormulaMetadata(
            latex=r"\int x^2 \sin(x) \, dx",
            image_base64=None,  # QWebChannel usará MathJax si no hay PNG
            width_px=500,
            height_px=None,
        ),
        children=[],
        is_expanded=False,
    )

    root.children.append(formula_step_1)

    # Sub-pasos para integración por partes
    text_step_1 = TextStep(
        step_id="step-2-strategy",
        step_type=StepType.TEXT,
        title="Estrategia",
        description="[R(x)]²: Usaremos integración por partes.\n"
                    "Fórmula: $$\\int u \\, dv = uv - \\int v \\, du$$",
        order=0,
        content="[R(x)]²: Usamos integración por partes con fórmula estándar.",
    )

    formula_step_2 = FormulaStep(
        step_id="step-3-setup",
        step_type=StepType.FORMULA,
        title="Identificación de u y dv",
        description=None,
        order=0,
        formula_metadata=FormulaMetadata(
            latex=r"u = \\sin(x), \\\\\n dv = x^2 \\, dx\\\\\n\\Rightarrow du = \\cos(x) \\, dx, \\\\\n v = \\frac{x^3}{3}",
            image_base64=None,
            width_px=500,
            height_px=None,
        ),
        children=[],
        is_expanded=False,
    )

    text_step_2 = TextStep(
        step_id="step-4-application",
        step_type=StepType.TEXT,
        title="Aplicar fórmula de integración por partes",
        description="$uv - \\int v du$",
        order=0,
        content="Aplicamos la fórmula: $\\int u dv = uv - \\int v du$.",
    )

    formula_step_3 = FormulaStep(
        step_id="step-5-result",
        step_type=StepType.FORMULA,
        title="Resultado final",
        description=None,
        order=0,
        formula_metadata=FormulaMetadata(
            latex=r"-\\frac{x^3}{3}\\cos(x) + \\int \\frac{x^3}{3}\\cos(x) \\, dx",
            image_base64=None,
            width_px=500,
            height_px=None,
        ),
        children=[],
        is_expanded=False,
    )

    formula_step_1.children = [formula_step_2, text_step_1]
    formula_step_2.children = [formula_step_3, text_step_2]

    return StepTree(root=root)


if __name__ == "__main__":
    # Demo rápida (para tests locales)
    tree = create_sample_photomath_tree()
    print("Árbol de pasos tipo Photomath creado:")
    print(json.dumps(tree.to_dict(), indent=2))
