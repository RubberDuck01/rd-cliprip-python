GLOBAL_STYLESHEET = """
/* Menu bar items (File, Edit, View, ...) light up on hover */
QMenuBar::item {
    padding: 4px 8px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background: rgba(128, 128, 128, 60);
}
QMenuBar::item:pressed {
    background: rgba(128, 128, 128, 95);
}

/* Dropdown menus */
QMenu::item {
    padding: 5px 24px 5px 20px;
    border-radius: 4px;
}
QMenu::item:selected {
    background: rgba(128, 128, 128, 55);
}

/* Buttons */
QPushButton {
    border-radius: 4px;
    padding: 4px 12px;
}
QPushButton:hover {
    background: rgba(128, 128, 128, 45);
}
QPushButton:pressed {
    background: rgba(128, 128, 128, 90);
}
"""
