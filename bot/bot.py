"""
自动回复聊天机器人抽象类
"""

# 从 bridge.context 模块导入 Context 类，用于处理对话上下文
from bridge.context import Context

# 从 bridge.reply 模块导入 Reply 类，用于构建回复消息
from bridge.reply import Reply

class Bot(object):
    """
    聊天机器人的抽象类，定义子类需要实现的接口
    """
    def reply(self, query, context: Context = None) -> Reply:
        """
        生成机器人的自动回复，由子类实现

        :param query: 接收到的消息内容，作为回复的输入
        :param context: 可选的对话上下文，提供额外的回复信息
        :return: 返回一个包含回复内容的 Reply 实例
        """
        raise NotImplementedError
