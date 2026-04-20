#!/usr/bin/python
# -*- coding: utf-8 -*-


from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from libs.utils import distance
import sys

DEFAULT_LINE_COLOR = QColor(0, 255, 0, 128)
DEFAULT_FILL_COLOR = QColor(255, 0, 0, 128)
DEFAULT_SELECT_LINE_COLOR = QColor(255, 255, 255)
DEFAULT_SELECT_FILL_COLOR = QColor(0, 128, 255, 155)
DEFAULT_VERTEX_FILL_COLOR = QColor(0, 255, 0, 255)
DEFAULT_HVERTEX_FILL_COLOR = QColor(255, 0, 0)


class Shape(object):
    P_SQUARE, P_ROUND = range(2)

    MOVE_VERTEX, NEAR_VERTEX = range(2)

    # --- Atributos de Clase (Configuración Global vía Plugins) ---
    line_color = DEFAULT_LINE_COLOR
    fill_color = DEFAULT_FILL_COLOR
    select_line_color = DEFAULT_SELECT_LINE_COLOR
    select_fill_color = DEFAULT_SELECT_FILL_COLOR
    vertex_fill_color = DEFAULT_VERTEX_FILL_COLOR
    h_vertex_fill_color = DEFAULT_HVERTEX_FILL_COLOR
    point_type = P_ROUND
    point_size = 9
    scale = 1.0
    label_font_size = 8
    
    # Nuevos parámetros extendidos
    line_thickness = 2.0
    fill_alpha = 128             # 0-255
    adaptive_thickness = False
    highlight_selected = True
    focus_mode = False
    show_dimensions = False
    saturation_factor = 1.0  # NUEVO: Factor de saturación (1.0 = normal)
    sharp_edges = False      # NUEVO: Bordes nítidos (sin antialiasing)
    dash_style = Qt.SolidLine    # Qt.SolidLine, Qt.DashLine, etc.

    def __init__(self, label=None, line_color=None, difficult=False, paint_label=False):
        self.label = label
        self.points = []
        self.fill = False
        self.selected = False
        self.difficult = difficult
        self.paint_label = paint_label

        self._highlight_index = None
        self._highlight_mode = self.NEAR_VERTEX
        self._highlight_settings = {
            self.NEAR_VERTEX: (2, self.P_ROUND),
            self.MOVE_VERTEX: (1.2, self.P_SQUARE),
        }

        self._closed = False

        if line_color is not None:
            self.line_color = line_color

    def close(self):
        self._closed = True

    def reach_max_points(self):
        if len(self.points) >= 4:
            return True
        return False

    def add_point(self, point):
        if not self.reach_max_points():
            self.points.append(point)

    def pop_point(self):
        if self.points:
            return self.points.pop()
        return None

    def is_closed(self):
        return self._closed

    def set_open(self):
        self._closed = False

    def paint(self, painter):
        if self.points:
            # 1. Determinar Color y Opacidad (Focus Mode)
            color = self.select_line_color if self.selected else self.line_color
            
            # Focus Mode: Atenuar si NO está seleccionada
            alpha = 255
            if Shape.focus_mode and not self.selected:
                alpha = 60 # 20-30% de opacidad
            
            # Aplicar Saturación
            if Shape.saturation_factor != 1.0:
                h, s, v, a = color.getHsv()
                new_s = min(255, int(s * Shape.saturation_factor))
                color = QColor.fromHsv(h, new_s, v, a)

            # 2. Configurar Pen (Grosor Adaptativo y Highlight)
            if Shape.sharp_edges:
                painter.setRenderHint(QPainter.Antialiasing, False)
            else:
                painter.setRenderHint(QPainter.Antialiasing, True)

            pen = QPen(color)
            pen.setStyle(Shape.dash_style)
            
            # Asegurar que el borde sea sólido y marcado incluso si el relleno es tenue
            c_pen = pen.color()
            c_pen.setAlpha(255) # Borde siempre sólido para máximo contraste
            pen.setColor(c_pen)
            
            thickness = Shape.line_thickness
            
            # Highlight de selección: +2px
            if Shape.highlight_selected and self.selected:
                thickness += 2.0
                
            # Grosor Adaptativo al Zoom
            # Si scale es pequeña (zoom out), la línea se ve muy gruesa si no compensamos.
            # Aquí la lógica es mantener la visibilidad.
            if Shape.adaptive_thickness:
                # Ajuste empírico para que se vea consistente
                actual_width = max(1, int(round(thickness * (1.0 / self.scale) ** 0.5)))
            else:
                actual_width = max(1, int(round(thickness / self.scale)))
            
            pen.setWidth(actual_width)
            
            # Aplicar opacidad al pen si está en focus mode
            if Shape.focus_mode and not self.selected:
                c = pen.color()
                c.setAlpha(alpha)
                pen.setColor(c)
                
            painter.setPen(pen)

            line_path = QPainterPath()
            vertex_path = QPainterPath()

            line_path.moveTo(self.points[0])

            for i, p in enumerate(self.points):
                line_path.lineTo(p)
                if self.selected and (self._highlight_index == i or self._highlight_index is None):
                    self.draw_vertex(vertex_path, i)
            if self.is_closed():
                line_path.lineTo(self.points[0])

            painter.drawPath(line_path)
            painter.drawPath(vertex_path)
            painter.fillPath(vertex_path, self.vertex_fill_color)

            # 3. Dibujar Dimensiones (W x H)
            if Shape.show_dimensions and self.is_closed() and len(self.points) == 4:
                self._paint_dimensions(painter)

            # 4. Dibujar Etiqueta
            if self.paint_label:
                self._paint_label(painter)

            # 5. Relleno (Alpha dinámico)
            if self.fill:
                fill_color = self.select_fill_color if self.selected else self.fill_color
                # Aplicar alpha personalizado del plugin
                f_color = QColor(fill_color)
                
                # Si estamos en focus mode y no seleccionada, alpha extra bajo
                current_alpha = Shape.fill_alpha
                if Shape.focus_mode and not self.selected:
                    current_alpha = int(current_alpha * 0.3)
                
                f_color.setAlpha(current_alpha)
                painter.fillPath(line_path, f_color)

    def _paint_label(self, painter):
        min_x = sys.maxsize
        min_y = sys.maxsize
        min_y_label = int(1.25 * self.label_font_size)
        for point in self.points:
            min_x = min(min_x, point.x())
            min_y = min(min_y, point.y())
        if min_x != sys.maxsize and min_y != sys.maxsize:
            font = QFont()
            font.setPointSize(self.label_font_size)
            font.setBold(True)
            painter.setFont(font)
            if self.label is None:
                self.label = ""
            if min_y < min_y_label:
                min_y += min_y_label
            painter.drawText(int(min_x), int(min_y), self.label)

    def _paint_dimensions(self, painter):
        # Calcular W y H
        min_x = min(p.x() for p in self.points)
        max_x = max(p.x() for p in self.points)
        min_y = min(p.y() for p in self.points)
        max_y = max(p.y() for p in self.points)
        w = int(max_x - min_x)
        h = int(max_y - min_y)
        
        dim_text = f"{w}x{h}"
        font = QFont("Consolas", 7)
        painter.setFont(font)
        
        # Dibujar en el centro o inferior derecha
        rect = painter.fontMetrics().boundingRect(dim_text)
        painter.setPen(QPen(Qt.white))
        painter.drawText(int(max_x - rect.width()), int(max_y + rect.height()), dim_text)

    def draw_vertex(self, path, i):
        d = max(3.0, self.point_size / self.scale)
        shape = self.point_type
        point = self.points[i]
        if i == self._highlight_index:
            size, shape = self._highlight_settings[self._highlight_mode]
            d *= size
        if self._highlight_index is not None:
            self.vertex_fill_color = self.h_vertex_fill_color
        else:
            self.vertex_fill_color = Shape.vertex_fill_color
        if shape == self.P_SQUARE:
            path.addRect(point.x() - d / 2, point.y() - d / 2, d, d)
        elif shape == self.P_ROUND:
            path.addEllipse(point, d / 2.0, d / 2.0)

    def nearest_vertex(self, point, epsilon):
        index = None
        for i, p in enumerate(self.points):
            dist = distance(p - point)
            if dist <= epsilon:
                index = i
                epsilon = dist
        return index

    def contains_point(self, point):
        return self.make_path().contains(point)

    def make_path(self):
        path = QPainterPath(self.points[0])
        for p in self.points[1:]:
            path.lineTo(p)
        return path

    def bounding_rect(self):
        return self.make_path().boundingRect()

    def move_by(self, offset):
        self.points = [p + offset for p in self.points]

    def move_vertex_by(self, i, offset):
        self.points[i] = self.points[i] + offset

    def highlight_vertex(self, i, action):
        self._highlight_index = i
        self._highlight_mode = action

    def highlight_clear(self):
        self._highlight_index = None

    def copy(self):
        shape = Shape("%s" % self.label)
        shape.points = [p for p in self.points]
        shape.fill = self.fill
        shape.selected = self.selected
        shape._closed = self._closed
        if self.line_color != Shape.line_color:
            shape.line_color = self.line_color
        if self.fill_color != Shape.fill_color:
            shape.fill_color = self.fill_color
        shape.difficult = self.difficult
        return shape

    def __len__(self):
        return len(self.points)

    def __getitem__(self, key):
        return self.points[key]

    def __setitem__(self, key, value):
        self.points[key] = value
