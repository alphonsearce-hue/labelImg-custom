import PyInstaller.__main__
import os

def build():
    base_path = os.path.abspath(".")
    
    # IMPORTANTE: En Windows, PyInstaller usa ';' como separador para --add-data
    # En Linux/Mac usa ':'
    sep = ";" 
    
    added_files = [
        (os.path.join(base_path, "custom"), "custom"),
        (os.path.join(base_path, "data"), "data"),
        (os.path.join(base_path, "libs"), "libs"),
        (os.path.join(base_path, "resources"), "resources"),
    ]

    hidden_imports = [
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtXml',
    ]

    args = [
        'labelImg.py',
        '--name=LabelImgCustom',
        '--windowed',
        '--noconfirm',
        '--clean',
        '--onedir',
    ]

    for src, dest in added_files:
        if os.path.exists(src):
            # Formato correcto: "origen;destino"
            args.append(f'--add-data={src}{sep}{dest}')

    for imp in hidden_imports:
        args.append(f'--hidden-import={imp}')

    icon_path = os.path.join(base_path, "resources", "icons", "app.png")
    if os.path.exists(icon_path):
        args.append(f'--icon={icon_path}')

    print("--- Iniciando proceso corregido ---")
    PyInstaller.__main__.run(args)

if __name__ == "__main__":
    build()
