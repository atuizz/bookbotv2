# 搜书神器 V2 - 备份防封架构设计文档

## 📋 核心问题理解

### 关于 file_id 的重要认知

```
❌ 错误理解：同一个文件在不同地方的 file_id 相同
✅ 正确理解：file_id 是上下文绑定的，不同聊天/频道的 file_id 都不同
```

### file_id 上下文机制

```
用户上传文件 → Bot 私聊
    ↓ 获取 file_id_A (Bot-用户私聊上下文)

转发到备份频道
    ↓ 获取 file_id_B (Bot-备份频道上下文)

发送给用户
    可用: file_id_A 直接发送
    或: 从备份频道转发 (使用 message_id)
```

## 🏗️ 备份架构设计

### 数据模型

```python
class FileLocation:
    """文件位置信息"""
    file_id: str          # 该上下文中的 file_id
    chat_id: int          # 所属聊天ID
    message_id: int       # 消息ID (用于转发)
    file_unique_id: str   # 全局唯一标识

class BackupRecord:
    """备份记录"""
    sha256_hash: str              # 文件内容哈希
    file_name: str               # 文件名
    file_size: int               # 文件大小

    original_location: FileLocation  # 用户私聊位置
    backup_location: FileLocation     # 备份频道位置

    is_active: bool              # 是否可用
    fail_count: int              # 失败次数
```

### 备份流程

```
用户上传文件
    ↓
Bot 接收文件
    ↓
计算 SHA256 哈希
    ↓
创建 OriginalLocation
    - file_id: 用户私聊的 file_id
    - chat_id: 用户私聊ID
    - message_id: 用户消息ID
    ↓
转发到备份频道
    ↓
创建 BackupLocation
    - file_id: 备份频道的 file_id
    - chat_id: 备份频道ID
    - message_id: 备份消息ID
    ↓
保存 BackupRecord 到数据库
```

### 恢复流程

```
用户请求下载
    ↓
检查 OriginalLocation
    可用 → 使用 original_file_id 直接发送
    失效 → 继续下一步
    ↓
使用 BackupLocation
    从备份频道转发到用户
    ↓
更新状态
    记录使用情况
    标记失效的资源
```

## 💻 核心代码实现

### 1. 创建备份

```python
async def create_backup(self, message: Message, sha256_hash: str):
    document = message.document

    # 创建 OriginalLocation
    original = FileLocation(
        file_id=document.file_id,
        chat_id=message.chat.id,
        message_id=message.message_id,
        file_unique_id=document.file_unique_id
    )

    # 转发到备份频道
    forwarded = await bot.forward_message(
        chat_id=backup_channel_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id
    )

    # 创建 BackupLocation
    backup = FileLocation(
        file_id=forwarded.document.file_id,
        chat_id=backup_channel_id,
        message_id=forwarded.message_id,
        file_unique_id=forwarded.document.file_unique_id
    )

    # 保存记录
    record = BackupRecord(
        sha256_hash=sha256_hash,
        file_name=document.file_name,
        file_size=document.file_size,
        original_location=original,
        backup_location=backup
    )

    await self.save_record(record)
```

### 2. 发送文件给用户

```python
async def send_file_to_user(self, sha256_hash: str, user_chat_id: int, caption: str = None):
    record = await self.get_record(sha256_hash)

    # 策略1: 使用 original_file_id 直接发送
    if record.original_location:
        try:
            return await bot.send_document(
                chat_id=user_chat_id,
                document=record.original_location.file_id,
                caption=caption
            )
        except Exception as e:
            logger.warning(f"original_file_id 失效: {e}")

    # 策略2: 从备份频道转发
    if record.backup_location:
        try:
            return await bot.forward_message(
                chat_id=user_chat_id,
                from_chat_id=record.backup_location.chat_id,
                message_id=record.backup_location.message_id
            )
        except Exception as e:
            logger.error(f"备份转发失败: {e}")

    return None
```

## 📊 对比：转发 vs 直接发送

| 方式 | 代码 | 显示效果 | 优缺点 |
|------|------|----------|--------|
| **forward_message** | `bot.forward_message()` | 显示 "Forwarded from XXX" | 保留原消息信息，但显示来源 |
| **send_document** | `bot.send_document(file_id)` | 不显示来源，像新消息 | 干净，但 file_id 可能失效 |
| **copy_message** | `bot.copy_message()` | 不显示来源 | 平衡方案，但需要 message_id |

## 🎯 推荐策略

根据截图显示的效果（**没有 "Forwarded from" 字样**），推荐以下混合策略：

```python
async def send_book_file(user_chat_id: int, book: Book):
    """
    发送书籍文件的最优策略
    """
    # 优先尝试直接发送 (最干净，不显示来源)
    try:
        return await bot.send_document(
            chat_id=user_chat_id,
            document=book.file_id,
            caption=f"📚 {book.title}"
        )
    except Exception as e:
        logger.warning(f"直接发送失败: {e}")

    # 直接发送失败，尝试从备份恢复
    backup_service = await get_backup_service()
    return await backup_service.send_file_to_user(
        sha256_hash=book.file_unique_id,
        user_chat_id=user_chat_id,
        caption=f"📚 {book.title}"
    )
```

## 🔧 运维建议

1. **多备份频道**：配置3个以上的备份频道，分散风险
2. **定期检查**：每周运行一次健康检查，标记失效资源
3. **监控告警**：文件发送失败率超过5%时发送告警
4. **数据保留**：保留最近90天的备份记录，定期清理旧数据

---

**最后更新**: 2024年
**版本**: 2.0 重构版
