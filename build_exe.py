import os

import PyInstaller.__main__


def build():
    base_path = os.path.abspath(".")

    # En Windows, PyInstaller usa ';' como separador para --add-data, y en Linux/Mac usa ':'
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

    args = [
        "labelImg.py",
        "--name=LabelImgCustom",
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

    print("--- Iniciando build (sin OpenCV) ---")
    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    build()
