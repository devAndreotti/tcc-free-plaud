"""Resolve Windows native libraries from this environment, not unrelated PATH DLLs."""

import ctypes
import os
from functools import lru_cache
from importlib.util import find_spec
from pathlib import Path


@lru_cache(maxsize=2)
def prepare_native_libraries(kind: str) -> tuple:
    if os.name != "nt":
        return ()
    package = "onnxruntime" if kind == "onnx" else "torch"
    spec = find_spec(package)
    if spec is None or spec.origin is None:
        return ()
    directory = Path(spec.origin).parent / ("capi" if kind == "onnx" else "lib")
    if not directory.is_dir():
        return ()
    names = (
        ["onnxruntime.dll"]
        if kind == "onnx"
        else ["cublasLt64_12.dll", "cublas64_12.dll", "cudnn64_9.dll"]
    )
    # Retain directory and DLL handles for the lifetime of the inference process.
    handles = [os.add_dll_directory(str(directory))]
    handles.extend(
        ctypes.WinDLL(str(directory / name))
        for name in names
        if (directory / name).is_file()
    )
    return tuple(handles)
