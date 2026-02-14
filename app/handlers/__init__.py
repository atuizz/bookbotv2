# -*- coding: utf-8 -*-
"""
搜书神器 V2 - 处理器包
统一注册所有处理器
"""

from aiogram import Dispatcher


def register_handlers(dp: Dispatcher) -> None:
    """
    注册所有处理器到 Dispatcher

    Args:
        dp: aiogram Dispatcher 实例
    """
    from app.handlers.book_detail import book_detail_router
    from app.handlers.common import common_router
    from app.handlers.group_verify import group_verify_router
    from app.handlers.invite import invite_router
    from app.handlers.rankings import rankings_router
    from app.handlers.search import search_router
    from app.handlers.settings import settings_router
    from app.handlers.tag_search import tag_search_router
    from app.handlers.upload import upload_router
    from app.handlers.user import user_router

    # 按照优先级顺序注册
    # 越靠前优先级越高
    dp.include_router(upload_router)       # 上传处理器 (需要优先处理文档)
    dp.include_router(search_router)       # 搜索处理器
    dp.include_router(tag_search_router)   # 标签搜索处理器 (/ss)
    dp.include_router(book_detail_router)  # 书籍详情处理器
    dp.include_router(user_router)         # 用户处理器
    dp.include_router(invite_router)       # 邀请处理器 (/my)
    dp.include_router(rankings_router)     # 排行榜处理器 (/top)
    dp.include_router(group_verify_router) # 入群验证处理器 (/yanzheng)
    dp.include_router(settings_router)     # 设置面板处理器 (/settings)
    dp.include_router(common_router)       # 通用处理器 (放在最后作为fallback)
