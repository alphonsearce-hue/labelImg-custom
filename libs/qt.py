#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import importlib

# Centralized Qt abstraction layer for labelImg.
# This module selects the best available Qt binding (PyQt5 or PyQt4)
# and silences IDE warnings for missing legacy modules.

try:
    # --- Try PyQt5 ---
    from PyQt5.QtCore import *
    from PyQt5.QtGui import *
    from PyQt5.QtWidgets import *
    
    # Handle sip
    
    QT5 = True
    QStringList = list # PyQt5 uses native list

except ImportError:
    # --- Fallback to PyQt4 ---
    try:
        # We use importlib to hide these from IDEs that don't have PyQt4 installed
        QtCore = importlib.import_module('PyQt4.QtCore')
        QtGui = importlib.import_module('PyQt4.QtGui')
        
        # In PyQt4, QtWidgets were part of QtGui
        QtWidgets = QtGui
        
        # Handle sip for PyQt4 on Python 3
        if sys.version_info.major >= 3:
            try:
                sip = importlib.import_module('sip')
                sip.setapi('QVariant', 2)
            except ImportError:
                pass
       
        # Inject into globals for star import support from this module
        globals().update(QtCore.__dict__)
        globals().update(QtGui.__dict__)

        # Compatibility mappings
        if not hasattr(QtCore, 'pyqtSignal'):
            QtCore.pyqtSignal = QtCore.Signal
        if not hasattr(QtCore, 'pyqtSlot'):
            QtCore.pyqtSlot = QtCore.Slot
            
        QT5 = False
        QT_VERSION_STR = QtCore.QT_VERSION_STR
        QStringList = QtGui.QStringList if hasattr(QtGui, 'QStringList') else list

    except ImportError:
        raise ImportError("Neither PyQt5 nor PyQt4 found. Please install one of them.")

# The globals() update above and the star imports from PyQt5 
# make everything available when doing 'from libs.qt import *'
