使用Pydantic-AI进行图片识别和重命名

## 背景

当前项目是基于ai ide环境中，ai根据skills和工具调用自己掌控调度。
但实践中发现由于agent环境限制或模型上下文漂移等问题，很难真正检查把控每个图片的质量。
为了提升图片质量，需要使用Pydantic-AI进行图片识别和重命名。

## 目标

使用Pydantic-AI进行图片逐一识别和重命名，提升图片质量。

## 总体方案

- 新建scripts/llm_process_image.py，处理单独调用llm方面的任务，但它必须能很好地与现有的scripts\web_search.py集成
- llm_process_image.py内部不写死具体llm，但为了方便，可默认提供类似占位符的方式，允许用户配置openai api兼容的baseurl，model name，api key（为了安全，必须用LLM_IMAGE_PROCESS_<模型名大写>_API_KEY 环境变量）。
- 开发测试用的llm设定为 https://token-plan-cn.xiaomimimo.com/v1/models 模型mimo-v2.5,key LLM_IMAGE_PROCESS_MIMOV25_API_KEY
- 使用pydantic-ai框架，其源码已经放到了pydantic-ai（只是供开发参考，不能直接引用）。已经安装到了venv环境。
- web search应该设计成阻塞的，针对每次搜索，阻塞式下载图片内容到内存中，应该立即调用llm_process_image.py，传入对应的 搜索关键词和PPT上下文信息（风格、受众）作为上下文的一部分，**逐个**图片要求llm审阅，是否符合相关性和质量要求（尺寸、比例等），如果llm认为不符合，内存丢弃，如果认为符合，要求llm给出图片内容高度精炼的英文文件名，并自动保存到workspace\images下，作为可用素材。
- 每次运行所有图片审查，总结最后结果，比如抛弃了多少，最终采纳了多少，文件名列表，返回到stdout，供llm查阅决定下一步动作。
- 目前下载设置了很多不必要的复杂度，比如黑名单、统计等、历史记录等，都不必要了，这些功能都删除。保持简单。
- 修改skills.md等文档使其与实际功能一致。
