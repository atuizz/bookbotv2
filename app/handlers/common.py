# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 通用处理器
处理基本命令和通用回调
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.core.config import settings
from app.core.logger import logger

common_router = Router(name="common")


@common_router.message(Command("start"))
async def cmd_start(message: Message):
    """处理 /start 命令"""
    welcome_text = f"""
👋 欢迎使用 <b>搜书神器 V2</b>!

📚 <b>我能帮你做什么？</b>
• 搜索海量电子书资源
• 支持多种格式 (TXT, PDF, EPUB, MOBI)
• 智能推荐，精准匹配

🔍 <b>如何使用？</b>
• 直接发送关键词: <code>剑来</code>
• 使用搜索命令: <code>/s 剑来</code>
• 查看帮助: <code>/help</code>

💡 <b>提示：</b>上传你的书籍，还能获得书币奖励哦！
"""
    await message.answer(welcome_text)


@common_router.message(Command("help"))
async def cmd_help(message: Message):
    """处理 /help 命令"""
    help_text = f"""
📖 <b>搜书神器 V2 使用指南</b>

<b>🔍 搜索命令</b>
• <code>/s [关键词]</code> - 搜索书名/作者
• <code>/ss [关键词]</code> - 搜索标签/主角
• 直接发送关键词也能搜索

<b>📤 上传书籍</b>
• 直接发送文件即可上传
• 支持格式: TXT, PDF, EPUB, MOBI, AZW3
• 上传可获得书币奖励

<b>📚 个人中心</b>
• <code>/me</code> - 查看个人信息
• <code>/coins</code> - 查看书币余额
• <code>/fav</code> - 查看收藏列表
• <code>/history</code> - 下载历史

<b>🌟 其他功能</b>
• <code>/top</code> - 查看排行榜
• <code>/my</code> - 邀请链接
• <code>/settings</code> - 设置面板

<b>⚙️ 基础命令</b>
• <code>/start</code> - 开始使用
• <code>/help</code> - 查看帮助
• <code>/about</code> - 关于我们

💬 有问题？请联系管理员 @admin
"""
    await message.answer(help_text)


@common_router.message(Command("about"))
async def cmd_about(message: Message):
    """处理 /about 命令"""
    about_text = f"""
🤖 <b>搜书神器 V2</b>

<b>版本:</b> 2.0.0
<b>技术栈:</b> Python 3.11, aiogram 3.x, PostgreSQL, Meilisearch

<b>开源协议:</b> MIT License

<b>致谢:</b>
• Telegram Bot API
• aiogram 开发团队
• Meilisearch 搜索引擎
• 所有贡献者

© 2024 搜书神器. All rights reserved.
"""
    await message.answer(about_text)


@common_router.callback_query(F.data == "cancel")
async def on_cancel(callback: CallbackQuery):
    """处理取消回调"""
    await callback.message.edit_text("❌ 操作已取消")
    await callback.answer()


@common_router.callback_query(F.data == "close")
async def on_close(callback: CallbackQuery):
    """处理关闭回调"""
    try:
        await callback.message.delete()
    except:
        pass
    await callback.answer()


@common_router.callback_query(F.data == "goto:search")
async def on_goto_search(callback: CallbackQuery):
    """跳转到搜索"""
    await callback.message.edit_text(
        "🔍 <b>开始搜索</b>\n\n"
        "请直接发送关键词，或使用:\n"
        "• <code>/s 关键词</code> - 搜索书名/作者\n"
        "• <code>/ss 关键词</code> - 搜索标签/主角"
    )
    await callback.answer()