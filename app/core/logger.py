# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 日志模块
统一的日志配置和管理
"""

import logging
import sys
from typing import Any

from app.core.config import settings


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
        # 创建日志记录器
        self._logger = logging.getLogger("bookbot")
        self._logger.setLevel(getattr(logging, settings.log_level.upper()))

        # 清除现有处理器
        self._logger.handlers = []

        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)

        # 选择格式化器
        if settings.log_format.lower() == "json":
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        else:
            formatter = ColoredFormatter(
                '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)

        # 文件处理器 (生产环境)
        if settings.log_level.upper() == "INFO" or settings.log_level.upper() == "DEBUG":
            log_file = settings.log_dir / "bookbot.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
                )
            )
            self._logger.addHandler(file_handler)

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
