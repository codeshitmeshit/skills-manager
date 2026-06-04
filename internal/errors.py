"""Shared exception and exit code definitions."""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    SUCCESS = 0
    USAGE_ERROR = 2
    RUNTIME_ERROR = 1


class CoshSkillsError(Exception):
    """Base class for expected cosh-skills failures."""

    exit_code = ExitCode.RUNTIME_ERROR
