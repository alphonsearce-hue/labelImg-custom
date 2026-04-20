import hashlib
from PyQt5.QtGui import QColor


COLOR_THEMES = {
    "neon": [
        "#39FF14", "#00E5FF", "#FF00FF", "#FF3131", "#FFF01F", "#8A2BE2",
        "#00FF7F", "#FF5F1F", "#00BFFF", "#FF1493", "#E4FF1A", "#7CFC00",
    ],
    "dark": [
        "#7F5AF0", "#2CB67D", "#F25F4C", "#94A1B2", "#EF4565", "#3DA9FC",
        "#A786DF", "#5BC0BE", "#F4A261", "#4CC9F0", "#90BE6D", "#F8961E",
    ],
    "military": [
        "#6B705C", "#A5A58D", "#B7B7A4", "#CB997E", "#DDBEA9", "#A98467",
        "#7F5539", "#606C38", "#283618", "#9C6644", "#774936", "#B08968",
    ],
    "ocean": [
        "#023E8A", "#0077B6", "#0096C7", "#00B4D8", "#48CAE4", "#90E0EF",
        "#ADE8F4", "#CAF0F8", "#3A86FF", "#4CC9F0", "#4361EE", "#4895EF",
    ],
    "sunset": [
        "#FF6B6B", "#F06595", "#CC5DE8", "#845EF7", "#5C7CFA", "#339AF0",
        "#22B8CF", "#20C997", "#51CF66", "#94D82D", "#FCC419", "#FF922B",
    ],
    "pastel": [
        "#FFD6E0", "#FFDEB4", "#FFF3B0", "#D9ED92", "#B5E48C", "#99D98C",
        "#76C893", "#52B69A", "#34A0A4", "#168AAD", "#1A759F", "#184E77",
    ],
    "cyberpunk": [
        "#00F5D4", "#00BBF9", "#F15BB5", "#9B5DE5", "#FEE440", "#FB5607",
        "#FF006E", "#8338EC", "#3A86FF", "#06D6A0", "#EF476F", "#FFD166",
    ],
    "forest": [
        "#1B4332", "#2D6A4F", "#40916C", "#52B788", "#74C69D", "#95D5B2",
        "#B7E4C7", "#081C15", "#2A9D8F", "#588157", "#3A5A40", "#A3B18A",
    ],
    "grayscale": [
        "#111111", "#222222", "#333333", "#444444", "#555555", "#666666",
        "#777777", "#888888", "#999999", "#AAAAAA", "#BBBBBB", "#DDDDDD",
    ],
    "retro": [
        "#264653", "#2A9D8F", "#E9C46A", "#F4A261", "#E76F51", "#8AB17D",
        "#F2CC8F", "#E07A5F", "#81B29A", "#3D405B", "#6D597A", "#B56576",
    ],
}

THEME_LABELS = {
    "neon": "Neón / Llamativo",
    "dark": "Oscuro / Tech",
    "military": "Militar / Tierra",
    "ocean": "Océano",
    "sunset": "Atardecer",
    "pastel": "Pastel",
    "cyberpunk": "Cyberpunk",
    "forest": "Bosque",
    "grayscale": "Escala de grises",
    "retro": "Retro",
}


MODE_INSTANCE = "instance"
MODE_CLASS = "class"
MODE_UNIFIED = "unified"
ALL_MODES = (MODE_INSTANCE, MODE_CLASS, MODE_UNIFIED)


def stable_index(text, modulo):
    if modulo <= 0:
        return 0
    encoded = (text or "").encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return int(digest, 16) % modulo


def color_from_hex(hex_color, alpha=255):
    color = QColor(hex_color)
    color.setAlpha(alpha)
    return color

