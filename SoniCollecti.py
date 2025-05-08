import pandas as pd
from pp_cleaning import load_data
from taptop import top_chart
from PySide6 import QtCore, QtWidgets, QtGui
import sys


class Thread(QtCore.QThread):
    def run(self):
        QtCore.QThread.sleep(2)

class Application(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.title = "Soni Collecti"
        self.left = 0
        self.top = 0
        self.width = 720
        self.height = 400

        self.setWindowTitle(self.title)
        self.setGeometry(self.left,
                         self.top,
                         self.width,
                         self.height)

        self.tabs = SCTabs()
        self.setCentralWidget(self.tabs)

        self.show()

class SCTabs(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QtWidgets.QVBoxLayout(self)
        self.df = load_data()

        self.chart_options = ["Album", "Artist", "Track"]
        self.tz_options = ["Local", "GMT"]

        # initialize tabs
        self.tabs = QtWidgets.QTabWidget()
        self.stats_tab = QtWidgets.QWidget()
        self.chart_tab = QtWidgets.QWidget()
        self.settings_tab = QtWidgets.QWidget()

        # add tabs
        self.tabs.addTab(self.stats_tab, "Stats")
        self.tabs.addTab(self.chart_tab, "Charts")
        self.tabs.addTab(self.settings_tab, "Settings")

        self.chart_layout = QtWidgets.QVBoxLayout(self.chart_tab)
        self.chart_layout.setContentsMargins(0, 0, 0, 0)

        self.load_timezone()
        self.load_chart_boxes()

        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)

    def load_timezone(self):
        tz_label = QtWidgets.QLabel("Timezone")
        self.tz_combo = QtWidgets.QComboBox()
        self.tz_combo.addItems(self.tz_options)

        self.chart_layout.addWidget(tz_label)
        self.chart_layout.addWidget(self.tz_combo)

    def load_chart_boxes(self):
        title_label = QtWidgets.QLabel("Chart Generator")
        generate_button = QtWidgets.QPushButton("Generate Chart")
        layout_chart_buttons = QtWidgets.QHBoxLayout(self)
        layout_chart_buttons.setContentsMargins(0, 0, 0, 0)

        chart_type_label = QtWidgets.QLabel("Chart Type")
        self.chart_type_combo  = QtWidgets.QComboBox()
        self.chart_type_combo.addItems(self.chart_options)

        start_label = QtWidgets.QLabel("Start Date")
        self.chart_start_entry = QtWidgets.QDateEdit()
        self.chart_start_entry.setDate(QtCore.QDate(self.df[f"time_{self.tz_combo.currentText().lower()}"].min()))

        end_label = QtWidgets.QLabel("End Date")
        self.chart_end_entry = QtWidgets.QDateEdit()
        self.chart_end_entry.setDate(QtCore.QDate(self.df[f"time_{self.tz_combo.currentText().lower()}"].max()))

        grid_rows_label = QtWidgets.QLabel("# of Rows")
        self.grid_rows_entry = QtWidgets.QLineEdit("3")

        grid_cols_label = QtWidgets.QLabel("# of Columns")
        self.grid_cols_entry = QtWidgets.QLineEdit("3")

        # add widget to layout
        self.chart_layout.addWidget(title_label, alignment=QtCore.Qt.AlignTop)
        layout_chart_buttons.addWidget(generate_button, alignment=QtCore.Qt.AlignTop)
        layout_chart_buttons.addWidget(chart_type_label, alignment=QtCore.Qt.AlignTop)
        layout_chart_buttons.addWidget(self.chart_type_combo, alignment=QtCore.Qt.AlignTop)

        layout_chart_buttons.addWidget(start_label, alignment=QtCore.Qt.AlignTop)
        layout_chart_buttons.addWidget(self.chart_start_entry, alignment=QtCore.Qt.AlignTop)
        layout_chart_buttons.addWidget(end_label, alignment=QtCore.Qt.AlignTop)
        layout_chart_buttons.addWidget(self.chart_end_entry, alignment=QtCore.Qt.AlignTop)
        layout_chart_buttons.addWidget(grid_rows_label, alignment=QtCore.Qt.AlignTop)
        layout_chart_buttons.addWidget(self.grid_rows_entry, alignment=QtCore.Qt.AlignTop)
        layout_chart_buttons.addWidget(grid_cols_label, alignment=QtCore.Qt.AlignTop)
        layout_chart_buttons.addWidget(self.grid_cols_entry, alignment=QtCore.Qt.AlignTop)

        generate_button.clicked.connect(self.generate_chart)
        self.chart_layout.addLayout(layout_chart_buttons)

    @QtCore.Slot()
    def generate_chart(self):
        print(pd.to_datetime(self.chart_start_entry.text()).date())
        print(pd.to_datetime(self.chart_end_entry.text()).date())
        print(self.chart_type_combo.currentText())
        top_chart(df=self.df,
                  date_start=pd.to_datetime(self.chart_start_entry.text()),
                  date_end=pd.to_datetime(self.chart_end_entry.text()),
                  chart_type=self.chart_type_combo.currentText(),
                  grid_size=(int(self.grid_rows_entry.text()), int(self.grid_cols_entry.text())),
                  tz=self.tz_combo.currentText())


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    ex = Application()
    sys.exit(app.exec())
