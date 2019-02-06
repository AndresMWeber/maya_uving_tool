from functools import wraps
from contextlib import contextmanager
from itertools import chain


class UVInterface(object):
    name = None
    transform = None
    shape = None
    uv = 'uv'
    bbox = 'bbox'
    dirty_callback = None
    delete_callback = None
    remove_callbacks = None

    @staticmethod
    def get_api_object(node):
        raise NotImplementedError

    @staticmethod
    def dcc_main_window(*args, **kwargs):
        raise NotImplementedError

    @staticmethod
    def defer_eval(*args):
        raise NotImplementedError

    @staticmethod
    def combine_dicts(dicts):
        result = {}
        all_sub_keys = set(chain.from_iterable([d.keys() for d in dicts]))
        for sub_key in all_sub_keys:
            for d in dicts:
                try:
                    result.setdefault(sub_key, []).append(d[sub_key])
                except KeyError:
                    pass
        return result

    @classmethod
    def undoable_decorator(cls, fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            cls.undo_chunk(True)
            return fn(*args, **kwargs)
        cls.undo_chunk(False)
        return wrapper

    @classmethod
    def pause_viewport_decorator(cls, fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            cls.pause_viewport(True)
            result = fn(*args, **kwargs)
            cls.pause_viewport(False)
            return result
        return wrapper

    @classmethod
    def maintain_selection_decorator(cls, fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            sel = cls.get_selection()
            result = fn(*args, **kwargs)
            cls.set_selection(sel)
            return result
        return wrapper

    @staticmethod
    def undo_chunk(state, *args, **kwargs):
        raise NotImplementedError

    @staticmethod
    def pause_viewport(*args, **kwargs):
        raise NotImplementedError

    @classmethod
    def updated_uv_data(cls, uv_data):
        raise NotImplementedError

    @staticmethod
    def get_uv_data(mesh):
        raise NotImplementedError

    @classmethod
    def combine_shells(uv_shells):
        raise NotImplementedError

    @staticmethod
    def get_uv_editors(*args, **kwargs):
        raise NotImplementedError

    @staticmethod
    def get_selection(*args, **kwargs):
        raise NotImplementedError

    @staticmethod
    def set_selection(objects, **kwargs):
        raise NotImplementedError
