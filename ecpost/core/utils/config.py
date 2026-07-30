#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Folder definitions

Author: Alessandro Sozza (CNR-ISAC)
Date: July 2026
"""

import os
import logging
from pathlib import Path
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CONFIG_FILENAME = "config.yml"
REQUIRED_KEYS = ("base_path", "src_path", "data_path")


class ConfigError(RuntimeError):
    pass


class Config:
    """ Carica un workspace-config.yml e fornisce i path di un esperimento. """

    def __init__(self, config_path=None):
        self.config_path = config_path #if config_path else self._find_config_file()
        self.base_path = None
        self.src_path = None
        self.data_path = None
        self._load()

    def _find_config_file(self, start=None, filename=CONFIG_FILENAME):
        current = (start or Path.cwd()).resolve()
        stop_at = Path.home()

        while True:
            candidate = current / filename
            if candidate.is_file():
                return candidate
            if current == current.parent or current == stop_at:
                break
            current = current.parent

        raise ConfigError(
            f"'{filename}' non trovato in {Path.cwd()} o nelle cartelle superiori."
        )

    def _load(self):
        if not self.config_path.is_file():
            raise ConfigError(f"Config non trovata: {self.config_path}")

        with open(self.config_path, "r") as f:
            raw = yaml.safe_load(f) or {}

        missing = [k for k in REQUIRED_KEYS if not raw.get(k)]
        if missing:
            raise ConfigError(f"Campi mancanti o vuoti in {self.config_path}: {missing}")

        self.base_path = raw["base_path"]
        self.src_path = raw["src_path"]
        self.data_path = raw["data_path"]

    def folders(self, expname):
        if expname == "":
            return {
                'rebuild': os.path.join(self.src_path, "rebuild_nemo"),
                'domain': os.path.join(self.data_path, "nemo", "domain"),
            }

        dirs = {
            'exp': os.path.join(self.base_path, expname),
            'nemo': os.path.join(self.base_path, expname, "output", "nemo"),
            'oifs': os.path.join(self.base_path, expname, "output", "oifs"),
            'restart': os.path.join(self.base_path, expname, "restart"),
            'log': os.path.join(self.base_path, expname, "log"),
            'tmp': os.path.join(self.base_path, expname, "tmp"),
            'post': os.path.join(self.base_path, expname, "post"),
            'rebuild': os.path.join(self.src_path, "rebuild_nemo"),
            'domain': os.path.join(self.data_path, "nemo", "domain"),
        }
        os.makedirs(dirs['post'], exist_ok=True)
        os.makedirs(dirs['tmp'], exist_ok=True)
        return dirs
