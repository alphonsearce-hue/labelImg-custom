# =============================================================================
# custom/plugins/visualizador/catalog_db.py
# =============================================================================

import os
import re
import shutil
import pandas as pd

_DISPLAY_ORDER = [
    "nombre_capturado",
    "sku_indice",
    "gramaje",
    "product category",
    "cluster_id",
]
_SUPPORTED_EXT = (".jpg", ".jpeg", ".png", ".webp")

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_BASE_DIR, "..", "..", ".."))

CSV_PATH     = os.path.join(_PROJECT_ROOT, "visualizador nestle",
                            "captured_products_master.csv")
DATASET_DIR  = os.path.join(_PROJECT_ROOT, "visualizador nestle",
                            "dataset_catalogo")


class CatalogDB:
    """Carga el CSV una sola vez y ofrece métodos de búsqueda y actualización."""

    def __init__(self, csv_path: str = CSV_PATH, dataset_dir: str = DATASET_DIR):
        self.csv_path    = csv_path
        self.dataset_dir = dataset_dir
        self._df: pd.DataFrame | None = None
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.csv_path):
            print(f"[Visualizador] CSV no encontrado: {self.csv_path}")
            self._df = pd.DataFrame()
            return
        try:
            self._df = pd.read_csv(self.csv_path, dtype=str).fillna("")
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

    @staticmethod
    def parse_sku_indice(label_text: str) -> str:
        if not label_text:
            return ""
        part = label_text.split(",")[0].strip()
        part = part.split("_")[0].strip()
        return part if part.isdigit() else ""

    def find_by_sku_indice(self, sku_indice: str) -> pd.DataFrame:
        if self.df.empty or not sku_indice:
            return pd.DataFrame()
        return self.df[self.df["sku_indice"].str.strip() == str(sku_indice).strip()]

    def find_by_upc_version(self, upc_version: str) -> pd.DataFrame:
        if self.df.empty or not upc_version:
            return pd.DataFrame()
        return self.df[self.df["upc_version"].str.strip() == str(upc_version).strip()]

    def find_by_label(self, label_text: str) -> pd.DataFrame:
        sku = self.parse_sku_indice(label_text)
        if sku:
            rows = self.find_by_sku_indice(sku)
            if not rows.empty:
                return rows
        return self.find_by_upc_version(label_text.strip())

    def search(self, query: str) -> pd.DataFrame:
        if self.df.empty or not query.strip():
            return pd.DataFrame()

        q = query.strip()

        if q.isdigit():
            r = self.find_by_sku_indice(q)
            if not r.empty:
                return r.head(200)

        mask_upc = (
            self.df["upc_version"].str.contains(q, case=False, na=False) |
            self.df.get("upc_capturado", pd.Series(dtype=str)).str.contains(q, case=False, na=False)
        )

        mask_name = pd.Series(True, index=self.df.index)
        for word in q.lower().split():
            mask_name &= self.df["nombre_capturado"].str.lower().str.contains(word, na=False)

        combined = self.df[mask_upc | mask_name]
        return combined.head(200)

    def get_images(self, upc_version: str, max_images: int = 10) -> list[str]:
        folder = os.path.join(self.dataset_dir, str(upc_version))
        if not os.path.isdir(folder):
            return []
        imgs = sorted(
            f for f in os.listdir(folder)
            if os.path.splitext(f.lower())[1] in _SUPPORTED_EXT
        )
        return [os.path.join(folder, f) for f in imgs[:max_images]]

    def get_first_image(self, upc_version: str) -> str | None:
        imgs = self.get_images(upc_version, max_images=1)
        return imgs[0] if imgs else None

    def get_images_for_label(self, label_text: str, max_images: int = 10) -> list[str]:
        rows = self.find_by_label(label_text)
        if rows.empty:
            return []
        upc = rows.iloc[0].get("upc_version", "")
        return self.get_images(upc, max_images)

    def ordered_record(self, row: pd.Series) -> list[tuple[str, str]]:
        all_cols = list(row.index)
        priority = [c for c in _DISPLAY_ORDER if c in all_cols]
        rest     = [c for c in all_cols if c not in priority]
        return [(c, str(row.get(c, ""))) for c in priority + rest]

    def update_field(self, row_index: int, column: str, value: str) -> bool:
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
        self._load()

    """ def registrar_nuevo_producto(
        self,
        upc_capturado: str,
        nombre: str,
        cluster_id: int,
        gramaje: str = "",
        category: str = "",
        sku_id: str = "",
        imagenes_paths: list[str] = None
    ) -> str:
        # Validar permisos de archivo antes de procesar
        try:
            with open(self.csv_path, 'a', encoding='utf-8') as f:
                pass
        except PermissionError:
            raise PermissionError(
                "El archivo CSV está siendo utilizado por otra aplicación (como Excel).\n"
                "Por favor, ciérralo e intenta nuevamente."
            )

        df = pd.read_csv(self.csv_path, dtype=str).fillna("")

        # 1. Calcular SKU índice
        sku_numericos = pd.to_numeric(df['sku_indice'], errors='coerce')
        max_sku = sku_numericos.max()
        nuevo_sku_indice = int(max_sku + 1) if pd.notnull(max_sku) else 1
        sku_clase = f"sku{nuevo_sku_indice}"

        # 2. Calcular versión por coincidencia de UPC
        coincidencias = df[df['upc_capturado'].astype(str) == str(upc_capturado)]
        product_version = len(coincidencias)
        upc_version = f"{upc_capturado}_{product_version}"

        nueva_fila = {
            'SKU ID': str(sku_id),
            'upc_capturado': str(upc_capturado),
            'nombre_capturado': str(nombre),
            'product_version': str(product_version),
            'product category': str(category),
            'gramaje': str(gramaje),
            'cluster_id': str(cluster_id),
            'sku_indice': str(nuevo_sku_indice),
            'sku_clase': sku_clase,
            'upc_version': upc_version,
            'Short Name': str(nombre)[:40]
        }

        # Sincronizar dinámicamente con cualquier otra columna presente
        for col in df.columns:
            if col not in nueva_fila:
                nueva_fila[col] = ""

        df_actualizado = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
        df_actualizado.to_csv(self.csv_path, index=False, encoding='utf-8')

        self.reload()

        # Copiar imágenes al catálogo
        folder_path = os.path.join(self.dataset_dir, upc_version)
        os.makedirs(folder_path, exist_ok=True)

        if imagenes_paths:
            for idx, img_path in enumerate(imagenes_paths[:3], start=1):
                if os.path.exists(img_path):
                    ext = os.path.splitext(img_path)[1].lower() or '.jpg'
                    shutil.copy2(img_path, os.path.join(folder_path, f"foto_{idx}{ext}"))

        return upc_version
    """
    def actualizar_catalogo_masivo(self, nuevo_csv_path: str, nueva_carpeta_imagenes: str) -> tuple[int, int]:
        """
        Fusiona el CSV recibido con el actual (preserva productos anteriores,
        actualiza existentes y añade nuevos) y copia las imágenes asociadas.
        
        Devuelve una tupla (total_productos_csv, total_carpetas_copiadas).
        """
        if not os.path.exists(nuevo_csv_path):
            raise FileNotFoundError(f"El archivo CSV no existe: {nuevo_csv_path}")

        # 1. Fusión inteligente (Merge / UPSERT) de los CSV
        if os.path.exists(self.csv_path):
            try:
                df_old = pd.read_csv(self.csv_path, dtype=str).fillna("")
                df_new = pd.read_csv(nuevo_csv_path, dtype=str).fillna("")

                # Identificar la columna clave para la fusión
                key_col = None
                if "upc_version" in df_old.columns and "upc_version" in df_new.columns:
                    key_col = "upc_version"
                elif "sku_indice" in df_old.columns and "sku_indice" in df_new.columns:
                    key_col = "sku_indice"

                if key_col:
                    # Concatenar ambos DataFrames
                    df_merged = pd.concat([df_old, df_new], ignore_index=True)
                    # Mantiene la versión del 'nuevo_csv' si coincide la clave, pero conserva los anteriores
                    df_merged = df_merged.drop_duplicates(subset=[key_col], keep="last")
                else:
                    df_merged = df_new

                # Guardar el CSV combinado en la ruta oficial
                df_merged.to_csv(self.csv_path, index=False, encoding="utf-8")
            except Exception as e:
                print(f"[Visualizador] Error al fusionar CSVs, recurriendo a copia directa: {e}")
                shutil.copy2(nuevo_csv_path, self.csv_path)
        else:
            # Si no existía un CSV previo, se hace la copia inicial
            shutil.copy2(nuevo_csv_path, self.csv_path)

        # 2. Copiar/Fusionar carpetas de imágenes hacia DATASET_DIR
        carpetas_copiadas = 0
        if os.path.exists(nueva_carpeta_imagenes) and os.path.isdir(nueva_carpeta_imagenes):
            for item in os.listdir(nueva_carpeta_imagenes):
                src_folder = os.path.join(nueva_carpeta_imagenes, item)
                
                # Procesa solo subcarpetas (ej. 777302931_0)
                if os.path.isdir(src_folder):
                    dst_folder = os.path.join(self.dataset_dir, item)
                    os.makedirs(dst_folder, exist_ok=True)
                    
                    # Copiar cada imagen dentro de la subcarpeta destino (sin borrar las previas)
                    for file_name in os.listdir(src_folder):
                        src_file = os.path.join(src_folder, file_name)
                        if os.path.isfile(src_file) and os.path.splitext(file_name.lower())[1] in _SUPPORTED_EXT:
                            shutil.copy2(src_file, os.path.join(dst_folder, file_name))
                    carpetas_copiadas += 1

        # 3. Recargar la base de datos interna con la combinación final
        self.reload()
        return len(self.df), carpetas_copiadas