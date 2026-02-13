#!/bin/bash
# Check Redis
if ! pgrep -x "redis-server" > /dev/null; then
    echo "❌ Redis 未运行"
else
    echo "✅ Redis 运行中"
fi

# Check Postgres
if ! pg_isready -h localhost > /dev/null; then
    echo "❌ PostgreSQL 未连接"
else
    echo "✅ PostgreSQL 运行中"
fi

# Check Meilisearch
if ! curl -s http://localhost:7700/health > /dev/null; then
    echo "❌ Meilisearch 未响应"
else
    echo "✅ Meilisearch 运行中"
fi
```
*(记得 `chmod +x scripts/doctor.sh`)*

---

### 🧠 4. 如何在 Prompt 中激活这些能力

做好了上述配置后，在你的 **启动提示词 (`start_prompt.md`)** 的最前面，加上这一段“能力激活指令”：

```markdown
### 🔧 能力激活 (Capabilities Activation)
Claude，我为你配置了额外的 MCP 工具和调试脚本，请在开发过程中主动使用它们：

1.  **数据库视察**: 当你需要确认 User 或 Book 表是否创建成功，或数据是否写入时，请**直接使用 Postgres MCP 工具查询**，不要让我去查。
2.  **搜索调试**: 当搜索功能不返回结果时，请运行 `python scripts/mcp_meili.py books` 来查看索引内部状态。
3.  **环境自检**: 如果遇到连接错误，请优先运行 `./scripts/doctor.sh` 确认服务状态。

---
(接之前的 "Hello Claude! 我要开发..." 内容)