# -*- coding: utf-8 -*-
"""
搜书神器 V2 - Telegram Bot 主入口
负责初始化Bot、注册处理器、启动轮询
"""

import asyncio
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.strategy import FSMStrategy

# 确保项目根目录在路径中
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings
from app.core.logger import logger
from app.handlers import register_handlers


async def on_startup(bot: Bot) -> None:
    """Bot 启动时的初始化操作"""
    settings = get_settings()
    logger.info("=" * 50)
    logger.info("搜书神器 V2 启动中...")
    logger.info(f"Bot 用户名: @{settings.bot_username}")
    logger.info(f"日志级别: {settings.log_level}")

    try:
        # 设置 Bot 命令菜单
        from aiogram.types import BotCommand, BotCommandScopeDefault

        commands = [
            BotCommand(command="start", description="开始使用"),
            BotCommand(command="s", description="搜索书籍"),
            BotCommand(command="ss", description="搜索标签/主角"),
            BotCommand(command="me", description="个人中心"),
            BotCommand(command="coins", description="书币余额"),
            BotCommand(command="fav", description="我的收藏"),
            BotCommand(command="top", description="排行榜"),
            BotCommand(command="my", description="邀请链接"),
            BotCommand(command="settings", description="设置面板"),
            BotCommand(command="help", description="使用帮助"),
            BotCommand(command="about", description="关于我们"),
        ]

        await bot.set_my_commands(
            commands=commands,
            scope=BotCommandScopeDefault(),
        )
        logger.info("Bot 命令菜单设置成功")

        # 获取 Bot 信息
        bot_info = await bot.get_me()
        logger.info(f"Bot 用户名: @{bot_info.username}")

    except Exception as e:
        logger.error(f"启动初始化失败: {e}", exc_info=True)
        raise

    logger.info("=" * 50)


async def on_shutdown(bot: Bot) -> None:
    """Bot 关闭时的清理操作"""
    logger.info("=" * 50)
    logger.info("搜书神器 V2 关闭中...")

    try:
        # 关闭 Bot 会话
        await bot.session.close()
        logger.info("Bot 会话已关闭")
    except Exception as e:
        logger.error(f"关闭时出错: {e}")

    logger.info("=" * 50)


async def main() -> None:
    """主入口函数"""
    settings = get_settings()

    # 初始化 Bot
    bot = Bot(
        token=settings.bot_token,
        parse_mode=ParseMode.HTML,
    )

    # 初始化 Dispatcher
    # 使用内存存储FSM状态（如需Redis可取消注释）
    dp = Dispatcher(
        storage=None,  # 简化版本不使用FSM
        fsm_strategy=FSMStrategy.CHAT,
    )

    # 注册启动和关闭钩子
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # 注册所有处理器
    register_handlers(dp)

    logger.info("Bot 初始化完成，开始轮询...")

    # 开始轮询
    try:
        await dp.start_polling(
            bot,
            skip_updates=True,  # 跳过启动前积累的更新
        )
    except Exception as e:
        logger.error(f"轮询出错: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
        sys.exit(1)
