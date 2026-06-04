import os
import re
import PyInstaller.__main__


def update_version():
    version_file = os.path.join("libs", "__init__.py")
    if not os.path.exists(version_file):
        print("No se encontró libs/__init__.py")
        return None

    # Leer versión actual
    with open(version_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Buscar la línea de __version_info__
    match = re.search(r"__version_info__\s*=\s*\(([^)]+)\)", content)
    if not match:
        print("No se pudo parsear __version_info__ en libs/__init__.py")
        return None

    parts = [p.strip().strip("'\"") for p in match.group(1).split(",")]
    while len(parts) < 3:
        parts.append("0")
    
    try:
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        print(f"Error parseando partes de versión: {parts}")
        return None

    current_ver = f"{major}.{minor}.{patch}"
    print(f"\nVersión actual del proyecto: v{current_ver}")
    print("Selecciona el tipo de cambio para la nueva versión de la build:")
    print("  1. Cambio GRANDE (Incrementar versión principal, ej: v1.8.6 -> v2.0.0)")
    print("  2. Cambio PEQUEÑO o corrección (Incrementar versión menor, ej: v1.8.6 -> v1.9.0)")
    print("  3. Sin cambios de versión (Mantener versión actual)")
    
    try:
        choice = input("Selecciona una opción (1/2/3): ").strip()
    except Exception:
        # Fallback si se ejecuta de forma no interactiva
        choice = "3"

    if choice == "1":
        new_ver = (major + 1, 0, 0)
    elif choice == "2":
        new_ver = (major, minor + 1, 0)
    else:
        print("Se mantendrá la versión actual.")
        return current_ver

    new_ver_str = ".".join(map(str, new_ver))
    print(f"Actualizando a la versión: v{new_ver_str}")

    # Reemplazar la versión en el archivo
    new_content = re.sub(
        r"__version_info__\s*=\s*\([^)]+\)",
        f"__version_info__ = ({', '.join(repr(str(x)) for x in new_ver)})",
        content
    )
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    return new_ver_str


def build():
    # Actualizar la versión de forma interactiva antes de construir
    new_ver = update_version()

    base_path = os.path.abspath(".")

    # En Windows, PyInstaller usa ';' como separador para --add-data
    sep = os.pathsep

    added_files = [
        (os.path.join(base_path, "custom"), "custom"),
        (os.path.join(base_path, "data"), "data"),
        (os.path.join(base_path, "libs"), "libs"),
        (os.path.join(base_path, "resources"), "resources"),
    ]

    hidden_imports = [
        "PyQt5.QtCore",
        "PyQt5.QtGui",
        "PyQt5.QtWidgets",
        "PyQt5.QtXml",
    ]

    # Módulos pesados que esta app no usa (ahorra tamaño y tiempo de arranque)
    excludes = [
        "cv2",
        "numpy",
        "matplotlib",
        "pandas",
        "scipy",
        "PIL",
        "tkinter",
        "IPython",
        "pytest",
    ]

    exe_name = "LabelImgCustom"
    if new_ver:
        # Opcional: renombrar el exe con la versión para diferenciar la build
        exe_name = f"LabelImgCustom_v{new_ver}"

    args = [
        "labelImg.py",
        f"--name={exe_name}",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--onedir",
    ]

    for src, dest in added_files:
        if os.path.exists(src):
            args.append(f"--add-data={src}{sep}{dest}")

    for imp in hidden_imports:
        args.append(f"--hidden-import={imp}")

    for mod in excludes:
        args.append(f"--exclude-module={mod}")

    # En Windows el icono del .exe debe ser .ico
    icon_ico = os.path.join(base_path, "resources", "icons", "app.ico")
    icon_png = os.path.join(base_path, "resources", "icons", "app.png")
    if os.path.exists(icon_ico):
        args.append(f"--icon={icon_ico}")
    elif os.path.exists(icon_png):
        args.append(f"--icon={icon_png}")

    print(f"\n--- Iniciando build de {exe_name} (sin OpenCV) ---")
    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    build()
