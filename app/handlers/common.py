# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 通用处理器
处理基本命令和通用回调
"""

import asyncio

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.core.config import get_settings
from app.core.logger import logger
from app.core.database import get_session_factory
from app.core.models import User, Book, BookStatus
from app.core.deeplink import decode_payload
from sqlalchemy import select, func
from app.handlers.book_detail import send_book_card, show_public_booklist
from app.handlers.invite import parse_invite_code, bind_invite_relation

common_router = Router(name="common")

HELP_TEXT = (
    "搜书神器是一个免费的Telegram机器人,致力于让每个人都能自由获取知识。我们鼓励分享优秀文化内容,希望打造高质量的知识共享库,让所有人都能够免费阅读。\n\n"
    "<blockquote>TG 最好用的智能搜书机器人</blockquote>\n\n"
    "新手指南:\n\n"
    "1.贡献等级\n"
    "使用贡献划分等级，从低到高分为黑铁、青铜、白银、黄金、钻石5个段位，拥有不同权限。\n"
    "2.怎么获得贡献值?\n"
    "上传书籍、邀请书友、书籍被好评、捐赠会员。\n"
    "3.怎么获得书币?\n"
    "自动签到、上传书籍、邀请注册、书籍被好评、捐赠会员。\n"
    "4.怎么搜书?\n"
    "/s+关键词，搜索书名和作者\n"
    "/ss+关键词，搜索书籍的标签\n"
    "5.下载书籍\n"
    "消耗账户1书币（优先使用签到获得的赠币）\n"
    "7天内重复下载不消耗书币，收藏书籍7天后下载不消耗书币，或自己上传的书籍7天后下载不消耗书币\n"
    "6.如何上传书籍?\n"
    "直接发送或转发书籍文件给我 @sosdbot\n"
    "7.如何邀请书友?\n"
    "/my 获得邀请链接,快速获得书币,极速邀请青铜捐赠会员后，邀请者获得书币奖励（无视每天下载封顶）\n"
    "8.捐赠会员有什么?\n"
    "一次性获得永久会员和书币（用来提升等级和下载书籍）\n"
    "等级权限翻倍（每天自动签到翻倍），优先体验新功能\n\n"
    "关注BOT频道获取更多信息,有问题找BokFather\n"
    "常用命令 /help /my /book /booklist /info /topuser /review\n\n"
    "<blockquote>请考虑捐赠以支持我们提供更安全、更稳定、更智能、更丰富的服务。</blockquote>"
)

HELP_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="邀请书友使用", callback_data="help:invite"),
            InlineKeyboardButton(text="捐赠会员计划", callback_data="help:donate"),
        ]
    ]
)


@common_router.message(Command("start"))
async def cmd_start(message: Message):
    """处理 /start 命令"""
    async def ensure_user() -> User:
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
                await session.refresh(user)
            return user

    payload = ""
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) > 1:
        payload = parts[1].strip()
    if payload.startswith("INV"):
        inviter_id = parse_invite_code(payload)
        if inviter_id is None:
            await message.answer("⚠️ 无效或过期的邀请码")
        else:
            try:
                current_user = await asyncio.wait_for(ensure_user(), timeout=3)
                bound = await bind_invite_relation(
                    inviter_id=inviter_id,
                    invitee_id=current_user.id,
                )
                if bound:
                    await message.answer("✅ 邀请绑定成功，邀请人已获得奖励")
            except Exception as e:
                logger.warning(f"处理邀请码失败: {e}")

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
    if payload.startswith("au_"):
        author = decode_payload(payload.replace("au_", "", 1))
        author = (author or "").strip()
        if len(author) < 1:
            await message.answer("⚠️ 无效的链接参数")
            return
        from app.handlers.search import perform_search

        await perform_search(message, author, user_id=message.from_user.id)
        return
    if payload.startswith("list_"):
        token = payload.replace("list_", "", 1).strip()
        if not token:
            await message.answer("⚠️ 无效的书单分享参数")
            return
        await show_public_booklist(
            bot=message.bot,
            chat_id=message.chat.id,
            share_token=token,
        )
        return

    welcome_text = (
        "搜书神器是一个免费的 Telegram 机器人，致力于让每个人都能自由获取知识。我们提供了优秀的分享型文化内容，希望打造高质量的知识共享平台，让所有人都能轻松阅读。\n\n"
        "发送 /s 关键词 直接搜索书名，作者\n"
        "发送 /ss 关键词 可以搜索主角，标签\n\n"
        "更多帮助请点击: /help"
    )
    await message.answer(welcome_text)

    async def ensure_user_with_timeout() -> None:
        try:
            await asyncio.wait_for(ensure_user(), timeout=3)
        except Exception as e:
            logger.warning(f"/start 写入用户记录失败: {e}")

    asyncio.create_task(ensure_user_with_timeout())


@common_router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    await message.answer("❌ 操作已取消")


@common_router.message(Command("help"))
async def cmd_help(message: Message):
    """处理 /help 命令"""
    await message.answer(HELP_TEXT, reply_markup=HELP_KEYBOARD)


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
    await message.answer(
        "评分入口已调整为排行榜浏览。\n"
        "你可以使用 /top rating 查看高分作品。"
    )


@common_router.callback_query(F.data.startswith("help:"))
async def on_help_callback(callback: CallbackQuery):
    action = callback.data.replace("help:", "")
    if action == "invite":
        username = (get_settings().bot_username or "").lstrip("@")
        link = f"https://t.me/{username}?start=invite_{callback.from_user.id}" if username else ""
        await callback.message.answer(f"邀请链接：{link}" if link else "⚠️ 暂无法生成邀请链接")
        await callback.answer()
        return
    if action == "donate":
        settings = get_settings()
        if not settings.donate_enabled:
            await callback.message.answer("当前未开放捐赠说明页。")
            await callback.answer()
            return
        text = f"{settings.donate_title}\n\n{settings.donate_text}"
        if settings.donate_url:
            text += f"\n\n了解更多: {settings.donate_url}"
        await callback.message.answer(text)
        await callback.answer()
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
