# encoding:utf-8

import time
from datetime import datetime

import openai
import openai.error
from bot.bot import Bot
from bot.zhipuai.zhipu_ai_session import ZhipuAISession
from bot.zhipuai.zhipu_ai_image import ZhipuAIImage
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from config import conf, load_config
from zhipuai import ZhipuAI


# ZhipuAI对话模型API
class ZHIPUAIBot(Bot, ZhipuAIImage):
    # class YourClassName:  # 这里假设类名为 YourClassName，请根据实际情况替换
    def __init__(self):
        """
            初始化函数，用于设置类的属性和初始化配置。

            本函数中初始化了与智谱AI相关的会话管理和客户端配置。
            它首先调用了父类的构造函数，然后初始化了会话管理和客户端对象。
            """
        super().__init__()  # 调用父类的构造方法
        # 初始化会话管理，指定对话模型为配置文件中的模型或默认的"ZHIPU_AI"
        self.sessions = SessionManager(ZhipuAISession, model=conf().get("model") or "ZHIPU_AI")
        self.search_prompt = """
            # 以下是来自互联网的信息：
            {search_result}

            # 当前日期: 2024-XX-XX

            # 要求：
            根据最新发布的信息回答用户问题，当回答引用了参考信息时，必须在句末使用对应的来源网站的[ref_序号:来源名称,标题,链接]来标明参考信息来源。
            """
        # 初始化对话模型的参数
        self.args = {
            "model": conf().get("model") or "glm-4-flash",  # 对话模型的名称，使用配置文件中的设置或默认值"glm-4"
            "temperature": conf().get("temperature", 0.9),  # 温度参数，控制输出的随机性，值在(0,1)之间(智谱AI 的温度不能取 0 或者 1)
            "top_p": conf().get("top_p", 0.7),  # top_p 参数，与温度参数一起控制输出的随机性，值在(0,1)之间(智谱AI 的 top_p 不能取 0 或者 1)
            "tools": [{
                "type": "web_search",
                "web_search": {"enable": True,  # 启用搜索
                               "search_result": True,  # 启用返回搜索结果.禁用False，启用：True，默认为禁用
                               "search_prompt": self.search_prompt}}]  # search_prompt:
            # 搜索提示，用于在搜索时提供额外的上下文信息，例如搜索的领域或主题等。
        }
        # 初始化智谱AI客户端，使用配置文件中的API密钥
        self.client = ZhipuAI(api_key=conf().get("zhipu_ai_api_key"))

    def reply(self, query, context=None):
        # acquire reply content
        if context.type == ContextType.TEXT:
            logger.info("[ZHIPU_AI] query={}".format(query))

            session_id = context["session_id"]
            reply = None
            clear_memory_commands = conf().get("clear_memory_commands", ["#清除记忆"])
            if query in clear_memory_commands:
                self.sessions.clear_session(session_id)
                reply = Reply(ReplyType.INFO, "记忆已清除")
            elif query == "#清除所有":
                self.sessions.clear_all_session()
                reply = Reply(ReplyType.INFO, "所有人记忆已清除")
            elif query == "#更新配置":
                load_config()
                reply = Reply(ReplyType.INFO, "配置已更新")
            if reply:
                return reply
            session = self.sessions.session_query(query, session_id)
            logger.debug("[ZHIPU_AI] session query={}".format(session.messages))

            api_key = context.get("openai_api_key") or openai.api_key
            model = context.get("gpt_model")
            new_args = None
            if model:
                new_args = self.args.copy()
                new_args["model"] = model
            # if context.get('stream'):
            #     # reply in stream
            #     return self.reply_text_stream(query, new_query, session_id)

            reply_content = self.reply_text(session, api_key, args=new_args)
            logger.debug(
                "[ZHIPU_AI] new_query={}, session_id={}, reply_cont={}, completion_tokens={}".format(
                    session.messages,
                    session_id,
                    reply_content["content"],
                    reply_content["completion_tokens"],
                )
            )
            if reply_content["completion_tokens"] == 0 and len(reply_content["content"]) > 0:
                reply = Reply(ReplyType.ERROR, reply_content["content"])
            elif reply_content["completion_tokens"] > 0:
                self.sessions.session_reply(reply_content["content"], session_id, reply_content["total_tokens"])
                reply = Reply(ReplyType.TEXT, reply_content["content"])
            else:
                reply = Reply(ReplyType.ERROR, reply_content["content"])
                logger.debug("[ZHIPU_AI] reply {} used 0 tokens.".format(reply_content))
            return reply
        elif context.type == ContextType.IMAGE_CREATE:
            ok, retstring = self.create_img(query, 0)
            reply = None
            if ok:
                reply = Reply(ReplyType.IMAGE_URL, retstring)
            else:
                reply = Reply(ReplyType.ERROR, retstring)
            return reply

        else:
            reply = Reply(ReplyType.ERROR, "Bot不支持处理{}类型的消息".format(context.type))
            return reply

    def reply_text(self, session: ZhipuAISession, api_key=None, args=None, retry_count=0) -> dict:
        """
        call openai's ChatCompletion to get the answer
        :param session: a conversation session
        :param session_id: session id
        :param retry_count: retry count
        :return: {}
        """
        try:
            # if conf().get("rate_limit_chatgpt") and not self.tb4chatgpt.get_token():
            #     raise openai.error.RateLimitError("RateLimitError: rate limit exceeded")
            # if api_key == None, the default openai.api_key will be used
            if args is None:
                args = self.args

            # 获取当前日期
            current_date = datetime.now().strftime("%Y-%m-%d")
            # 添加系统消息
            system_message = {
                "role": "system",
                "content": f"You are AI Jarvis, capable of accessing the internet and using online information to provide answers when appropriate. Speak in English only to anyone, even if they speak a local language to you. Must reply succinctly and concisely. Today's date is {current_date}."
            }
            # response = openai.ChatCompletion.create(api_key=api_key, messages=session.messages, **args)
            response = self.client.chat.completions.create(messages=session.messages, **args)
            # logger.debug("[ZHIPU_AI] response={}".format(response))
            # logger.info("[ZHIPU_AI] reply={}, total_tokens={}".format(response.choices[0]['message']['content'], response["usage"]["total_tokens"]))

            return {
                "total_tokens": response.usage.total_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "content": response.choices[0].message.content,
            }
        except Exception as e:
            need_retry = retry_count < 2
            result = {"completion_tokens": 0, "content": "我现在有点累了，等会再来吧"}
            if isinstance(e, openai.error.RateLimitError):
                logger.warn("[ZHIPU_AI] RateLimitError: {}".format(e))
                result["content"] = "提问太快啦，请休息一下再问我吧"
                if need_retry:
                    time.sleep(20)
            elif isinstance(e, openai.error.Timeout):
                logger.warn("[ZHIPU_AI] Timeout: {}".format(e))
                result["content"] = "我没有收到你的消息"
                if need_retry:
                    time.sleep(5)
            elif isinstance(e, openai.error.APIError):
                logger.warn("[ZHIPU_AI] Bad Gateway: {}".format(e))
                result["content"] = "请再问我一次"
                if need_retry:
                    time.sleep(10)
            elif isinstance(e, openai.error.APIConnectionError):
                logger.warn("[ZHIPU_AI] APIConnectionError: {}".format(e))
                result["content"] = "我连接不到你的网络"
                if need_retry:
                    time.sleep(5)
            else:
                logger.exception("[ZHIPU_AI] Exception: {}".format(e), e)
                need_retry = False
                self.sessions.clear_session(session.session_id)

            if need_retry:
                logger.warn("[ZHIPU_AI] 第{}次重试".format(retry_count + 1))
                return self.reply_text(session, api_key, args, retry_count + 1)
            else:
                return result
