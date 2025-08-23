import os
import logging
import sys
from datetime import timezone, timedelta

# 配置常量
# ... (您的 MODEL 相关代码保持不变) ...
MODEL = os.getenv("GOOGLE_GENAI_MODEL")
if not MODEL:
    MODEL = "gemini-2.5-flash"

USER_TIMEZONE = timezone(timedelta(hours=8))

# ---------------------------
# 日志 (logger) 配置说明
# ---------------------------
# 目标：为整个包提供一个统一的 package-level logger，
# 并导出一个 module-level 的 logger 以供当前模块和其它模块使用。
#
# 要点：
# - package_logger 是为顶层包名（这里使用 'smart_task'）配置的 logger，
#   所有以该包名为前缀的子模块（例如 'smart_task.agents.agent'）都会继承
#   这个配置（level、handler 等）。
# - 为避免重复输出，我们将 package_logger.propagate 设为 False，
#   并在 package_logger 没有 handler 时添加一个 StreamHandler。
# - 导出的 `logger` 使用 package_logger.getChild(__name__)，
#   这样模块名仍保留（方便追踪行号/模块），但会继承 package_logger 的
#   处理器和级别设置。
#
# 使用方法（在其它文件中）：
# - 直接导入共享的 logger：
#     from agents.shared_libraries.constants import logger
#   或（相对导入，若在同包内）：
#     from .shared_libraries.constants import logger
#
# - 如果你想按模块单独创建 logger（可选）：
#     import logging
#     local_logger = logging.getLogger(__name__)
#   但推荐导入共享的 `logger`，以保证输出格式和级别一致。

# 1. 从环境变量获取日志级别
loglevel = os.getenv("GOOGLE_GENAI_FOMC_AGENT_LOG_LEVEL", "INFO")
numeric_level = getattr(logging, loglevel.upper(), None)
if not isinstance(numeric_level, int):
    raise ValueError(f"Invalid log level: {loglevel}")

# 2. 为顶层包创建 package-level logger（与仓库/包名一致）
package_logger = logging.getLogger("smart_task")
package_logger.setLevel(numeric_level)

# 阻止向根 logger 传播，避免重复输出
package_logger.propagate = False

# 3. 创建一个 Formatter 来定义日志格式
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s (line:%(lineno)d)'
)

# 4. 创建并添加 Handler（仅在尚未添加 handler 时）
if not package_logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    package_logger.addHandler(handler)

# 5. 导出 module-level logger，其他模块可以直接导入使用
#    使用 getChild 保持模块名信息，但继承 package_logger 的配置
logger = package_logger.getChild(__name__)

__all__ = ["MODEL", "USER_TIMEZONE", "package_logger", "logger"]