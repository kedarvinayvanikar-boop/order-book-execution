"""Optional pybind11 engine. Add the CMake build directory to PYTHONPATH."""

from importlib import import_module


def engine():
    try:
        return import_module("_lob_cpp")
    except ImportError as exc:
        raise RuntimeError("Build C++ bindings and set PYTHONPATH=build:src") from exc


def native_events(events):
    native = engine()
    return [native.Event(e.event_type, e.side, e.price, e.quantity) for e in events]
