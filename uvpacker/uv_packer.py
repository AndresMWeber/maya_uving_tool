from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from PySide2 import QtCore, QtGui, QtWidgets
from pymel.core import UndoChunk
import maya.cmds as mc
import maya.mel as mel
from itertools import chain
import maya.api.OpenMaya as om
from pprint import pprint

def pause_refresh_maintain_selection(func):
    def wrapper(*args, **kwargs):
        mc.refresh(su=True)
        selection = mc.ls(sl=True)
        result = func(*args, **kwargs)
        mc.select(selection, r=True)
        mc.refresh(su=False)
        return result
    return wrapper


class Settings(object):
    NUM_BLOCKS_X = 10
    NUM_BLOCKS_Y = 10
    WIDTH = 30
    HEIGHT = 30
    TOTAL_WIDTH = NUM_BLOCKS_X * WIDTH
    TOTAL_HEIGHT = NUM_BLOCKS_Y * HEIGHT
    ACTIVE_FILL_COLOR = QtGui.QColor(5, 200, 10, 25)
    INACTIVE_FILL_COLOR = QtGui.QColor(200, 100, 150, 25)
    UV_STROKE_COLOR = QtGui.QColor(200, 200, 200, 80)
    UV_STROKE_WIDTH = 0.01
    GRID_STROKE_COLOR = QtGui.QColor(250, 250, 250, 40)


class UVFunctions(object):
    @staticmethod
    @pause_refresh_maintain_selection
    def get_uv_shells(mesh, progress_bar):
        with UndoChunk():
            shells = {}
            shapes = mc.listRelatives(mesh, s=True, c=True)
            total_uvs = 0
            if shapes:
                for shape in shapes:
                    shells[shape] = []
                    uvs = mc.ls(shape + '.map[:]', fl=True)
                    skip_uvs = set()
                    num_uvs = len(uvs)

                    for uv_index, uv in enumerate(uvs):
                        if uv not in skip_uvs:
                            mc.select(uv, r=True)
                            mel.eval('polySelectBorderShell 0')
                            shell = mc.ls(sl=True, fl=True)
                            bbox = mc.polyEvaluate(boundingBoxComponent2d=True)
                            skip_uvs = skip_uvs.union(set(shell))
                            shells[shape].append({'UVS': shell, 'BBOX': bbox})
                        progress_bar.setValue((float(uv_index) / float(num_uvs)) * 100.0)
                        total_uvs += num_uvs
            progress_bar.setValue(100)
            return shells, total_uvs

    @staticmethod
    def select(selection, **kwargs):
        selection = [sel if mc.objectType(sel) == 'transform' else mc.listRelatives(sel, p=True)[0] for sel in
                     selection]
        mc.select(selection, **kwargs)

    @staticmethod
    def select_uv_shells(uv_shells):
        uvs = list(chain.from_iterable(uv_shells))
        mc.select(uvs, r=True)

    @staticmethod
    def visible_uv_editors(self):
        return list(set(mc.getPanel(sty='polyTexturePlacementPanel')) & set(mc.getPanel(vis=True)))

    def get_all_selected_uvs(self):
        if self.selected_uvs == mc.ls(sl=True, fl=True):
            return mc.ls(mc.listRelatives(self.selected_uvs[0], p=True)[0]+'.map[:]', fl=True)
        return mc.ls(mc.ls(sl=True, type='transform')[0]+'.map[:]', fl=True)

    @property
    def selected_uvs(self):
        return [uv for uv in mc.ls(sl=True, fl=True) if '.map' in uv]

    @pause_refresh_maintain_selection
    def get_updated_uvs(self, uv_data):
        updated_uv_entries = [uv_entry for uv_entry in uv_data if set(uv_entry.get('UVS')) & set(self.selected_uvs)]

        for updated_uv_entry in updated_uv_entries:
            mc.select(updated_uv_entry['UVS'], r=True)
            mel.eval('polySelectBorderShell 0')
            bbox = mc.polyEvaluate(boundingBoxComponent2d=True)
            updated_uv_entry['BBOX'] = bbox

        return updated_uv_entries


