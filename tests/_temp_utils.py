from __future__ import annotations

import errno
import tempfile
import time


class GitTemporaryDirectory(tempfile.TemporaryDirectory):
    """清理可能被字节 Git 异步日志短暂重建目录的测试仓库。"""

    def cleanup(self) -> None:
        deadline = time.monotonic() + 2
        while True:
            try:
                super().cleanup()
                return
            except OSError as error:
                if error.errno != errno.ENOTEMPTY or time.monotonic() >= deadline:
                    raise
                # 只重试 macOS 的目录非空竞争，权限等真实错误仍立即暴露。
                time.sleep(0.02)
