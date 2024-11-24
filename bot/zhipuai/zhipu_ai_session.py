from bot.session_manager import Session
from common.log import logger

class ZhipuAISession(Session):
    """
    ZhipuAI会话类，继承自Session类。
    用于管理与ZhipuAI模型的会话，包括处理会话中的消息和令牌计数。

    参数:
    - session_id: 会话ID，用于唯一标识一个会话。
    - system_prompt: 系统提示信息，用于设置模型的行为。
    - model: 使用的模型名称，默认为"glm-4"。
    """
    def __init__(self, session_id, system_prompt=None, model="glm-4"):
        super().__init__(session_id, system_prompt)
        self.model = model
        self.reset()
        if not system_prompt:
            logger.warn("[ZhiPu] `character_desc` can not be empty")

    def discard_exceeding(self, max_tokens, cur_tokens=None):
        """
        移除超过最大令牌数的消息。

        参数:
        - max_tokens: 最大令牌数。
        - cur_tokens: 当前令牌数，如果未提供，则会计算当前消息的令牌数。

        返回:
        - cur_tokens: 调整后的当前令牌数。
        """
        precise = True
        try:
            cur_tokens = self.calc_tokens()
        except Exception as e:
            precise = False
            if cur_tokens is None:
                raise e
            logger.debug("Exception when counting tokens precisely for query: {}".format(e))
        while cur_tokens > max_tokens:
            if len(self.messages) > 2:
                self.messages.pop(1)
            elif len(self.messages) == 2 and self.messages[1]["role"] == "assistant":
                self.messages.pop(1)
                if precise:
                    cur_tokens = self.calc_tokens()
                else:
                    cur_tokens = cur_tokens - max_tokens
                break
            elif len(self.messages) == 2 and self.messages[1]["role"] == "user":
                logger.warn("user message exceed max_tokens. total_tokens={}".format(cur_tokens))
                break
            else:
                logger.debug("max_tokens={}, total_tokens={}, len(messages)={}".format(max_tokens, cur_tokens,
                                                                                       len(self.messages)))
                break
            if precise:
                cur_tokens = self.calc_tokens()
            else:
                cur_tokens = cur_tokens - max_tokens
        return cur_tokens

    def calc_tokens(self):
        """
        计算当前消息的令牌数。

        返回:
        - tokens: 当前消息的令牌数。
        """
        return num_tokens_from_messages(self.messages, self.model)

def num_tokens_from_messages(messages, model):
    """
    计算给定消息的令牌数。

    参数:
    - messages: 消息列表，每个消息是一个包含"content"字段的字典。
    - model: 使用的模型名称。

    返回:
    - tokens: 消息的令牌数。
    """
    tokens = 0
    for msg in messages:
        tokens += len(msg["content"])
    return tokens
