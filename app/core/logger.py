# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 日志模块
统一的日志配置和管理
"""

import logging
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from logging.handlers import TimedRotatingFileHandler


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器"""

    # ANSI 颜色代码
    COLORS = {
        "DEBUG": "\033[36m",      # 青色
        "INFO": "\033[32m",       # 绿色
        "WARNING": "\033[33m",    # 黄色
        "ERROR": "\033[31m",      # 红色
        "CRITICAL": "\033[35m",   # 紫色
        "RESET": "\033[0m",       # 重置
    }

    def format(self, record: logging.LogRecord) -> str:
        # 保存原始级别名称
        levelname = record.levelname

        # 添加颜色
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"

        # 格式化消息
        result = super().format(record)

        # 恢复原始级别名称
        record.levelname = levelname

        return result


class Logger:
    """日志管理器"""

    _instance: "Logger" = None
    _logger: logging.Logger = None

    def __new__(cls) -> "Logger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup_logger()
        return cls._instance

    def _setup_logger(self) -> None:
        """配置日志记录器"""
        log_level = "INFO"
        log_format = "json"
        log_dir = Path(__file__).parent.parent.parent / "logs"

        try:
            from app.core.config import get_settings

            settings = get_settings()
            log_level = settings.log_level
            log_format = settings.log_format
            log_dir = settings.log_dir
        except Exception:
            pass

        level = getattr(logging, log_level.upper(), logging.INFO)
        log_dir.mkdir(parents=True, exist_ok=True)

        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                payload = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "level": record.levelname,
                    "logger": record.name,
                    "msg": record.getMessage(),
                    "module": record.module,
                    "func": record.funcName,
                    "line": record.lineno,
                    "process": record.process,
                    "thread": record.thread,
                }
                if record.exc_info:
                    payload["exc"] = self.formatException(record.exc_info)
                return json.dumps(payload, ensure_ascii=False)

        if log_format.lower() == "json":
            console_formatter: logging.Formatter = JsonFormatter()
            file_formatter: logging.Formatter = JsonFormatter()
        else:
            console_formatter = ColoredFormatter(
                '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S',
            )
            file_formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(name)s [%(filename)s:%(lineno)d] %(message)s'
            )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(console_formatter)

        file_handler = TimedRotatingFileHandler(
            filename=str(log_dir / "bookbot.log"),
            when="midnight",
            backupCount=14,
            encoding="utf-8",
            utc=True,
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(file_formatter)

        error_file_handler = TimedRotatingFileHandler(
            filename=str(log_dir / "bookbot-error.log"),
            when="midnight",
            backupCount=30,
            encoding="utf-8",
            utc=True,
        )
        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(file_formatter)

        logging.basicConfig(
            level=level,
            handlers=[console_handler, file_handler, error_file_handler],
            force=True,
        )

        self._logger = logging.getLogger("bookbot")
        self._logger.setLevel(level)
        self._logger.propagate = True

    @property
    def logger(self) -> logging.Logger:
        """获取日志记录器实例"""
        return self._logger


# 全局日志实例
logger = Logger().logger


# 便捷方法
def debug(msg: str, *args: Any, **kwargs: Any) -> None:
    """记录 DEBUG 级别日志"""
    logger.debug(msg, *args, **kwargs)


def info(msg: str, *args: Any, **kwargs: Any) -> None:
    """记录 INFO 级别日志"""
    logger.info(msg, *args, **kwargs)


def warning(msg: str, *args: Any, **kwargs: Any) -> None:
    """记录 WARNING 级别日志"""
    logger.warning(msg, *args, **kwargs)


def error(msg: str, *args: Any, **kwargs: Any) -> None:
    """记录 ERROR 级别日志"""
    logger.error(msg, *args, **kwargs)


def critical(msg: str, *args: Any, **kwargs: Any) -> None:
    """记录 CRITICAL 级别日志"""
    logger.critical(msg, *args, **kwargs)


def success(msg: str, *args: Any, **kwargs: Any) -> None:
    """记录 SUCCESS 级别日志 (使用 INFO 级别)"""
    logger.info(f"✓ {msg}", *args, **kwargs)
