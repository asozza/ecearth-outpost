#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Folder definitions

Author: Alessandro Sozza (CNR-ISAC)
Date: July 2026
"""

import os
import sys
import yaml
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class ConfigError(RuntimeError):
    pass


CONFIG_FILENAME = "config.yml"
# repository root (ecearth-outpost/), for the editable install from src/ecpost/utils/config.py
REPO_ROOT = Path(__file__).resolve().parents[3]
REQUIRED_KEYS = ("base_path", "src_path", "data_path")


class Config:
    """Configure experiment paths giving priority to explicit args > file config (if exists) > error. """

    def __init__(self, base_path=None, src_path=None, data_path=None, config_path=None):
        explicit = {
            k: v for k, v in
            {"base_path": base_path, "src_path": src_path, "data_path": data_path}.items()
            if v
        }

        from_file, path = {}, None
        if len(explicit) < len(REQUIRED_KEYS):      # file config is only used if something is missing
            path = self._find_file(config_path)
            if path is not None:
                from_file = self._read_file(path)

        merged = {**from_file, **explicit}           # explicit paths take precedence over file config
        missing = [k for k in REQUIRED_KEYS if not merged.get(k)]
        if missing:
            if path is not None:
                where = f"they are not defined in {path}"
            else:
                searched = ", ".join(str(p) for p in self._default_files())
                where = f"no configuration file found (searched: {searched})"
            raise ConfigError(
                f"Missing paths: {missing}: {where}. "
                f"Define them in a {CONFIG_FILENAME} file, pass it with --config, or pass them as arguments."
            )

        self.base_path = Path(merged["base_path"])
        self.src_path = Path(merged["src_path"])
        self.data_path = Path(merged["data_path"])

    @staticmethod
    def _default_files():
        """Default configuration files, in order of priority: current directory, repository root"""
        return list(dict.fromkeys([Path.cwd() / CONFIG_FILENAME, REPO_ROOT / CONFIG_FILENAME]))

    @staticmethod
    def _find_file(config_path):
        """Configuration file to read: the explicit one (must exist) or the first default found, else None"""
        if config_path:                              # file explicitly specified: must exist
            path = Path(config_path)
            if not path.is_file():
                raise ConfigError(f"Config not found: {path}")
            return path
        for path in Config._default_files():         # default files: optional
            if path.is_file():
                return path
        return None

    @staticmethod
    def _read_file(path):
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        # optional per-platform sections (e.g. 'darwin', 'linux'), see config-example.yml
        if isinstance(raw.get(sys.platform), dict):
            raw = raw[sys.platform]
        return raw

    def folders(self, expname):
        """Return dictionary of experiment folders."""

        # default folders
        if not expname:  # handles both "" and None
            return {
                'rebuild': str(self.src_path / "rebuild_nemo"),
                'domain': str(self.data_path / "nemo" / "domain"),
            }

        exp_base = self.base_path / expname
        dirs = {
            'exp': str(exp_base),
            'nemo': str(exp_base / "output" / "nemo"),
            'oifs': str(exp_base / "output" / "oifs"),
            'restart': str(exp_base / "restart"),
            'log': str(exp_base / "log"),
            'saveic': str(exp_base / "saveic"),
            'post': str(exp_base / "post"),
            'rebuild': str(self.src_path / "rebuild_nemo"),
            'domain': str(self.data_path / "nemo" / "domain"),
        }
        
        # Create folders if missing. Careful on other users...
        Path(dirs['post']).mkdir(parents=True, exist_ok=True)
        Path(dirs['saveic']).mkdir(parents=True, exist_ok=True)
        
        return dirs
