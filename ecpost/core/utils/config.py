#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Folder definitions

Author: Alessandro Sozza (CNR-ISAC)
Date: July 2026
"""

import os
import yaml
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


CONFIG_FILENAME = "config.yml"
REQUIRED_KEYS = ("base_path", "src_path", "data_path")


class ConfigError(RuntimeError):
    pass

CONFIG_FILENAME = "config.yml"
DEFAULT_CONFIG = Path(__file__).resolve().parent / CONFIG_FILENAME
REQUIRED_KEYS = ("base_path", "src_path", "data_path")


class Config:
    """Configure experiment paths giving priority to explicit args > file config (if exists) > error. """

    def __init__(self, base_path=None, src_path=None, data_path=None, config_path=None):
        explicit = {
            k: v for k, v in
            {"base_path": base_path, "src_path": src_path, "data_path": data_path}.items()
            if v
        }

        from_file = {}
        if len(explicit) < len(REQUIRED_KEYS):      # file config is only used if something is missing
            from_file = self._read_file(config_path)

        merged = {**from_file, **explicit}           # explicit paths take precedence over file config
        missing = [k for k in REQUIRED_KEYS if not merged.get(k)]
        if missing:
            raise ConfigError(
                f"Path mancanti: {missing}. Passali come argomenti o definiscili in "
                f"{config_path or DEFAULT_CONFIG}"
            )

        self.base_path = Path(merged["base_path"])
        self.src_path = Path(merged["src_path"])
        self.data_path = Path(merged["data_path"])

    @staticmethod
    def _read_file(config_path):
        if config_path:                              # file explicitly specified: must exist
            path = Path(config_path)
            if not path.is_file():
                raise ConfigError(f"Config not found: {path}")
        else:                                        # default next to module: optional
            path = Path.cwd() / CONFIG_FILENAME
            if not path.is_file():
                return {}
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

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
        
        # Creazione cartelle in modo sicuro. Careful on other users...
        Path(dirs['post']).mkdir(parents=True, exist_ok=True)
        Path(dirs['saveic']).mkdir(parents=True, exist_ok=True)
        
        return dirs
