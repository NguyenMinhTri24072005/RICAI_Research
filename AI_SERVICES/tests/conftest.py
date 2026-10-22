# -*- coding: utf-8 -*-
"""
Pytest configuration for AI_SERVICES test suite.
Initializes platform caching and environment flags to ensure reliable test execution.
"""
import os
import platform
import sys

# Cache platform.uname on Windows to prevent WMI 0x8007000e fatal exceptions during pytest session startup
if sys.platform == "win32" and getattr(platform, "_uname_cache", None) is None:
    try:
        winver = sys.getwindowsversion()
        platform._uname_cache = platform.uname_result(
            system="Windows",
            node=os.environ.get("COMPUTERNAME", "localhost"),
            release=str(winver.major),
            version=f"{winver.major}.{winver.minor}.{winver.build}",
            machine=os.environ.get("PROCESSOR_ARCHITECTURE", "AMD64"),
        )
    except Exception:
        pass

# Ensure headless matplotlib and PyTorch backend for Keras
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("KERAS_BACKEND", "torch")

