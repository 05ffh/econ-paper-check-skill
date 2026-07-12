# providers package
"""
Providers · M3 v1.6.0

- base.py: 抽象基类 + 数据结构 + 错误类型
- paddle_provider.py: PaddleOCR 3.x 本地（骨架）
- ark_provider.py: 火山方舟多模态（骨架）
- mock_provider.py: 单测用 Mock（可运行）

导入示例：
    from scripts.vision.providers.base import TaskKind, VisionRequest
    from scripts.vision.providers.mock_provider import MockProvider
"""
