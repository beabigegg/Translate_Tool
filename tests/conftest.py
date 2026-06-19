"""
Pre-load CUDA runtime libraries so onnxruntime-gpu can find them.
onnxruntime-gpu uses dlopen() lazily at C-extension init time;
loading via ctypes first puts the .so in the process's dlopen cache.
"""
import ctypes
import os
import site


def _preload_cuda_libs() -> None:
    sp = site.getsitepackages()[0]
    libs = [
        os.path.join(sp, "nvidia", "cu13", "lib", "libcudart.so.13"),
        os.path.join(sp, "nvidia", "cuda_runtime", "lib", "libcudart.so.12"),
    ]
    for path in libs:
        if os.path.exists(path):
            try:
                ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)
            except OSError:
                pass


_preload_cuda_libs()