class QStrokeRect(QtWidgets.QGraphicsRectItem):
    def __init__(self, parent=None):
        super(QStrokeRect, self).__init__(parent)
        self.strokeWidth = Settings.UV_STROKE_WIDTH
        self.setPen(QtGui.QPen(Settings.UV_STROKE_COLOR, 0, QtCore.Qt.SolidLine))
        self.setFlags(QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.brush = QtGui.QBrush(Settings.INACTIVE_FILL_COLOR)
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
        self.setFixedSize(Settings.WIDTH * Settings.NUM_BLOCKS_X, Settings.HEIGHT * Settings.NUM_BLOCKS_Y)
        self.setSceneRect(0, 0, Settings.TOTAL_WIDTH, Settings.TOTAL_HEIGHT)
        self.origin = None
        self.canZoom = True
        self.canPan = True
        self.zoomStack = []
        self.rubber_band = QtWidgets.QRubberBand(QtWidgets.QRubberBand.Rectangle, self)
        self.setMouseTracking(True)
        self.aspectRatioMode = QtCore.Qt.KeepAspectRatio
        """
        initial_rect = QtCore.QRect(0.0,
                                    Settings.TOTAL_HEIGHT-Settings.WIDTH*4,
                                    Settings.WIDTH*4,
                                    Settings.HEIGHT*4)
        initial_rect = self.mapToScene(initial_rect).boundingRect().toRect()
        self.fitInView(initial_rect, self.aspectRatioMode)
        """
        self.default_view()
        self.initial_fit = True

    def default_view(self):
        vert_scroll = self.verticalScrollBar()
        horiz_scroll = self.horizontalScrollBar()
        vert_scroll.setValue(vert_scroll.maximum())
        horiz_scroll.setValue(horiz_scroll.minimum())

    def resizeEvent(self, event):
        # matrix = QtGui.QTransform(1, 0, 0, 0, 1, 0, 0, 0, 1)
        # matrix.scale(Settings.TOTAL_HEIGHT / self.sceneRect().width(), Settings.TOTAL_HEIGHT/ self.sceneRect().height())
        # self.setTransform(matrix)
        if self.initial_fit:
            self.fitInView(self.grid_scene.sceneRect(), QtCore.Qt.KeepAspectRatio)
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
        viewportRect = QtCore.QRect(0, 0, self.viewport().width(), self.viewport().height())
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
            self.fitInView(self.zoomStack[-1], self.aspectRatioMode)  # Show zoomed rect (ignore aspect ratio).
            if self.grid_scene.rects:
                adjusted_viewport_size = self.visibleRect
                scale_value = adjusted_viewport_size.width() / previous_viewport_size.width()
                self.grid_scene.set_rect_widths(self.grid_scene.get_rect_widths() * scale_value)

        else:
            self.zoomStack = []  # Clear the zoom stack (in case we got here because of an invalid zoom).
            self.fitInView(self.sceneRect(), self.aspectRatioMode)  # Show entire image (use current aspect ratio mode).

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
                viewBBox = self.zoomStack[-1] if len(self.zoomStack) else self.sceneRect()
                selectionBBox = self.grid_scene.selectionArea().boundingRect().intersected(viewBBox)
                self.grid_scene.setSelectionArea(QtGui.QPainterPath())  # Clear current selection area.
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
        color = Settings.INACTIVE_FILL_COLOR
        if select:
            color = Settings.ACTIVE_FILL_COLOR

        for rect in rects:
            rect.setBrush(QtGui.QBrush(color))
            rect.update()

    def rubberband_release(self, release_event):
        if self.rubber_band.isVisible():
            self.rubber_band.hide()
            self.toggle_rects([child.get('RECT') for child in self.grid_scene.data], select=False)
            rect = self.mapToScene(self.rubber_band.geometry()).boundingRect().toRect()
            selected = [child for child in self.grid_scene.data
                        if rect.intersects(child.get('RECT').sceneBoundingRect().toRect())]
            UVFunctions.select_uv_shells([child.get('UVS') for child in selected])
            self.toggle_rects([child.get('RECT') for child in selected])

    def rubberband_move(self, move_event):
        if self.rubber_band.isVisible():
            selection_rect = QtCore.QRect()
            point = move_event.pos()
            selection_rect.setX(point.x() if point.x() < self.origin.x() else self.origin.x())
            selection_rect.setY(point.y() if point.y() < self.origin.y() else self.origin.y())
            selection_rect.setWidth(abs(point.x() - self.origin.x()))
            selection_rect.setHeight(abs(point.y() - self.origin.y()))

            self.rubber_band.setGeometry(selection_rect)
            move_event.accept()
        return QtWidgets.QGraphicsView.mouseMoveEvent(self, move_event)


class GridScene(QtWidgets.QGraphicsScene):
    def __init__(self, *args, **kwargs):
        super(GridScene, self).__init__(*args, **kwargs)
        self.lines = []

        self.draw_grid()
        self.set_opacity(0.3)
        # self.aspectRatioMode = QtCore.Qt.KeepAspectRatio
        self.data = []

    @property
    def rects(self):
        return [uv_entry.get('RECT') for uv_entry in self.data if uv_entry.get('RECT')]

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
        items_rect = QtCore.QRectF(bbox_x_min, bbox_y_min, bbox_x_max - bbox_x_min, bbox_y_max - bbox_y_min)
        return items_rect

    def draw_grid(self):
        width = Settings.NUM_BLOCKS_X * Settings.WIDTH
        height = Settings.NUM_BLOCKS_Y * Settings.HEIGHT
        self.setSceneRect(0, 0, width, height)
        self.setItemIndexMethod(QtWidgets.QGraphicsScene.NoIndex)

        pen = QtGui.QPen(Settings.GRID_STROKE_COLOR, 1, QtCore.Qt.SolidLine)

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

    def update_rect_from_bbox_for_uv_data(self, uv_data):
        scale_x = Settings.WIDTH * Settings.NUM_BLOCKS_X
        scale_y = Settings.HEIGHT * Settings.NUM_BLOCKS_Y
        if self.data and uv_data:
            for uv_entry in self.data:
                for uv_data_item in uv_data:
                    if uv_data_item.get('UVS') == uv_entry.get('UVS'):
                        bbox = uv_entry.get('BBOX', (0, 0, 0, 0))
                        x_minmax, y_minmax = bbox
                        min_x, max_x = x_minmax
                        min_y, max_y = y_minmax
                        width = max_x - min_x
                        height = max_y - min_y

                        rect_values = [val * Settings.WIDTH for val in [min_x, max_y, width, height]]
                        rect_values[1] = scale_y - rect_values[1]
                        x, y, width, height = rect_values
                        if uv_entry.get('RECT'):
                            self.removeItem(uv_entry.get('RECT'))
                        rect = QStrokeRect(QtCore.QRectF(x, y, width, height))
                        uv_entry['RECT'] = rect
                        break

    def draw_uv_bounding_boxes(self, uv_data):
        self.clear()
        self.data = uv_data
        self.update_rect_from_bbox_for_uv_data(self.data)

        for uv_entry in self.data:
            self.addItem(uv_entry.get('RECT'))


class DeselectableListView(QtWidgets.QListView):
    clear_selection = QtCore.Signal(bool)

    def mousePressEvent(self, event):
        if not self.indexAt(event.pos()).isValid():
            self.clearSelection()
            self.clear_selection.emit(True)
        super(DeselectableListView, self).mousePressEvent(event)


class UVPackerUI(MayaQWidgetDockableMixin, QtWidgets.QWidget):
    def __init__(self):
        super(UVPackerUI, self).__init__()
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        self.setWindowFlags(QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        # self.setWindowFlags(QtCore.Qt.CustomizeWindowHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setObjectName('UV_PACKING_TOOL')
        self.setWindowTitle('UV Packing Tool')
        self.headers = ['Shape node', 'Number of Shells']
        self.previous_selection = []
        self.data = {}
        self.callbacks = []
        self.num_computed_uvs = 0

        self.layout()
        self.connect()
        self.style()

    @classmethod
    def create(cls):
        global window_instance
        try:
            window_instance.close()
        except (NameError, RuntimeError, TypeError):
            pass
        instance = cls()
        instance.show()
        return instance

    def layout(self):
        layout = QtWidgets.QGridLayout()

        self.shapes_qlistview = DeselectableListView()
        self.shapes_qlistview.setWindowTitle('Shapes List')
        self.shapes_qlistview.setMinimumSize(80, 250)
        self.shapes_qlistview.setSelectionMode(QtWidgets.QListView.MultiSelection)

        self.shapes_model = QtGui.QStandardItemModel(self.shapes_qlistview)
        self.shapes_qlistview.setModel(self.shapes_model)

        self.get_shells_btn = QtWidgets.QPushButton("Get UV Shells")
        self.test_btn = QtWidgets.QPushButton("Get updated UVs")

        self.progress_bar = QtWidgets.QProgressBar()
        self.grid_widget = GridView()

        layout.addWidget(self.shapes_qlistview)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.get_shells_btn)
        layout.addWidget(self.test_btn)

        app_widget = QtWidgets.QWidget()
        app_widget.setLayout(layout)
        horizontal_layout = QtWidgets.QHBoxLayout()
        horizontal_layout.addWidget(app_widget)
        horizontal_layout.addWidget(self.grid_widget)
        self.setLayout(horizontal_layout)
        self.grid_widget.default_view()

    def style(self):
        pass

    def connect(self):
        self.get_shells_btn.clicked.connect(self.refresh_ui)
        self.test_btn.clicked.connect(self.update_changed_uvs)
        self.shapes_qlistview.clicked.connect(self.on_shapes_view_clicked)
        self.shapes_qlistview.clear_selection.connect(self.grid_widget.grid_scene.clear)
        self.shapes_qlistview.clear_selection.connect(self.deselected_grid_view)

    """
    @staticmethod
    def get_maya_window():
        win = QtWidgets.QApplication.activeWindow()
        parent = win
        while parent is not None:
            parent = win.parent()
        return parent
    """

    def deselected_grid_view(self):
        self.previous_selection = []

    def on_shapes_view_clicked(self, index):
        current_selection = self.shapes_qlistview.selectedIndexes()
        if index not in self.previous_selection or index not in current_selection:
            self.previous_selection = current_selection or []
            self.update_grid_view()
        UVFunctions.select([sel.data() for sel in current_selection], r=True)

    def update_changed_uvs(self, *args):
        if self.num_computed_uvs != UVFunctions().get_all_selected_uvs():
            print 'detecting fuck up, refreshing UI completely.'
            self.refresh_ui()
            return

        if UVFunctions.visible_uv_editors:
            print 'uv change detected.'
            changed_uv_sets = UVFunctions.get_updated_uvs(self.selected_uv_data)
            self.grid_widget.grid_scene.update_rect_from_bbox_for_uv_data(changed_uv_sets)
            self.grid_widget.grid_scene.draw_uv_bounding_boxes(self.selected_uv_data)

    def update_grid_view(self):
        self.grid_widget.grid_scene.draw_uv_bounding_boxes(self.selected_uv_data)
        self.grid_widget.frame_items()

    @property
    def selected_uv_data(self):
        if self.previous_selection:
            return [i for i in
                    chain.from_iterable([self.data.get(selection.data()) for selection in self.previous_selection])]
        return []

    @staticmethod
    def combine_uv_dicts(dictionaries):
        d = {}
        mega_keys = set(chain.from_iterable([i_dict.keys() for i_dict in dictionaries]))
        for key in mega_keys:
            for i_dict in dictionaries:
                try:
                    d.setdefault(key, []).append(i_dict[key])
                except KeyError:
                    pass
        return d

    def refresh_data(self, mesh):
        self.data, self.num_computed_uvs = UVFunctions.get_uv_shells(mesh, self.progress_bar)
        self.progress_bar.reset()

    def refresh_ui(self):
        transforms = [transform for transform in mc.ls(sl=True, type='transform')]
        for transform in transforms:
            self.refresh_data(transform)
            self.shapes_model.clear()

            for shape in self.data:
                item = QtGui.QStandardItem(shape)
                self.shapes_model.appendRow(item)
                self.createNodeCallback(shape)
            self.update_grid_view()

    def createNodeCallback(self, shape_node):
        sel = om.MSelectionList()
        sel.add(shape_node)
        mobject = sel.getDagPath(0).node()
        self.callbacks.append(om.MNodeMessage.addNodeDirtyCallback(mobject, lambda e, v:mc.evalDeferred(self.update_changed_uvs)))

    def closeEvent(self, event):
        om.MMessage.removeCallbacks(self.callbacks)
        try:
            super(UVPackerUI, self).closeEvent(event)
        except TypeError:
            pass

window_instance = UVPackerUI.create()
