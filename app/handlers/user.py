# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 用户处理器
处理用户中心、书币、收藏等
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from app.core.logger import logger
from app.core.database import get_session_factory
from app.core.models import User, Favorite, Book, DownloadLog
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

user_router = Router(name="user")


@user_router.message(Command("me"))
async def cmd_me(message: Message):
    """个人中心 - 显示用户信息"""
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

        fav_count = await session.scalar(
            select(func.count()).select_from(Favorite).where(Favorite.user_id == user.id)
        )

    text = f"""
👤 <b>个人中心</b>

📝 <b>基本信息</b>
├ 用户名: <code>{tg_user.username or '未设置'}</code>
├ 用户ID: <code>{tg_user.id}</code>
└ 注册时间: {user.created_at.strftime('%Y-%m-%d') if user.created_at else '未知'}

💰 <b>账户信息</b>
├ 书币余额: <code>{user.coins} 🪙</code>
└ 等级: <code>{user.level.value}</code>

📊 <b>数据统计</b>
├ 上传书籍: <code>{user.upload_count} 本</code>
├ 下载书籍: <code>{user.download_count} 本</code>
└ 收藏书籍: <code>{fav_count or 0} 本</code>

💡 <b>提示:</b>
• 上传书籍可获得书币奖励
• 书币可用于下载高质量书籍
• 收藏的书籍可在 /fav 中查看
"""

    await message.answer(text)


@user_router.message(Command("coins"))
async def cmd_coins(message: Message):
    """查看书币余额"""
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

    text = f"""
💰 <b>书币余额</b>

用户: <code>{tg_user.username or tg_user.full_name}</code>
余额: <code>{user.coins} 🪙</code>

📖 <b>书币用途:</b>
• 下载高质量书籍
• 获取VIP资源访问权限
• 参与平台活动

💡 <b>如何获得书币:</b>
• 上传书籍: +5~20 书币
• 每日签到: +1 书币
• 邀请好友: +10 书币
• 完善资料: +5 书币
"""

    await message.answer(text)


@user_router.message(Command("fav"))
async def cmd_favorites(message: Message):
    """查看收藏列表"""
    tg_user = message.from_user
    session_factory = get_session_factory()
    async with session_factory() as session:
        stmt = select(User).where(User.id == tg_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            await message.answer(
                "📚 <b>我的收藏</b>\n\n"
                "您还没有注册记录，请先发送 /start"
            )
            return

        stmt = (
            select(Favorite)
            .where(Favorite.user_id == user.id)
            .order_by(Favorite.created_at.desc())
            .options(selectinload(Favorite.book))
            .limit(20)
        )
        result = await session.execute(stmt)
        favorites = result.scalars().all()

    if not favorites:
        await message.answer(
            "📚 <b>我的收藏</b>\n\n"
            "您的收藏夹是空的。\n\n"
            "💡 搜索书籍并在详情页点击收藏按钮，即可将书籍添加到收藏夹！"
        )
        return

    lines = [
        "📚 <b>我的收藏</b>",
        f"共 <code>{len(favorites)}</code> 本书籍（最多显示20本）\n",
    ]

    keyboard_rows: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []
    for i, fav in enumerate(favorites, 1):
        book = fav.book
        if not book:
            continue
        lines.append(f"{i}. <b>{book.title}</b>")
        lines.append(f"   👤 {book.author} | 📅 {fav.created_at.strftime('%Y-%m-%d') if fav.created_at else '未知'}")
        lines.append("")

        current_row.append(
            InlineKeyboardButton(text=str(i), callback_data=f"book:detail:{book.id}")
        )
        if len(current_row) == 5:
            keyboard_rows.append(current_row)
            current_row = []
    if current_row:
        keyboard_rows.append(current_row)

    keyboard_rows.append([InlineKeyboardButton(text="❌ 关闭", callback_data="close")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await message.answer("\n".join(lines), reply_markup=keyboard)


@user_router.message(Command("history"))
async def cmd_history(message: Message):
    """查看下载历史"""
    tg_user = message.from_user
    session_factory = get_session_factory()
    async with session_factory() as session:
        stmt = (
            select(DownloadLog)
            .where(DownloadLog.user_id == tg_user.id)
            .order_by(DownloadLog.created_at.desc())
            .limit(20)
        )
        result = await session.execute(stmt)
        logs = result.scalars().all()

        book_ids = [log.book_id for log in logs]
        books_by_id: dict[int, Book] = {}
        if book_ids:
            result = await session.execute(select(Book).where(Book.id.in_(book_ids)))
            for book in result.scalars().all():
                books_by_id[book.id] = book

    if not logs:
        await message.answer(
            "📜 <b>下载历史</b>\n\n"
            "暂无记录。\n\n"
            "💡 通过 /s 搜索并下载书籍后，这里会显示历史记录。"
        )
        return

    lines = [
        "📜 <b>下载历史</b>",
        f"共 <code>{len(logs)}</code> 条记录（最多显示20条）\n",
    ]

    keyboard_rows: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []
    for i, log in enumerate(logs, 1):
        book = books_by_id.get(log.book_id)
        title = book.title if book else f"书籍ID {log.book_id}"
        lines.append(f"{i}. <b>{title}</b>")
        lines.append(f"   📅 {log.created_at.strftime('%Y-%m-%d %H:%M') if log.created_at else '未知'}")
        lines.append("")

        if book:
            current_row.append(
                InlineKeyboardButton(text=str(i), callback_data=f"book:detail:{book.id}")
            )
            if len(current_row) == 5:
                keyboard_rows.append(current_row)
                current_row = []

    if current_row:
        keyboard_rows.append(current_row)
    keyboard_rows.append([InlineKeyboardButton(text="❌ 关闭", callback_data="close")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await message.answer("\n".join(lines), reply_markup=keyboard)
