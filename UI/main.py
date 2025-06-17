from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QGraphicsScene,
    QGraphicsTextItem,
    QFileDialog,
    QGraphicsPolygonItem,
    QGraphicsView,
)
from PySide6.QtGui import QPolygonF
from PySide6.QtCore import QPointF
from main_ui import Ui_MainWindow
import xml.etree.ElementTree as et
import sys





class mw(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.scene = QGraphicsScene(self)
        # self.ui.graphicsView = contourviewer(self)

        self.ui.graphicsView.setScene(self.scene)

        self.ui.actionOpen.triggered.connect(self.onopen)
        self.ui.actionExport_to_DXF.triggered.connect(self.onexport)
        self.ui.graphicsView.wheelEvent

    def onopen(self, s):
        filname = QFileDialog.getOpenFileName(self, filter="*.xml")[0]
        print(filname)
        self.contours = readxml(filname)

        for contour in self.contours:
            poly = QPolygonF()
            for point in contour:
                poly.append(QPointF(*point))
            polyitem = QGraphicsPolygonItem(poly)
            self.scene.addItem(polyitem)

    def onexport(self, s):
        pass


def readxml(path):
    tree = et.parse(path)
    root = tree.getroot()
    res = []
    for contour in root.iter("contour"):
        for sp in contour.iter("spatial_element"):
            points = []
            for ord in sp.iter("ordinate"):
                points.append((float(ord.find("y").text), float(ord.find("x").text)))
            res.append(points)
    return res


if __name__ == "__main__":
    app = QApplication()
    mainwindow = mw()
    mainwindow.show()

    sys.exit(app.exec())
