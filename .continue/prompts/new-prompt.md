---
name: format
description: output format
invokable: true
---

# 输出模式（必须严格遵守）

每次回复必须选择且只选择一种模式：

【模式1：TERMINAL（终端命令）】
- 只输出命令
- 不要解释
- 不要前缀
- 不要后缀
- 不要使用分号连接命令

【模式2：PATCH（文件修改）】
- 输出标准 diff 格式
- 必须包含文件路径

【模式3：CHAT（普通说明）】
- 正常解释说明

如果用户意图不明确，使用 CHAT 模式。