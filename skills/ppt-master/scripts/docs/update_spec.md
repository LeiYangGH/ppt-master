# update_spec.py

将 `spec_lock.md` 的值变更同步到锁文件本身以及每个 `svg_output/*.svg`。生成后批量调整样式的单一编辑入口。

## 用法

```bash
python skills/ppt-master/scripts/update_spec.py <project_path> <section>.<key>=<value>
```

省略点的裸 `<key>=<value>` 视为 `colors.<key>=<value>`，保持向后兼容。

一次调用 = 一次变更。工具流程：

1. 从 `<project_path>/spec_lock.md` 读取旧值
2. 将新值写入 `spec_lock.md`
3. 将变更传播到 `svg_output/` 下的每个 `.svg`
4. 输出受影响的文件列表

## 示例

```bash
# 全演示文稿换主色（裸 key → colors.primary）
python skills/ppt-master/scripts/update_spec.py projects/acme_ppt169_20260301 primary=#0066AA

# 显式 section.key 形式
python skills/ppt-master/scripts/update_spec.py projects/acme_ppt169_20260301 colors.accent=#FF6B35

# 更换全演示文稿字体
python skills/ppt-master/scripts/update_spec.py projects/acme_ppt169_20260301 \
  'typography.font_family="Inter", Arial, sans-serif'
```

## v2 支持范围

- **支持**：
  - `colors.*` — 在 `svg_output/*.svg` 中替换 HEX 值（不区分大小写）。
  - `typography.font_family` — 替换每个 `font-family="..."` / `font-family='...'` 属性的内部值。
- **不支持**：字号、图标、图像、画布、禁用项 — 这些涉及属性级或语义级替换，批量传播的风险收益不成比例。请手动编辑 `spec_lock.md` 和受影响 SVG，或由 Executor 重生成对应页面。

## 何时使用

- "更换全演示文稿主色" → 一次 `update_spec.py` 调用
- "更换全演示文稿字体" → 一次 `update_spec.py` 调用
- "更换单页强调色" → 直接编辑该页 SVG
- "重新设计配色 / 字体系统" → 手动更新 `spec_lock.md`，再由 Executor 重生成受影响页面

## 安全性

- HEX 值（如 `#005587`）在 SVG 内容中足够唯一，字面替换安全
- `font-family` 替换限定于属性内；外层引号保留，若新值含相同引号则自动切换
- 工具拒绝非 HEX 输入、未知键和不支持的节
- 不创建备份 — 项目文件夹应受 git 管理，以便 diff / 回退

### 首次 `font-family` 更新的注意事项

脚本将 `spec_lock.md` 的值原样写入每个 SVG 的 `font-family` 属性。若 Executor 生成的 SVG 中字体名未加引号（如 `font-family="Microsoft YaHei, Arial, sans-serif"`），而 `spec_lock.md` 采用带引号形式（`"Microsoft YaHei", Arial, sans-serif`），则**首次**替换会将所有 SVG 规范化为与 `spec_lock.md` 字面一致（如 `font-family='"Microsoft YaHei", Arial, sans-serif'`）。两种形式语义等价（CSS 和 DrawingML 解析结果一致），但规范化会在含文本的 SVG 上产生字节级差异。后续更新仅触及值真正变化的文件。
