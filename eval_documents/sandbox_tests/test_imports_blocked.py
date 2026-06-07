# Test: Blocked imports - copy/paste entire file at once
# Or run line by line interactively

# Test os - should fail
try:
    import os
    print("FAIL: os imported")
except ImportError:
    print("OK: os blocked")

# Test subprocess - should fail
try:
    import subprocess
    print("FAIL: subprocess imported")
except ImportError:
    print("OK: subprocess blocked")

# Test sys - should fail
try:
    import sys
    print("FAIL: sys imported")
except ImportError:
    print("OK: sys blocked")

# Test socket - should fail
try:
    import socket
    print("FAIL: socket imported")
except ImportError:
    print("OK: socket blocked")

# Test importlib - should fail
try:
    import importlib
    print("FAIL: importlib imported")
except ImportError:
    print("OK: importlib blocked")

# Test builtins - should fail
try:
    import builtins
    print("FAIL: builtins imported")
except ImportError:
    print("OK: builtins blocked")

# Test urllib - should fail
try:
    import urllib
    print("FAIL: urllib imported")
except ImportError:
    print("OK: urllib blocked")

# Test shutil - should fail
try:
    import shutil
    print("FAIL: shutil imported")
except ImportError:
    print("OK: shutil blocked")

# Test serialization modules - should fail
try:
    import pickle
    print("FAIL: pickle imported")
except ImportError:
    print("OK: pickle blocked")

try:
    import shelve
    print("FAIL: shelve imported")
except ImportError:
    print("OK: shelve blocked")

try:
    import marshal
    print("FAIL: marshal imported")
except ImportError:
    print("OK: marshal blocked")

# Test dynamic import via __import__ - should fail
try:
    mod = __import__('os')
    print("FAIL: dynamic __import__('os') succeeded")
except ImportError:
    print("OK: dynamic __import__ blocked")

# Test sub-module import of blocked package - should fail
try:
    import os.path
    print("FAIL: os.path sub-import succeeded")
except ImportError:
    print("OK: sub-import of blocked module blocked")

print("=== BLOCKED IMPORTS TEST COMPLETE ===")
