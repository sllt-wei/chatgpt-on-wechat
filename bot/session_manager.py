from common.expired_dict import ExpiredDict
from common.log import logger
from config import conf


class Session(object):
    """
    Session类用于管理一次会话中的所有消息，包括系统提示、用户查询和助手回复。
    它可以根据会话ID初始化会话，并支持添加用户查询和助手回复到会话消息列表中。
    """
    def __init__(self, session_id, system_prompt=None):
        """
        初始化Session对象。

        参数:
        - session_id: 会话ID，用于唯一标识一次会话。
        - system_prompt: 系统提示，用于设置会话的初始上下文。
        """
        self.session_id = session_id
        self.messages = []
        if system_prompt is None:
            self.system_prompt = conf().get("character_desc", "")
        else:
            self.system_prompt = system_prompt

    # 重置会话
    def reset(self):
        """
        重置会话消息列表，仅保留系统提示。
        """
        system_item = {"role": "system", "content": self.system_prompt}
        self.messages = [system_item]

    def set_system_prompt(self, system_prompt):
        """
        设置会话的系统提示并重置会话。

        参数:
        - system_prompt: 新的系统提示。
        """
        self.system_prompt = system_prompt
        self.reset()

    def add_query(self, query):
        """
        添加用户查询到会话消息列表中。

        参数:
        - query: 用户的查询。
        """
        user_item = {"role": "user", "content": query}
        self.messages.append(user_item)

    def add_reply(self, reply):
        """
        添加助手回复到会话消息列表中。

        参数:
        - reply: 助手的回复。
        """
        assistant_item = {"role": "assistant", "content": reply}
        self.messages.append(assistant_item)

    def discard_exceeding(self, max_tokens=None, cur_tokens=None):
        """
        根据最大token限制丢弃超出的消息。

        参数:
        - max_tokens: 最大token限制。
        - cur_tokens: 当前token数量。
        """
        raise NotImplementedError

    def calc_tokens(self):
        """
        计算会话中所有消息的总token数量。
        """
        raise NotImplementedError


class SessionManager(object):
    """
    SessionManager类用于管理所有会话，包括创建、更新和删除会话。
    它使用字典存储所有活动的会话，并可以根据会话ID快速访问特定会话。
    """
    def __init__(self, sessioncls, **session_args):
        """
        初始化SessionManager对象。

        参数:
        - sessioncls: Session类，用于创建新的会话对象。
        - session_args: 传递给Session类构造函数的额外参数。
        """
        if conf().get("expires_in_seconds"):
            sessions = ExpiredDict(conf().get("expires_in_seconds"))
        else:
            sessions = dict()
        self.sessions = sessions
        self.sessioncls = sessioncls
        self.session_args = session_args

    def build_session(self, session_id, system_prompt=None):
        """
        根据session_id创建或更新会话。

        参数:
        - session_id: 会话ID。
        - system_prompt: 系统提示，如果提供，则更新会话的系统提示。

        返回:
        - session: 创建或更新后的会话对象。
        """
        if session_id is None:
            return self.sessioncls(session_id, system_prompt, **self.session_args)

        if session_id not in self.sessions:
            self.sessions[session_id] = self.sessioncls(session_id, system_prompt, **self.session_args)
        elif system_prompt is not None:  # 如果有新的system_prompt，更新并重置session
            self.sessions[session_id].set_system_prompt(system_prompt)
        session = self.sessions[session_id]
        return session

    def session_query(self, query, session_id):
        """
        向指定会话添加用户查询。

        参数:
        - query: 用户的查询。
        - session_id: 会话ID。

        返回:
        - session: 更新后的会话对象。
        """
        session = self.build_session(session_id)
        session.add_query(query)
        try:
            max_tokens = conf().get("conversation_max_tokens", 1000)
            total_tokens = session.discard_exceeding(max_tokens, None)
            logger.debug("prompt tokens used={}".format(total_tokens))
        except Exception as e:
            logger.warning("Exception when counting tokens precisely for prompt: {}".format(str(e)))
        return session

    def session_reply(self, reply, session_id, total_tokens=None):
        """
        向指定会话添加助手回复。

        参数:
        - reply: 助手的回复。
        - session_id: 会话ID。
        - total_tokens: 当前会话的总token数量。

        返回:
        - session: 更新后的会话对象。
        """
        session = self.build_session(session_id)
        session.add_reply(reply)
        try:
            max_tokens = conf().get("conversation_max_tokens", 1000)
            tokens_cnt = session.discard_exceeding(max_tokens, total_tokens)
            logger.debug("raw total_tokens={}, savesession tokens={}".format(total_tokens, tokens_cnt))
        except Exception as e:
            logger.warning("Exception when counting tokens precisely for session: {}".format(str(e)))
        return session

    def clear_session(self, session_id):
        """
        清除指定的会话。

        参数:
        - session_id: 会话ID。
        """
        if session_id in self.sessions:
            del self.sessions[session_id]

    def clear_all_session(self):
        """
        清除所有会话。
        """
        self.sessions.clear()
