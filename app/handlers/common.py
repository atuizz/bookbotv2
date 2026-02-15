# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 通用处理器
处理基本命令和通用回调
"""

import asyncio

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.core.logger import logger
from app.core.database import get_session_factory
from app.core.models import User, Book, BookStatus
from sqlalchemy import select, func
from app.handlers.book_detail import send_book_card

common_router = Router(name="common")


@common_router.message(Command("start"))
async def cmd_start(message: Message):
    """处理 /start 命令"""
    payload = ""
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) > 1:
        payload = parts[1].strip()
    if payload.startswith("book_"):
        try:
            book_id = int(payload.replace("book_", "").strip())
        except ValueError:
            await message.answer("⚠️ 无效的链接参数")
            return
        await send_book_card(
            bot=message.bot,
            chat_id=message.chat.id,
            book_id=book_id,
            from_user=message.from_user,
        )
        return

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

    async def ensure_user() -> None:
        tg_user = message.from_user
        session_factory = get_session_factory()
        async with session_factory() as session:
            stmt = select(User).where(User.id == tg_user.id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if not user:
                user = User(
                    id=tg_user.id,
                    username=tg_user.username,
                    first_name=tg_user.first_name,
                    last_name=tg_user.last_name,
                    coins=0,
                    upload_count=0,
                    download_count=0,
                    search_count=0,
                )
                session.add(user)
                await session.commit()

    async def ensure_user_with_timeout() -> None:
        try:
            await asyncio.wait_for(ensure_user(), timeout=3)
        except Exception as e:
            logger.warning(f"/start 写入用户记录失败: {e}")

    asyncio.create_task(ensure_user_with_timeout())


@common_router.message(Command("help"))
async def cmd_help(message: Message):
    """处理 /help 命令"""
    help_text = (
        "搜书神器是一个免费的 Telegram 机器人，致力于让每个人都能自由获取知识。我们提供了优秀的分享型文化内容，希望打造高质量的知识共享平台，让所有人都能轻松阅读。\n\n"
        "<blockquote>TG 最好用的智能搜书机器人</blockquote>\n\n"
        "<b>新手指南:</b>\n"
        "1. <b>如何升级</b>：使用贡献划分等级，从低到高为黑铁、青铜、白银、黄金、钻石 5 个段位。\n"
        "2. <b>怎么获得贡献值</b>：上传书籍、邀请好友、书籍被好评、捐赠会员。\n"
        "3. <b>怎么得书币</b>：自动签到、上传书籍、邀请注册、书籍被好评、捐赠会员。\n"
        "4. <b>怎么搜书</b>：\n"
        "   /s+关键词，搜索书名/作者\n"
        "   /ss+关键词，搜索主角/标签\n"
        "5. <b>下载书籍/电子书</b>：消耗书币（优先使用签到获得的账户）。\n"
        "6. <b>如何上传书籍</b>：直接发送文档/电子书文件给我。\n"
        "7. <b>如何邀请好友</b>：/my 获取专属邀请链接。\n"
        "8. <b>捐赠会员有什么</b>：一次性获得永久会员与书币（用于提升等级和下载书籍）。\n\n"
        "关注 BOT 频道获取更多信息：@BookFather\n"
        "常用命令：/help /my /book /booklist /info /topuser /review\n\n"
        "<blockquote>请注意：请勿上传违规内容，避免争议，更爱你。愿书店的那扇门，永远对你关闭。</blockquote>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="邀请好友使用", callback_data="help:invite"),
            InlineKeyboardButton(text="捐赠会员计划", callback_data="help:donate"),
        ]
    ])
    await message.answer(help_text, reply_markup=keyboard)


@common_router.message(Command("about"))
async def cmd_about(message: Message):
    """处理 /about 命令"""
    about_text = f"""
🤖 <b>搜书神器 V2</b>

<b>版本:</b> 2.0.1
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


@common_router.message(Command("info"))
async def cmd_info(message: Message):
    session_factory = get_session_factory()
    async with session_factory() as session:
        total_books = await session.scalar(select(func.count()).select_from(Book)) or 0
        active_books = await session.scalar(
            select(func.count()).select_from(Book).where(Book.status == BookStatus.ACTIVE)
        ) or 0
        pending_books = await session.scalar(
            select(func.count()).select_from(Book).where(Book.status == BookStatus.PENDING)
        ) or 0
        total_users = await session.scalar(select(func.count()).select_from(User)) or 0

    failed_books = max(total_books - active_books - pending_books, 0)
    text = (
        f"书库统计:\n"
        f"书籍: {total_books}\n"
        f"用户: {total_users}\n\n"
        f"排队({pending_books}) 成功({active_books}) 失败({failed_books})\n"
        f"发送 /info 查看书库统计和上传进度"
    )
    await message.answer(text)


@common_router.message(Command("review"))
async def cmd_review(message: Message):
    await message.answer("功能开发中...")


@common_router.callback_query(F.data.startswith("help:"))
async def on_help_callback(callback: CallbackQuery):
    action = callback.data.replace("help:", "")
    if action == "invite":
        username = callback.bot.username or ""
        link = f"https://t.me/{username}?start=invite_{callback.from_user.id}" if username else ""
        await callback.message.answer(f"邀请链接：{link}" if link else "⚠️ 暂无法生成邀请链接")
        await callback.answer()
        return
    if action == "donate":
        await callback.answer("功能开发中...", show_alert=True)
        return
    await callback.answer()


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
