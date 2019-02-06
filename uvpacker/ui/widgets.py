from PySide2 import QtCore, QtGui, QtWidgets
from settings import Settings

dcc = Settings.PLUGIN

ACTIVE_FILL_COLOR = QtGui.QColor(5, 200, 10, 25)
INACTIVE_FILL_COLOR = QtGui.QColor(200, 100, 150, 25)
UV_STROKE_COLOR = QtGui.QColor(200, 200, 200, 80)
GRID_STROKE_COLOR = QtGui.QColor(250, 250, 250, 40)


class QStrokeRect(QtWidgets.QGraphicsRectItem):
    def __init__(self, parent=None):
        super(QStrokeRect, self).__init__(parent)
        self.strokeWidth = Settings.UV_STROKE_WIDTH
        self.setPen(QtGui.QPen(UV_STROKE_COLOR, 0, QtCore.Qt.SolidLine))
        self.setFlags(QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.brush = QtGui.QBrush(INACTIVE_FILL_COLOR)
        self.setBrush(self.brush)

    def setStrokeWidth(self, strokeWidth):
        self.strokeWidth = strokeWidth

    def shape(self):
        path = QtGui.QPainterPath()
        path.addRect(self.boundingRect())
        pStroker = QtGui.QPainterPathStroker()
        pStroker.setWidth(self.strokeWidth)
        return pStroker.createStroke(path)


class GridView(QtWidgets.QGraphicsView):
    leftMouseButtonPressed = QtCore.Signal(float, float)
    rightMouseButtonPressed = QtCore.Signal(float, float)
    leftMouseButtonReleased = QtCore.Signal(float, float)
    rightMouseButtonReleased = QtCore.Signal(float, float)
    leftMouseButtonDoubleClicked = QtCore.Signal(float, float)
    rightMouseButtonDoubleClicked = QtCore.Signal(float, float)

    def __init__(self, *args, **kwargs):
        super(GridView, self).__init__(*args, **kwargs)
        self.grid_scene = GridScene()
        self.setScene(self.grid_scene)
        self.setFixedSize(Settings.WIDTH * Settings.NUM_BLOCKS_X,
                          Settings.HEIGHT * Settings.NUM_BLOCKS_Y)
        self.setSceneRect(0, 0, Settings.TOTAL_WIDTH, Settings.TOTAL_HEIGHT)
        self.origin = None
        self.canZoom = True
        self.canPan = True
        self.zoomStack = []
        self.rubber_band = QtWidgets.QRubberBand(
            QtWidgets.QRubberBand.Rectangle, self)
        self.setMouseTracking(True)
        self.aspectRatioMode = QtCore.Qt.KeepAspectRatio
        self.default_view()
        self.initial_fit = True

    def default_view(self):
        vert_scroll = self.verticalScrollBar()
        horiz_scroll = self.horizontalScrollBar()
        vert_scroll.setValue(vert_scroll.maximum())
        horiz_scroll.setValue(horiz_scroll.minimum())

    def resizeEvent(self, event):
        if self.initial_fit:
            self.fitInView(self.grid_scene.sceneRect(),
                           QtCore.Qt.KeepAspectRatio)
            self.initial_fit = False
        super(GridView, self).resizeEvent(event)

    @property
    def alt_pressed(self):
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        if modifiers == QtCore.Qt.AltModifier:
            return True
        return False

    @property
    def visibleRect(self):
        viewportRect = QtCore.QRect(
            0, 0, self.viewport().width(), self.viewport().height())
        return QtCore.QRectF(self.mapToScene(viewportRect).boundingRect())

    def frame_items(self):
        items_rect = self.grid_scene.focus_rect()
        adjustment = Settings.TOTAL_HEIGHT / Settings.NUM_BLOCKS_X
        items_rect.adjust(-adjustment, -adjustment, adjustment, adjustment)
        self.fitInView(items_rect, self.aspectRatioMode)

    def mousePressEvent(self, event):
        if self.alt_pressed:
            self.zoom_press(event)
        else:
            self.rubberband_press(event)
        QtWidgets.QGraphicsView.mousePressEvent(self, event)

    def mouseReleaseEvent(self, event):
        if self.alt_pressed:
            self.zoom_release(event)
        else:
            self.rubberband_release(event)
        QtWidgets.QWidget.mouseReleaseEvent(self, event)

    def mouseMoveEvent(self, event):
        QtWidgets.QGraphicsView.mouseMoveEvent(self, event)
        if not self.alt_pressed:
            self.rubberband_move(event)

    def mouseDoubleClickEvent(self, event):
        """ Show entire image.
        """
        scenePos = self.mapToScene(event.pos())
        if event.button() == QtCore.Qt.LeftButton:
            self.leftMouseButtonDoubleClicked.emit(scenePos.x(), scenePos.y())
        elif event.button() == QtCore.Qt.RightButton:
            if self.canZoom:
                self.zoomStack = []  # Clear zoom stack.
                self.updateViewer()
            self.rightMouseButtonDoubleClicked.emit(scenePos.x(), scenePos.y())
        QtWidgets.QGraphicsView.mouseDoubleClickEvent(self, event)

    def updateViewer(self):
        if len(self.zoomStack) and self.sceneRect().contains(self.zoomStack[-1]):
            previous_viewport_size = self.visibleRect
            # Show zoomed rect (ignore aspect ratio).
            self.fitInView(self.zoomStack[-1], self.aspectRatioMode)
            if self.grid_scene.rects:
                adjusted_viewport_size = self.visibleRect
                scale_value = adjusted_viewport_size.width() / previous_viewport_size.width()
                self.grid_scene.set_rect_widths(
                    self.grid_scene.get_rect_widths() * scale_value)

        else:
            # Clear the zoom stack (in case we got here because of an invalid zoom).
            self.zoomStack = []
            # Show entire image (use current aspect ratio mode).
            self.fitInView(self.sceneRect(), self.aspectRatioMode)

    def zoom_press(self, press_event):
        scene_pos = self.mapToScene(press_event.pos())
        if press_event.button() == QtCore.Qt.LeftButton:
            if self.canPan:
                self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
            self.leftMouseButtonPressed.emit(scene_pos.x(), scene_pos.y())

        elif press_event.button() == QtCore.Qt.RightButton:
            if self.canZoom:
                self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)
            self.rightMouseButtonPressed.emit(scene_pos.x(), scene_pos.y())

    def zoom_release(self, release_event):
        QtWidgets.QGraphicsView.mouseReleaseEvent(self, release_event)
        scenePos = self.mapToScene(release_event.pos())
        if release_event.button() == QtCore.Qt.LeftButton:
            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
            self.leftMouseButtonReleased.emit(scenePos.x(), scenePos.y())

        elif release_event.button() == QtCore.Qt.RightButton:
            if self.canZoom:
                viewBBox = self.zoomStack[-1] if len(
                    self.zoomStack) else self.sceneRect()
                selectionBBox = self.grid_scene.selectionArea().boundingRect().intersected(viewBBox)
                # Clear current selection area.
                self.grid_scene.setSelectionArea(QtGui.QPainterPath())
                if selectionBBox.isValid() and (selectionBBox != viewBBox):
                    self.zoomStack.append(selectionBBox)
                    self.updateViewer()
            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
            self.rightMouseButtonReleased.emit(scenePos.x(), scenePos.y())

    def rubberband_press(self, press_event):
        self.origin = press_event.pos()  # self.mapToScene(press_event.pos()).toPoint()
        self.rubber_band.setGeometry(QtCore.QRect(self.origin, QtCore.QSize()))
        self.rubber_band.show()

    def toggle_rects(self, rects, select=True):
        color = INACTIVE_FILL_COLOR
        if select:
            color = ACTIVE_FILL_COLOR

        for rect in rects:
            rect.setBrush(QtGui.QBrush(color))
            rect.update()

    def rubberband_release(self, release_event):
        if self.rubber_band.isVisible():
            self.rubber_band.hide()
            self.toggle_rects(self.grid_scene.rects, select=False)
            rect = self.mapToScene(
                self.rubber_band.geometry()).boundingRect().toRect()

            selected_shapes = [shape for shape in self.grid_scene.bboxes if rect.intersects(
                self.grid_scene.bboxes[shape].sceneBoundingRect().toRect())]

            dcc.set_selection([shape+'.map[:]' for shape in selected_shapes])
            self.toggle_rects([self.grid_scene.rects.bboxes[shape]
                               for shape in selected_shapes])

    def rubberband_move(self, move_event):
        if self.rubber_band.isVisible():
            selection_rect = QtCore.QRect()
            point = move_event.pos()
            selection_rect.setX(point.x() if point.x() <
                                self.origin.x() else self.origin.x())
            selection_rect.setY(point.y() if point.y() <
                                self.origin.y() else self.origin.y())
            selection_rect.setWidth(abs(point.x() - self.origin.x()))
            selection_rect.setHeight(abs(point.y() - self.origin.y()))

            self.rubber_band.setGeometry(selection_rect)
            move_event.accept()
        return QtWidgets.QGraphicsView.mouseMoveEvent(self, move_event)


