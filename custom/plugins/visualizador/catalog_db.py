# =============================================================================
# custom/plugins/visualizador/catalog_db.py
# =============================================================================
# Capa de acceso a datos: CSV de productos + imágenes del dataset.
# No depende de Qt — es Python puro.
# =============================================================================

import os
import re

import pandas as pd

# ── Columnas de interés ────────────────────────────────────────────────────────
_DISPLAY_ORDER = [
    "nombre_capturado",
    "sku_indice",
    "gramaje",
]
_SUPPORTED_EXT = (".jpg", ".jpeg", ".png", ".webp")

# Rutas fijas (relativas al directorio de trabajo, que es la raíz del proyecto)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # plugins/visualizador/
_PROJECT_ROOT = os.path.abspath(os.path.join(_BASE_DIR, "..", "..", ".."))  # raíz labelImg

CSV_PATH     = os.path.join(_PROJECT_ROOT, "visualizador nestle",
                            "captured_products_interno_1468.csv")
DATASET_DIR  = os.path.join(_PROJECT_ROOT, "visualizador nestle",
                            "dataset_catalogo_1468_skus")


# =============================================================================
class CatalogDB:
    """
    Carga el CSV una sola vez y ofrece métodos de búsqueda rápidos.
    Singleton liviano — instanciar una vez y compartir.
    """

    def __init__(self, csv_path: str = CSV_PATH, dataset_dir: str = DATASET_DIR):
        self.csv_path    = csv_path
        self.dataset_dir = dataset_dir
        self._df: pd.DataFrame | None = None
        self._load()

    # ── Carga ─────────────────────────────────────────────────────────────────
    def _load(self) -> None:
        if not os.path.exists(self.csv_path):
            print(f"[Visualizador] CSV no encontrado: {self.csv_path}")
            self._df = pd.DataFrame()
            return
        try:
            self._df = pd.read_csv(self.csv_path, dtype=str).fillna("")
            # Asegurar columnas requeridas
            for col in ("sku_indice", "upc_version", "nombre_capturado", "gramaje"):
                if col not in self._df.columns:
                    self._df[col] = ""
            print(f"[Visualizador] CSV cargado: {len(self._df)} productos")
        except Exception as e:
            print(f"[Visualizador] Error leyendo CSV: {e}")
            self._df = pd.DataFrame()

    @property
    def df(self) -> pd.DataFrame:
        return self._df if self._df is not None else pd.DataFrame()

    # ── Utilidades de parseo ───────────────────────────────────────────────────
    @staticmethod
    def parse_sku_indice(label_text: str) -> str:
        """
        Extrae el sku_indice de la etiqueta de una caja anotada.

        Formatos soportados:
          - "219_36900100..."          → "219"
          - "219_36900...,Nombre..."   → "219"
          - "219,Nombre..."            → "219"
          - "219"                      → "219"
          - "7506475117951_0"          → el primer segmento numérico largo
        """
        if not label_text:
            return ""
        # Tomar solo la parte antes de la coma (si hay nombre al final)
        part = label_text.split(",")[0].strip()
        # Tomar solo la parte antes del primer guion bajo
        part = part.split("_")[0].strip()
        # Devolver solo si es numérico
        return part if part.isdigit() else ""

    # ── Búsquedas ─────────────────────────────────────────────────────────────
    def find_by_sku_indice(self, sku_indice: str) -> pd.DataFrame:
        """Busca filas exactas por sku_indice."""
        if self.df.empty or not sku_indice:
            return pd.DataFrame()
        return self.df[self.df["sku_indice"].str.strip() == str(sku_indice).strip()]

    def find_by_upc_version(self, upc_version: str) -> pd.DataFrame:
        """Busca filas exactas por upc_version (p.ej. '7506475117975_0')."""
        if self.df.empty or not upc_version:
            return pd.DataFrame()
        return self.df[self.df["upc_version"].str.strip() == str(upc_version).strip()]

    def find_by_label(self, label_text: str) -> pd.DataFrame:
        """
        Infiere el sku_indice desde el texto de la etiqueta y devuelve filas.
        """
        sku = self.parse_sku_indice(label_text)
        if sku:
            rows = self.find_by_sku_indice(sku)
            if not rows.empty:
                return rows
        # Fallback: buscar el texto exacto como upc_version
        return self.find_by_upc_version(label_text.strip())

    def search(self, query: str) -> pd.DataFrame:
        """
        Búsqueda flexible: sku_indice exacto, UPC parcial o palabras clave
        en nombre_capturado.  Devuelve hasta 200 filas.
        """
        if self.df.empty or not query.strip():
            return pd.DataFrame()

        q = query.strip()

        # Intento 1: sku_indice exacto
        if q.isdigit():
            r = self.find_by_sku_indice(q)
            if not r.empty:
                return r.head(200)

        # Intento 2: contiene en upc_version o upc_capturado
        mask_upc = (
            self.df["upc_version"].str.contains(q, case=False, na=False) |
            self.df.get("upc_capturado", pd.Series(dtype=str)).str.contains(
                q, case=False, na=False)
        )

        # Intento 3: contiene en nombre_capturado (todas las palabras)
        mask_name = pd.Series(True, index=self.df.index)
        for word in q.lower().split():
            mask_name &= self.df["nombre_capturado"].str.lower().str.contains(
                word, na=False)

        combined = self.df[mask_upc | mask_name]
        return combined.head(200)

    # ── Imágenes ───────────────────────────────────────────────────────────────
    def get_images(self, upc_version: str, max_images: int = 10) -> list[str]:
        """Devuelve lista de rutas de imagen para un upc_version."""
        folder = os.path.join(self.dataset_dir, str(upc_version))
        if not os.path.isdir(folder):
            return []
        imgs = sorted(
            f for f in os.listdir(folder)
            if os.path.splitext(f.lower())[1] in _SUPPORTED_EXT
        )
        return [os.path.join(folder, f) for f in imgs[:max_images]]

    def get_first_image(self, upc_version: str) -> str | None:
        """Primera imagen del producto, o None."""
        imgs = self.get_images(upc_version, max_images=1)
        return imgs[0] if imgs else None

    def get_images_for_label(self, label_text: str, max_images: int = 10) -> list[str]:
        """Obtiene imágenes a partir del texto de la etiqueta de una caja."""
        rows = self.find_by_label(label_text)
        if rows.empty:
            return []
        upc = rows.iloc[0].get("upc_version", "")
        return self.get_images(upc, max_images)

    # ── Orden de columnas para mostrar ────────────────────────────────────────
    def ordered_record(self, row: pd.Series) -> list[tuple[str, str]]:
        """
        Devuelve lista de (columna, valor) con el orden preferido:
        nombre_capturado, sku_indice, gramaje, luego el resto.
        """
        all_cols = list(row.index)
        priority = [c for c in _DISPLAY_ORDER if c in all_cols]
        rest     = [c for c in all_cols if c not in priority]
        return [(c, str(row.get(c, ""))) for c in priority + rest]

    # ── Edición ───────────────────────────────────────────────────────────────
    def update_field(self, row_index: int, column: str, value: str) -> bool:
        """
        Modifica una celda en el DataFrame y guarda el CSV.
        Devuelve True si tuvo éxito.
        """
        if self.df.empty:
            return False
        try:
            self._df.at[row_index, column] = value
            self._df.to_csv(self.csv_path, index=False)
            return True
        except Exception as e:
            print(f"[Visualizador] Error guardando CSV: {e}")
            return False

    def reload(self) -> None:
        """Recarga el CSV desde disco."""
        self._load()
