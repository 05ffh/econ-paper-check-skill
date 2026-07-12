# providers package
"""
Providers · M3 v1.6.0-rc.3 · v0.3.1 轻量化

- base.py: 抽象基类 + 数据结构 + 错误类型
- ark_provider.py: 火山方舟视觉 Provider · OpenAI Compatible · 真实实现
- mock_provider.py: pytest 用 Mock · 6 种任务全支持（不接主流程）

已删除（v0.3.1）：
- paddle_provider.py（本地 PaddleOCR，v0.2 遗留）

导入示例：
    from scripts.vision.providers.base import TaskKind, VisionRequest
    from scripts.vision.providers.ark_provider import ArkCloudProvider
    from scripts.vision.providers.mock_provider import MockProvider
"""
