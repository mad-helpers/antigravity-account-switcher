# -*- coding: utf-8 -*-
"""Unified core package for Antigravity Account Switcher v3.0."""

VERSION = "3.0.0"

from . import cdp, quota, store, vault

__all__ = ["VERSION", "vault", "store", "quota", "cdp"]
