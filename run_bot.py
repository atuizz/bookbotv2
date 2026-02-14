# -*- coding: utf-8 -*-
"""
搜书神器 V2 - Bot 启动脚本
简化入口文件
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入并运行主程序
from app.bot import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
