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
    """ Carica un config.yml e fornisce i path di un esperimento. """

    def __init__(self, config_path=None):
        # Convertiamo sempre in Path se viene passata una stringa
        self.config_path = Path(config_path) if config_path else self._find_config_file()
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

        with open(self.config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        missing = [k for k in REQUIRED_KEYS if not raw.get(k)]
        if missing:
            raise ConfigError(f"Campi mancanti o vuoti in {self.config_path}: {missing}")

        # Convertiamo anche questi in Path per coerenza con pathlib
        self.base_path = Path(raw["base_path"])
        self.src_path = Path(raw["src_path"])
        self.data_path = Path(raw["data_path"])

    def folders(self, expname):
        if not expname:  # Gestisce sia "" che None
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
            'tmp': str(exp_base / "tmp"),
            'post': str(exp_base / "post"),
            'rebuild': str(self.src_path / "rebuild_nemo"),
            'domain': str(self.data_path / "nemo" / "domain"),
        }
        
        # Creazione cartelle in modo sicuro
        Path(dirs['post']).mkdir(parents=True, exist_ok=True)
        Path(dirs['tmp']).mkdir(parents=True, exist_ok=True)
        
        return dirs