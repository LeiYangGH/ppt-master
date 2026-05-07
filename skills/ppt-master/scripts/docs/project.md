# 项目工具

项目工具用于创建、验证和检查标准 PPT Master 工作区。

## `project_manager.py`

项目初始化和验证的主入口。

```powershell
python scripts/project_manager.py init <project_name>
python scripts/project_manager.py import-sources <project_path> <source1> [<source2> ...]
python scripts/project_manager.py validate <project_path>
python scripts/project_manager.py info <project_path>
```

注意：
- 仓库外的文件默认复制到 `sources/`
- 使用 `--move` 则移动到 `sources/`
- 仓库内的文件默认也移动到 `sources/`（stderr 提示），避免误提交多余文件。
  如需强制复制仓库内文件，加 `--copy`
- `--move` 与 `--copy` 互斥

画布格式：`ppt169`（PPT 16:9，1280×720）

示例：

```powershell
python scripts/project_manager.py init my_presentation
python scripts/project_manager.py validate projects/my_presentation_ppt169_20251116
python scripts/project_manager.py info projects/my_presentation_ppt169_20251116
```

## `project_utils.py`

其他脚本共用的辅助模块。

典型用法：

```python
from project_utils import get_project_info, validate_project_structure
```

也可直接运行做快速检查：

```powershell
python scripts/project_utils.py <project_path>
```

## `batch_validate.py`

批量检查项目结构与合规性。

```powershell
python scripts/batch_validate.py examples
python scripts/batch_validate.py examples projects
python scripts/batch_validate.py --all
python scripts/batch_validate.py examples --export
```

用于发布或清理前的全仓库健康检查。

## `generate_examples_index.py`

自动重建 `examples/README.md`。

```powershell
python scripts/generate_examples_index.py
python scripts/generate_examples_index.py examples
```

## `pptx_template_import.py`

`/create-template` 的统一 PPTX 预处理入口。

```powershell
python scripts/pptx_template_import.py <template.pptx>
python scripts/pptx_template_import.py <template.pptx> -o <output_dir>
python scripts/pptx_template_import.py <template.pptx> --manifest-only
python scripts/pptx_template_import.py <template.pptx> --keep-raw
python scripts/pptx_template_import.py <template.pptx> --skip-manifest
```

功能：
- 从 `ppt/media/` 提取可复用的媒体资源
- 汇总幻灯片尺寸、主题色和字体元数据
- 推断背景图在幻灯片、版式、母版中的继承关系
- 生成 `manifest.json`、`analysis.md`、`master_layout_refs.json`、`master_layout_analysis.md`、`assets/`、清理后的 SVG 和 `reference_svg_selection.json`
- 原生 SVG 导出仅 Windows 可用（依赖已安装的 Microsoft PowerPoint）
- macOS 下回退为通过 Keynote 导出 PDF，再转换为 SVG
- 将内联 Base64 图像外链后，写入 `svg/`
- `/create-template` 引用源为 `.pptx` 时必须执行
- 默认输出目录为 `<pptx_stem>_template_import/`
- 如仅需轻量导入结果而不导出幻灯片 SVG，加 `--manifest-only`
- 仅用于模板参考准备，不做最终 1:1 模板交付

实现说明：
- 此工作流的内部辅助脚本位于 `scripts/template_import/`

## `error_helper.py`

显示常见项目错误的标准修复方案。

```powershell
python scripts/error_helper.py
python scripts/error_helper.py missing_readme
python scripts/error_helper.py missing_readme project_path=my_project
```