class GridScene(QtWidgets.QGraphicsScene):
    RECT = 'RECT'

    def __init__(self, *args, **kwargs):
        super(GridScene, self).__init__(*args, **kwargs)
        self.lines = []
        self.bboxes = {}
        self.draw_grid()
        self.set_opacity(0.3)

    @property
    def rects(self):
        return [self.bboxes[bbox] for bbox in self.bboxes]

    def focus_rect(self):
        bbox_y_max = 0
        bbox_x_max = 0
        bbox_y_min = Settings.TOTAL_HEIGHT
        bbox_x_min = Settings.TOTAL_WIDTH

        for rect in self.rects:
            bbox = rect.sceneBoundingRect()
            bbox_x_min = min(bbox_x_min, bbox.x())
            bbox_y_min = min(bbox_y_min, bbox.y())
            bbox_x_max = max(bbox_x_max, bbox.x() + bbox.width())
            bbox_y_max = max(bbox_y_max, bbox.y() + bbox.height())
        items_rect = QtCore.QRectF(
            bbox_x_min, bbox_y_min, bbox_x_max - bbox_x_min, bbox_y_max - bbox_y_min)
        return items_rect

    def draw_grid(self):
        width = Settings.NUM_BLOCKS_X * Settings.WIDTH
        height = Settings.NUM_BLOCKS_Y * Settings.HEIGHT
        self.setSceneRect(0, 0, width, height)
        self.setItemIndexMethod(QtWidgets.QGraphicsScene.NoIndex)

        pen = QtGui.QPen(GRID_STROKE_COLOR, 1, QtCore.Qt.SolidLine)

        for x in range(0, Settings.NUM_BLOCKS_X + 1):
            xc = x * Settings.WIDTH
            self.lines.append(self.addLine(xc, 0, xc, height, pen))

        for y in range(0, Settings.NUM_BLOCKS_Y + 1):
            yc = y * Settings.HEIGHT
            self.lines.append(self.addLine(0, yc, width, yc, pen))

    def set_rect_widths(self, value):
        for rect in self.rects:
            rect.setStrokeWidth(value)

    def get_rect_widths(self):
        for rect in self.rects:
            return rect.strokeWidth

    def set_visible(self, visible=True):
        for line in self.lines:
            line.setVisible(visible)

    def delete_grid(self):
        for line in self.lines:
            self.removeItem(line)
        del self.lines[:]

    def set_opacity(self, opacity):
        for line in self.lines:
            line.setOpacity(opacity)

    def clear(self):
        for rect in self.rects:
            self.removeItem(rect)

    def update_rect(self, uv_data):
        scale_x = Settings.WIDTH * Settings.NUM_BLOCKS_X
        scale_y = Settings.HEIGHT * Settings.NUM_BLOCKS_Y

        for xform in uv_data:
            for shape in uv_data[xform]:
                shape_uv_data = uv_data[xform][shape]

                bbox = shape_uv_data.get(dcc.bbox, (0, 0, 0, 0))
                x_minmax, y_minmax = bbox
                min_x, max_x = x_minmax
                min_y, max_y = y_minmax
                width = max_x - min_x
                height = max_y - min_y

                rect_values = [
                    val * Settings.WIDTH for val in [min_x, max_y, width, height]]
                rect_values[1] = scale_y - rect_values[1]
                x, y, width, height = rect_values

                if shape_uv_data.get(self.RECT):
                    self.removeItem(shape_uv_data[self.RECT])

                rect = QStrokeRect(QtCore.QRectF(x, y, width, height))
                shape_uv_data[self.RECT] = rect
                self.bboxes[shape] = rect

    def draw_uv_bboxes(self, uv_data):
        self.clear()
        self.update_rect(uv_data)

        for uv_entry in uv_data:
            self.addItem(uv_data[uv_entry].get(self.RECT))


class DeselectableListView(QtWidgets.QListView):
    clear_selection = QtCore.Signal(bool)

    def mousePressEvent(self, event):
        if not self.indexAt(event.pos()).isValid():
            self.clearSelection()
            self.clear_selection.emit(True)
        super(DeselectableListView, self).mousePressEvent(event)
