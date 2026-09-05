from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class SessionEditDialog(QDialog):
    """Rename a session and/or change its download directory."""

    def __init__(self, parent, label: str, output_dir: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Session")
        self.setModal(True)
        self.resize(460, 140)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(6)

        self.label_input = QLineEdit(label)
        form.addRow("Session name:", self.label_input)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(6)
        self.dir_input = QLineEdit(output_dir)
        self.dir_input.setReadOnly(True)
        dir_row.addWidget(self.dir_input, stretch=1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_dir)
        dir_row.addWidget(browse_btn)
        form.addRow("Download folder:", dir_row)

        layout.addLayout(form)

        hint_label = QLabel("Changing the folder affects new downloads only.")
        hint_label.setEnabled(False)
        layout.addWidget(hint_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _browse_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select Download Folder", self.dir_input.text()
        )
        if path:
            self.dir_input.setText(path)

    def values(self) -> tuple[str, str]:
        return self.label_input.text().strip(), self.dir_input.text().strip()
