from PySide6.QtWidgets import QGraphicsView

class contourviewer(QGraphicsView):
    def __init__(self,parent):
        super().__init__(parent)
        # self.setScene(QGraphicsScene(self))
        self.setTransformationAnchor(self.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event):
        angle = event.angleDelta().y()
        zoomFactor = 1 + (angle / 1000)
        self.scale(zoomFactor, zoomFactor)
        print(angle)