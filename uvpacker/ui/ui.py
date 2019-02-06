from functools import partial

from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from PySide2 import QtCore, QtGui, QtWidgets

from .settings import Settings
from .widgets import GridView, DeselectableListView

dcc = Settings.PLUGIN


class UVPackerUI(MayaQWidgetDockableMixin, QtWidgets.QWidget):
    def __init__(self):
        super(UVPackerUI, self).__init__()
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                           QtWidgets.QSizePolicy.Preferred)
        self.setWindowFlags(QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setObjectName('UV_PACKING_TOOL')
        self.setWindowTitle('UV Packing Tool')
        self.headers = ['Shape node', 'Number of Shells']

        self.selected_indices = []
        self.uv_data = {}
        self.uv_count = 0

        self.callbacks = {}
        self.refresh_callbacks = [self.refresh_ui]

        self.layout()
        self.connect()

    def selected_row_labels(self):
        return [row_index.data() for row_index in self.v_shapes_list.selectedIndexes()]
    
    def selected_rows_uv_data(self):
        return {xform: self.uv_data.get(xform) for xform in self.selected_row_labels()}

    @classmethod
    def create(cls):
        global window_instance
        try:
            window_instance.close()
        except (NameError, RuntimeError, TypeError):
            pass
        window_instance = cls()
        try:
            window_instance.show(dockable=True)
        except RuntimeError:
            pass
            
        return window_instance

    def layout(self):
        self.g_layout = QtWidgets.QGridLayout()

        self.v_shapes_list = DeselectableListView()
        self.v_shapes_list.setWindowTitle('Shapes List')
        self.v_shapes_list.setMinimumSize(80, 250)
        self.v_shapes_list.setSelectionMode(QtWidgets.QListView.MultiSelection)

        self.i_transforms = QtGui.QStandardItemModel(self.v_shapes_list)
        self.v_shapes_list.setModel(self.i_transforms)

        self.b_get_shells = QtWidgets.QPushButton("Get UV Shells")
        self.b_update_uvs = QtWidgets.QPushButton("Get updated UVs")

        self.pbar_progress = QtWidgets.QProgressBar()
        self.w_grid = GridView()

        self.g_layout.addWidget(self.v_shapes_list)
        self.g_layout.addWidget(self.pbar_progress)
        self.g_layout.addWidget(self.b_get_shells)
        self.g_layout.addWidget(self.b_update_uvs)

        self.w_app = QtWidgets.QWidget()
        self.w_app.setLayout(self.g_layout)

        self.h_layout = QtWidgets.QHBoxLayout()
        self.h_layout.addWidget(self.w_app)
        self.h_layout.addWidget(self.w_grid)

        self.setLayout(self.h_layout)
        self.w_grid.default_view()

    def connect(self):
        self.b_get_shells.clicked.connect(self.ui_dirty)
        self.b_update_uvs.clicked.connect(self.update_changed_uvs)
        self.v_shapes_list.clicked.connect(self.on_shapes_view_clicked)
        self.v_shapes_list.clear_selection.connect(
            self.w_grid.grid_scene.clear)
        self.v_shapes_list.clear_selection.connect(self.on_deselect_grid_view)

    def on_deselect_grid_view(self):
        self.selected_indices = []

    def on_shapes_view_clicked(self, index):
        self.update_grid_view()

    def update_changed_uvs(self, *args):
        self.ui_dirty()
        self.uv_data, self.uv_count = dcc.update_uv_data(self.uv_data)
        self.w_grid.grid_scene.update_rect(self.uv_data)
        self.w_grid.grid_scene.draw_uv_bboxes(self.selected_rows_uv_data())

    def update_grid_view(self):
        self.w_grid.grid_scene.draw_uv_bboxes(self.selected_rows_uv_data())
        self.w_grid.frame_items()

    def update_uv_data_from_transform(self, transform):
        self.uv_data, self.uv_count = dcc.get_uv_data([transform], uv_data=self.uv_data)
        self.pbar_progress.reset()

    def register_refresh_callback(self, callback, *args, **kwargs):
        self.refresh_callbacks.append(partial(callback, *args, **kwargs))

    def ui_dirty(self):
        for callback in self.refresh_callbacks:
            callback()

    def refresh_ui(self):
        for transform in dcc.get_selection(type=dcc.transform):
            self.update_uv_data_from_transform(transform)
        
        self.i_transforms.clear()

        for shape in self.uv_data:
            if shape != 'uv_total':
                item = QtGui.QStandardItem(shape)
                self.i_transforms.appendRow(item)
                if not self.callbacks.get(shape):
                    self.create_node_callbacks(shape)

        self.update_grid_view()

    def create_node_callbacks(self, node):
        api_object = dcc.get_api_object(node)

        dirty_callback = lambda e, v: dcc.defer_eval(self.update_changed_uvs)
        deleted_callback = lambda e, v: dcc.defer_eval(partial(self.remove_node_callback, node))

        self.callbacks[node] = [dcc.dirty_callback(api_object, dirty_callback), 
                                dcc.delete_callback(api_object, deleted_callback)]

    def remove_node_callbacks(self, nodes):
        dcc.remove_callbacks([callback for node in nodes for callback in self.callbacks[node]])

    def closeEvent(self, event):
        self.remove_node_callbacks(self.callbacks.keys())
        try:
            super(UVPackerUI, self).closeEvent(event)
        except TypeError:
            pass
