import os
from collections.abc import AsyncGenerator
from typing import Protocol

from langchain_core.messages import HumanMessage
from langchain_redis import RedisChatMessageHistory

from agents.common.data import Message
from agents.graph import IGraph, KymaGraph
from agents.memory.redis_checkpointer import RedisSaver, initialize_async_pool
from initial_questions.inital_questions import (
    IInitialQuestionsHandler,
    InitialQuestionsHandler,
)
from services.k8s import IK8sClient
from utils.logging import get_logger
from utils.models import LLM, IModel, ModelFactory
from utils.singleton_meta import SingletonMeta

logger = get_logger(__name__)

REDIS_URL = f"{os.getenv('REDIS_URL')}/0"


class IService(Protocol):
    """Service interface"""

    def new_conversation(
        self, session_id: str, k8s_client: IK8sClient, message: Message
    ) -> list[str]:
        """Initialize a new conversation."""
        ...

    def handle_request(
        self, conversation_id: str, message: Message
    ) -> AsyncGenerator[bytes, None]:
        """Handle a request for a conversation"""
        ...


class ConversationService(metaclass=SingletonMeta):
    """
    Implementation of the conversation service.
    This class is a singleton and should be used to handle the conversation.
    """

    _model: IModel
    _init_questions_handler: IInitialQuestionsHandler
    _kyma_graph: IGraph

    def __init__(
        self,
        model: IModel | None = None,
        initial_questions_handler: IInitialQuestionsHandler | None = None,
    ) -> None:
        # Set up the Model, which contains the llm.
        self._model = (
            model if model is not None else ModelFactory().create_model(LLM.GPT4O_MODEL)
        )

        # Set up the initial question handler, which will handle all the logic to generate the inital questions.
        self._init_questions_handler = (
            initial_questions_handler
            if initial_questions_handler is not None
            else InitialQuestionsHandler(model=self._model)
        )

        # Set up the Kyma Graph which allows access to stored conversation histories.
        redis_saver = RedisSaver(async_connection=initialize_async_pool(url=REDIS_URL))
        self._kyma_graph = KymaGraph(model=self._model, memory=redis_saver)

    def new_conversation(
        self, session_id: str, k8s_client: IK8sClient, message: Message
    ) -> list[str]:
        """Initialize a new conversation."""

        logger.info(
            f"Initializing conversation ({session_id}) with namespace '{message.namespace}', "
            f"resource_type '{message.resource_kind}' and resource name {message.resource_name}"
        )

        # Fetch the context for our questions from the Kubernetes cluster.
        k8s_context = self._init_questions_handler.fetch_relevant_data_from_k8s_cluster(
            message=message, k8s_client=k8s_client
        )

        # Pass the context to the initial question handler to generate the questions.
        questions = self._init_questions_handler.generate_questions(context=k8s_context)

        # Store the Kubernetes context in the Redis chat history.
        history = RedisChatMessageHistory(session_id=session_id, redis_url=REDIS_URL)
        history.add_message(
            message=HumanMessage(
                content=f"These are the information I got from my Kubernetes cluster:\n{k8s_context}"
            )
        )

        return questions

    async def handle_request(
        self, conversation_id: str, message: Message
    ) -> AsyncGenerator[bytes, None]:
        """Handle a request"""

        logger.info("Processing request...")

        async for chunk in self._kyma_graph.astream(conversation_id, message):
            logger.debug(f"Sending chunk: {chunk}")
            yield f"{chunk}".encode()