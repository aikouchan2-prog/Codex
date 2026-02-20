from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}


@dataclass
class RenamePlan:
    source: Path
    destination: Path


class ThumbnailList(QListWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setViewMode(QListWidget.IconMode)
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Snap)
        self.setDragDropMode(QListWidget.InternalMove)
        self.setSpacing(10)
        self.setWordWrap(True)
        self.setIconSize(QSize(140, 140))
        self.setGridSize(QSize(170, 190))

    def ordered_paths(self) -> list[Path]:
        paths: list[Path] = []
        for i in range(self.count()):
            item = self.item(i)
            raw = item.data(Qt.UserRole)
            if raw:
                paths.append(Path(raw))
        return paths


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Image Sorter & Batch Renamer")
        self.resize(1080, 760)

        self.current_dir: Path | None = None

        self.thumbnail_list = ThumbnailList()

        self.folder_label = QLabel("フォルダ未選択")
        self.folder_label.setWordWrap(True)

        choose_button = QPushButton("フォルダを開く")
        choose_button.clicked.connect(self.choose_folder)

        refresh_button = QPushButton("再読み込み")
        refresh_button.clicked.connect(self.reload_images)

        rename_button = QPushButton("現在の並びで一括リネーム")
        rename_button.clicked.connect(self.batch_rename)

        self.prefix_input = QLineEdit("image_")
        self.start_number = QSpinBox()
        self.start_number.setMinimum(0)
        self.start_number.setMaximum(9_999_999)
        self.start_number.setValue(1)

        self.padding = QSpinBox()
        self.padding.setMinimum(1)
        self.padding.setMaximum(10)
        self.padding.setValue(3)

        self.keep_extension = QPushButton("拡張子を維持")
        self.keep_extension.setCheckable(True)
        self.keep_extension.setChecked(True)

        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(12, 12, 12, 12)

        top_row = QHBoxLayout()
        top_row.addWidget(choose_button)
        top_row.addWidget(refresh_button)
        top_row.addWidget(rename_button)
        controls_layout.addLayout(top_row)
        controls_layout.addWidget(self.folder_label)

        form = QFormLayout()
        form.addRow("プレフィックス", self.prefix_input)
        form.addRow("開始番号", self.start_number)
        form.addRow("ゼロ埋め桁数", self.padding)
        form.addRow("設定", self.keep_extension)
        controls_layout.addLayout(form)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(controls)
        layout.addWidget(self.thumbnail_list)
        self.setCentralWidget(container)

        open_action = QAction("フォルダを開く", self)
        open_action.triggered.connect(self.choose_folder)
        open_action.setShortcut("Ctrl+O")
        self.menuBar().addAction(open_action)

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "画像フォルダを選択")
        if not folder:
            return
        self.current_dir = Path(folder)
        self.folder_label.setText(str(self.current_dir))
        self.reload_images()

    def reload_images(self) -> None:
        self.thumbnail_list.clear()
        if not self.current_dir:
            return

        images = sorted(
            [p for p in self.current_dir.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS],
            key=lambda p: p.name.lower(),
        )

        for path in images:
            self.thumbnail_list.addItem(self._item_for_image(path))

    def _item_for_image(self, path: Path) -> QListWidgetItem:
        pixmap = QPixmap(str(path))
        icon = QIcon(pixmap.scaled(140, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        item = QListWidgetItem(icon, path.name)
        item.setToolTip(str(path))
        item.setData(Qt.UserRole, str(path))
        item.setFlags(
            Qt.ItemIsSelectable
            | Qt.ItemIsEnabled
            | Qt.ItemIsDragEnabled
            | Qt.ItemIsDropEnabled
        )
        return item

    def batch_rename(self) -> None:
        if not self.current_dir:
            QMessageBox.warning(self, "エラー", "先にフォルダを選択してください。")
            return

        ordered = self.thumbnail_list.ordered_paths()
        if not ordered:
            QMessageBox.information(self, "情報", "リネーム対象がありません。")
            return

        plans = self._build_rename_plan(ordered)

        conflict = [p for p in plans if p.destination.exists() and p.destination != p.source]
        if conflict:
            msg = "以下のファイル名が既に存在するため中断しました:\n" + "\n".join(
                f"- {p.destination.name}" for p in conflict[:10]
            )
            QMessageBox.critical(self, "競合", msg)
            return

        try:
            temp_mapped: list[tuple[Path, Path]] = []
            for plan in plans:
                temp_path = plan.source.with_name(f".__tmp__{uuid.uuid4().hex}{plan.source.suffix}")
                os.replace(plan.source, temp_path)
                temp_mapped.append((temp_path, plan.destination))

            for temp, destination in temp_mapped:
                os.replace(temp, destination)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "リネーム失敗", f"処理中にエラー: {exc}")
            return

        QMessageBox.information(self, "完了", f"{len(plans)} 件のファイル名を更新しました。")
        self.reload_images()

    def _build_rename_plan(self, ordered_paths: Iterable[Path]) -> list[RenamePlan]:
        prefix = self.prefix_input.text().strip() or "image_"
        start = self.start_number.value()
        padding = self.padding.value()
        keep_extension = self.keep_extension.isChecked()

        plans: list[RenamePlan] = []
        for idx, source in enumerate(ordered_paths):
            number = str(start + idx).zfill(padding)
            suffix = source.suffix if keep_extension else ""
            dest_name = f"{prefix}{number}{suffix}"
            destination = source.with_name(dest_name)
            plans.append(RenamePlan(source=source, destination=destination))
        return plans


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
