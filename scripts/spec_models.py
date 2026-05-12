#!/usr/bin/env python
"""
结构化配置 schema 定义

使用 Pydantic 模型定义 spec_lock.json 的结构化 schema，
用于替代当前的 Markdown + 正则解析方式。

用法：
    from scripts.spec_models import SpecLock
    import json
    
    # 从 JSON 文件加载
    with open('workspace/spec_lock.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    spec = SpecLock(**data)
    
    # 验证 JSON 文件
    python scripts/validate_spec.py workspace/spec_lock.json
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class PageRhythmType(str, Enum):
    """页面节奏类型枚举"""
    STRUCTURAL = "structural"
    FOCAL = "focal"
    ANALYTICAL = "analytical"


class CanvasConfig(BaseModel):
    """画布配置"""
    viewbox: str = Field(
        default="0 0 1280 720",
        description="SVG viewBox 属性值"
    )
    format: str = Field(
        default="PPT 16:9",
        description="画布格式"
    )
    width: int = Field(
        default=1280,
        description="画布宽度"
    )
    height: int = Field(
        default=720,
        description="画布高度"
    )
    margin_left: int = Field(
        default=60,
        description="左边距"
    )
    margin_right: int = Field(
        default=60,
        description="右边距"
    )
    margin_top: int = Field(
        default=50,
        description="上边距"
    )
    margin_bottom: int = Field(
        default=50,
        description="下边距"
    )
    rationale: Optional[str] = Field(
        default=None,
        description="设计理由"
    )

    @field_validator('viewbox')
    @classmethod
    def validate_viewbox(cls, v: str) -> str:
        """验证 viewBox 格式"""
        pattern = r'^0 0 \d+ \d+$'
        if not re.match(pattern, v):
            raise ValueError(f'viewBox 格式无效: {v}，应为 "0 0 width height"')
        return v


class ColorConfig(BaseModel):
    """颜色配置"""
    bg: str = Field(
        default="#FFFFFF",
        description="背景色"
    )
    secondary_bg: str = Field(
        default="#F5F5F5",
        description="次要背景色"
    )
    primary: str = Field(
        default="#4CAF50",
        description="主色"
    )
    accent: str = Field(
        default="#2196F3",
        description="强调色"
    )
    secondary_accent: str = Field(
        default="#FF9800",
        description="次要强调色"
    )
    text: str = Field(
        default="#333333",
        description="正文文字颜色"
    )
    text_secondary: str = Field(
        default="#666666",
        description="次要文字颜色"
    )
    text_tertiary: str = Field(
        default="#999999",
        description="第三级文字颜色"
    )
    border: str = Field(
        default="#E0E0E0",
        description="边框颜色"
    )
    warning: str = Field(
        default="#F44336",
        description="警告色"
    )
    rationale: Optional[str] = Field(
        default=None,
        description="配色理由"
    )

    @field_validator('bg', 'secondary_bg', 'primary', 'accent', 'secondary_accent',
                     'text', 'text_secondary', 'text_tertiary', 'border', 'warning')
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        """验证 HEX 颜色格式"""
        pattern = r'^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$'
        if not re.match(pattern, v):
            raise ValueError(f'无效的 HEX 颜色: {v}')
        return v.upper()


class TypographyConfig(BaseModel):
    """字体配置"""
    font_family: str = Field(
        default='"Microsoft YaHei", Arial, sans-serif',
        description="默认字体族"
    )
    body_family: str = Field(
        default='"Microsoft YaHei", "PingFang SC", Arial, sans-serif',
        description="正文字体族"
    )
    code_family: str = Field(
        default='Consolas, "Courier New", monospace',
        description="代码字体族"
    )
    body: int = Field(
        default=22,
        description="正文字号"
    )
    title: int = Field(
        default=36,
        description="标题字号"
    )
    subtitle: int = Field(
        default=28,
        description="副标题字号"
    )
    section_title: int = Field(
        default=48,
        description="章节标题字号"
    )
    cover_title: int = Field(
        default=60,
        description="封面标题字号"
    )
    annotation: int = Field(
        default=16,
        description="注释字号"
    )
    footer: int = Field(
        default=12,
        description="页脚字号"
    )
    rationale: Optional[str] = Field(
        default=None,
        description="字体选择理由"
    )

    @field_validator('body', 'title', 'subtitle', 'section_title', 'cover_title',
                     'annotation', 'footer')
    @classmethod
    def validate_font_size(cls, v: int) -> int:
        """验证字号范围"""
        if v < 8 or v > 120:
            raise ValueError(f'字号超出范围 (8-120): {v}')
        return v


class IconsConfig(BaseModel):
    """图标配置"""
    library: str = Field(
        default="tabler-filled",
        description="图标库名称"
    )
    inventory: List[str] = Field(
        default_factory=lambda: [
            "building", "wind", "droplet", "flame", "bolt",
            "shield-check", "alert-triangle", "kid", "heart", "book"
        ],
        description="可用图标列表"
    )
    rationale: Optional[str] = Field(
        default=None,
        description="图标选择理由"
    )


class ImageItem(BaseModel):
    """单个图片配置"""
    filename: str = Field(
        description="图片文件名"
    )
    page: Optional[str] = Field(
        default=None,
        description="使用该图片的页面"
    )
    usage: Optional[str] = Field(
        default=None,
        description="用途说明"
    )
    rationale: Optional[str] = Field(
        default=None,
        description="图片选择理由"
    )


class ImagesConfig(BaseModel):
    """图片配置"""
    items: Dict[str, str] = Field(
        default_factory=dict,
        description="图片映射: {页面: 文件名}"
    )
    rationale: Optional[str] = Field(
        default=None,
        description="图片配置理由"
    )


class PageRhythmConfig(BaseModel):
    """页面节奏配置"""
    rhythm: Dict[str, PageRhythmType] = Field(
        default_factory=dict,
        description="页面节奏映射: {页面: 节奏类型}"
    )
    rationale: Optional[str] = Field(
        default=None,
        description="节奏配置理由"
    )


class ProjectInfo(BaseModel):
    """项目信息"""
    name: str = Field(
        description="项目名称"
    )
    description: str = Field(
        default="",
        description="项目描述"
    )
    audience: str = Field(
        default="",
        description="目标受众"
    )
    style: str = Field(
        default="",
        description="设计风格"
    )
    total_pages: int = Field(
        default=13,
        description="总页数"
    )
    created_date: Optional[str] = Field(
        default=None,
        description="创建日期"
    )
    rationale: Optional[str] = Field(
        default=None,
        description="项目信息理由"
    )


class ContentOutlineItem(BaseModel):
    """内容大纲项"""
    page: str = Field(
        description="页面编号"
    )
    title: str = Field(
        description="页面标题"
    )
    layout: str = Field(
        default="",
        description="布局方式"
    )
    content: List[str] = Field(
        default_factory=list,
        description="内容要点"
    )
    notes_file: Optional[str] = Field(
        default=None,
        description="演讲备注文件名"
    )
    rationale: Optional[str] = Field(
        default=None,
        description="内容设计理由"
    )


class ContentOutline(BaseModel):
    """内容大纲"""
    sections: List[ContentOutlineItem] = Field(
        default_factory=list,
        description="内容大纲列表"
    )
    rationale: Optional[str] = Field(
        default=None,
        description="大纲设计理由"
    )


class TechnicalConstraints(BaseModel):
    """技术约束"""
    forbidden_elements: List[str] = Field(
        default_factory=lambda: [
            "rgba()",
            "<style>", "class", "<foreignObject>", "textPath",
            "@font-face", "<animate*>", "<script>", "<iframe>",
            "<symbol>+<use>"
        ],
        description="禁止使用的元素和属性"
    )
    forbidden_patterns: List[str] = Field(
        default_factory=lambda: [
            "<g opacity>",
            "HTML 命名实体"
        ],
        description="禁止的模式"
    )
    xml_escape_chars: List[str] = Field(
        default_factory=lambda: ["&", "<", ">", '"', "'"],
        description="需要转义的 XML 字符"
    )
    xml_escape_entities: List[str] = Field(
        default_factory=lambda: ["&amp;", "&lt;", "&gt;", "&quot;", "&apos;"],
        description="对应的 XML 转义实体"
    )
    rationale: Optional[str] = Field(
        default=None,
        description="技术约束理由"
    )


class SpecLock(BaseModel):
    """执行锁定配置主模型"""
    project: ProjectInfo = Field(
        default_factory=ProjectInfo,
        description="项目信息"
    )
    canvas: CanvasConfig = Field(
        default_factory=CanvasConfig,
        description="画布配置"
    )
    colors: ColorConfig = Field(
        default_factory=ColorConfig,
        description="颜色配置"
    )
    typography: TypographyConfig = Field(
        default_factory=TypographyConfig,
        description="字体配置"
    )
    icons: IconsConfig = Field(
        default_factory=IconsConfig,
        description="图标配置"
    )
    images: ImagesConfig = Field(
        default_factory=ImagesConfig,
        description="图片配置"
    )
    page_rhythm: PageRhythmConfig = Field(
        default_factory=PageRhythmConfig,
        description="页面节奏配置"
    )
    content_outline: ContentOutline = Field(
        default_factory=ContentOutline,
        description="内容大纲"
    )
    technical_constraints: TechnicalConstraints = Field(
        default_factory=TechnicalConstraints,
        description="技术约束"
    )
    forbidden: List[str] = Field(
        default_factory=list,
        description="禁止项列表"
    )
    rationale: Optional[str] = Field(
        default=None,
        description="整体设计理由"
    )

    @model_validator(mode='after')
    def validate_consistency(self) -> 'SpecLock':
        """验证配置一致性"""
        # 验证 canvas 尺寸与 viewbox 一致
        viewbox_parts = self.canvas.viewbox.split()
        if len(viewbox_parts) == 4:
            vb_width, vb_height = int(viewbox_parts[2]), int(viewbox_parts[3])
            if self.canvas.width != vb_width or self.canvas.height != vb_height:
                raise ValueError(
                    f'canvas 尺寸 ({self.canvas.width}x{self.canvas.height}) '
                    f'与 viewBox ({vb_width}x{vb_height}) 不一致'
                )
        return self

    def to_json(self, indent: int = 2) -> str:
        """导出为格式化 JSON 字符串"""
        return self.model_dump_json(indent=indent)

    def to_dict(self) -> dict:
        """导出为字典"""
        return self.model_dump()

    @classmethod
    def from_json(cls, json_str: str) -> 'SpecLock':
        """从 JSON 字符串加载"""
        return cls.model_validate_json(json_str)

    @classmethod
    def from_dict(cls, data: dict) -> 'SpecLock':
        """从字典加载"""
        return cls.model_validate(data)


# 便捷的类型别名
SpecLockType = SpecLock


if __name__ == '__main__':
    # 测试模型创建
    spec = SpecLock()
    print("默认配置创建成功")
    print(f"画布: {spec.canvas.width}x{spec.canvas.height}")
    print(f"主色: {spec.colors.primary}")
    print(f"正文字号: {spec.typography.body}")
