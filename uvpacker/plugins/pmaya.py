import maya.cmds as mc
import maya.mel as mel
from PySide2 import QtWidgets
import maya.api.OpenMaya as om

from contextlib import contextmanager
from itertools import chain
from interface import UVInterface


component_suffixes = ['.map', '.uv', '.vtx', '.e', '.f']


class MayaInterface(UVInterface):
    name = 'maya'
    transform = 'transform'
    shape = 'mesh'
    dirty_callback = om.MNodeMessage.addNodeDirtyCallback
    delete_callback = om.MNodeMessage.addNodeDestroyedCallback
    remove_callbacks = om.MMessage.removeCallbacks

    @classmethod
    def get_api_object(cls, node):
        try:
            sel = om.MSelectionList()
            sel.add(node)
            return sel.getDagPath(0).node()
        except RuntimeError:
            raise KeyError('Object %s does not exist in the DCC %s' % (node, cls.name))

    @staticmethod
    def dcc_main_window(*args, **kwargs):
        win=QtWidgets.QApplication.activeWindow()
        parent=win
        while parent is not None:
            parent=win.parent()
        return parent

    @staticmethod
    def undo_chunk(state, *args, **kwargs):
        return MayaRuntime.undo_chunk(state, *args, **kwargs)

    @staticmethod
    def pause_viewport(state, *args, **kwargs):
        return MayaRuntime.undo_chunk(state, *args, **kwargs)

    @staticmethod
    def defer_eval(*args):
        return MayaRuntime.defer_eval(*args)

    @classmethod
    def update_uv_data(cls, uv_data):
        needs_updating=[]

        for xform in uv_data:
            for shape in uv_data[xform]:
                data=uv_data[xform][shape]
                if len(MayaNode.wrap(shape).uvs) != len(data[cls.uv]):
                    needs_updating.append(xform)
                    break

        if not needs_updating:
            return False

        return cls.get_uv_data(needs_updating, uv_data=uv_data)

    @classmethod
    def get_uv_data(cls, xforms, uv_data=None):
        if uv_data is None:
            uv_data={}
        total_uvs=0

        for xform in xforms:
            for shape in MayaNode.wrap(xform).get_shapes():
                uv_data[xform]=uv_data.get(xform, {})
                uv_data[xform][shape]=uv_data[xform].get(shape, {})

                uvs=MayaNode.wrap(shape).uvs
                uv_data[xform][shape]={cls.uv: uvs,
                                         cls.bbox: mc.polyEvaluate(uvs, boundingBoxComponent2d=True)}

                total_uvs += len(uvs)
        return uv_data, total_uvs

    @classmethod
    def combine_shells(cls, uv_shells):
        return list(chain.from_iterable(uv_shells))

    @staticmethod
    def get_uv_editors(*args, **kwargs):
        return MayaRuntime.get_uv_editors(*args, **kwargs)

    @staticmethod
    def get_selection(*args, **kwargs):
        return MayaRuntime.get_selection(*args, **kwargs)

    @staticmethod
    def set_selection(objects, *args, **kwargs):
        return MayaRuntime.set_selection(objects, *args, **kwargs)


class MayaNode(object):
    def __init__(self, node):
        try:
            self._uuid=MayaRuntime.list_objects(node, uuid=True)[0]
        except IndexError:
            raise ValueError('Error retrieving uuid of node %s' % node)

    @classmethod
    def wrap(cls, node):
        if isinstance(node, cls.__class__):
            return node
        return cls(node)

    @property
    def node(self):
        return MayaRuntime.list_objects(self._uuid)[0]

    @property
    def type(self):
        return MayaRuntime.type(self.node)

    @property
    def uvs(self):
        return MayaRuntime.flatten_objects(self.node + '.map[:]')

    @property
    def is_shape(self):
        return self.is_type(MayaInterface.shape)

    @property
    def is_xform(self):
        return self.is_type(MayaInterface.transform)

    @property
    def is_component(self):
        return any(suffix in self.node for suffix in component_suffixes)

    @property
    def is_uv(self):
        return '.map' in self.node

    @property
    def is_edge(self):
        return '.e' in self.node

    @property
    def is_face(self):
        return '.f' in self.node

    @property
    def is_vertex(self):
        return '.vtx' in self.node

    def is_type(self, object_type):
        return MayaRuntime.type(self.node) == object_type

    def get_parent(self, **kwargs):
        return MayaRuntime.get_relatives(self.node, p=True, **kwargs)

    def get_children(self, **kwargs):
        return MayaRuntime.get_relatives(self.node, c=True, **kwargs)

    def get_shapes(self, **kwargs):
        return self.get_children(shapes=True)

    def __eq__(self, other):
        return self.node == other


class MayaRuntime(object):
    @classmethod
    def list_components(cls):
        return [cmpt for cmpt in cls.list_selection() if any(suffix in cmpt for suffix in component_suffixes)]

    @staticmethod
    def get_uv_editors(*args, **kwargs):
        return list(set(mc.getPanel(sty='polyTexturePlacementPanel')) & set(mc.getPanel(vis=True)))

    @staticmethod
    def undo_chunk(state, *args, **kwargs):
        if state:
            return mc.undoInfo(openChunk=True)
        else:
            return mc.undoInfo(closeChunk=True)

    @staticmethod
    def pause_viewport(state, *args, **kwargs):
        return mc.refresh(su=state)

    @staticmethod
    def get_selection(*args, **kwargs):
        return mc.ls(*args, sl=True, **kwargs)

    @staticmethod
    def set_selection(objects):
        return mc.select(objects, r=True)

    @staticmethod
    def list_objects(*args, **kwargs):
        return mc.ls(*args, **kwargs)

    @classmethod
    def list_selection(cls, **kwargs):
        return cls.list_objects(sl=True, fl=True, **kwargs)

    @classmethod
    def flatten_objects(cls, *args, **kwargs):
        return cls.list_objects(*args, fl=True, **kwargs)

    @staticmethod
    def type(node):
        return mc.objectType(node)

    @classmethod
    def is_type(cls, node, object_type):
        return cls.type(node) == object_type

    @classmethod
    def resolve_xform(cls, node, type=None):
        node=MayaNode.wrap(node)
        if node.is_xform:
            return node
        elif node.is_shape:
            return node.get_parent(type=MayaInterface.transform)
        return []

    @staticmethod
    def get_relatives(*args, **kwargs):
        return mc.listRelatives(*args, **kwargs)

    @staticmethod
    def get_parent(node, **kwargs):
        return MayaNode.wrap(node).get_parent(**kwargs)

    @staticmethod
    def get_children(node, **kwargs):
        return MayaNode.wrap(node).get_children(**kwargs)

    @classmethod
    def get_all_selected_uvs(cls):
        return [MayaNode.wrap(xform).uvs for xform in cls.list_xforms()]

    @classmethod
    def list_xforms(cls, **kwargs):
        return [cls.resolve_xform(o) for o in cls.list_objects(sl=True, fl=True, **kwargs) if cls.resolve_xform(o)]

    @staticmethod
    def defer_eval(*args):
        return mc.evalDeferred(*args)
