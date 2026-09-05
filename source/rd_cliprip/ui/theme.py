GLOBAL_STYLESHEET = """
/* Menu bar items (File, Edit, View, ...) light up on hover.
   NOTE: no QPushButton rules here - styling buttons forces them into the
   stylesheet renderer and hides their native background/border. */
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
"""
