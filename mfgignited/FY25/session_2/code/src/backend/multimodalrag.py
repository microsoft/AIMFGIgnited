import json
import logging
from os import path
from aiohttp import web
from azure.search.documents.aio import SearchClient
from azure.search.documents.agent import KnowledgeAgentRetrievalClient
from azure.storage.blob import ContainerClient
from openai import AsyncAzureOpenAI
from typing import List
from grounding_retriever import GroundingRetriever
from knowledge_agent import KnowledgeAgentGrounding
from helpers import get_blob_as_base64
from search_grounding import SearchGroundingRetriever
from rag_base import RagBase
from data_model import DataModel
from prompts import (
    SYSTEM_PROMPT_NO_META_DATA,
)
from processing_step import ProcessingStep
from models import GroundingResult, Message, SearchConfig, GroundingResults

logger = logging.getLogger("multimodalrag")


class MultimodalRag(RagBase):
    """Handles multimodal RAG with AI Search, streaming responses with SSE."""

    def __init__(
        self,
        knowledge_agent: KnowledgeAgentGrounding,
        search_grounding: SearchGroundingRetriever,
        openai_client: AsyncAzureOpenAI,
        chatcompletions_model_name: str,
        container_client: ContainerClient,
    ):
        super().__init__(
            openai_client,
            chatcompletions_model_name,
        )
        self.container_client = container_client
        self.blob_service_client = container_client._get_blob_service_client()
        self.knowledge_agent = knowledge_agent
        self.search_grounding = search_grounding

    async def _process_request(
        self,
        request_id: str,
        response: web.StreamResponse,
        user_message: str,
        chat_thread: list,
        search_config: SearchConfig,
        image_data: str = None,
    ):
        """Processes a chat request through the RAG pipeline."""
        await self._send_processing_step_message(
            request_id,
            response,
            ProcessingStep(title="Search config", type="code", content=search_config),
        )

        try:
            await self._send_processing_step_message(
                request_id,
                response,
                ProcessingStep(
                    title="Grounding the user message",
                    type="code",
                    content={
                        "user_message": user_message,
                        "chat_thread": chat_thread,
                        "has_image": image_data is not None,
                    },
                ),
            )

            grounding_retriever = self._get_grounding_retriever(search_config)

            grounding_results = await grounding_retriever.retrieve(
                user_message, chat_thread, search_config, image_data
            )

            await self._send_processing_step_message(
                request_id,
                response,
                ProcessingStep(
                    title="Grounding results received",
                    type="code",
                    description=f"Retrieved {len(grounding_results["references"])} results.",
                    content=grounding_results,
                ),
            )

        except Exception as e:
            await self._send_error_message(
                request_id, response, "Grounding failed: " + str(e)
            )
            return

        messages = await self.prepare_llm_messages(
            grounding_results, chat_thread, user_message
        )

        await self._formulate_response(
            request_id,
            response,
            messages,
            grounding_retriever,
            grounding_results,
            search_config,
        )

    def _get_grounding_retriever(self, search_config) -> GroundingRetriever:
        if search_config["use_knowledge_agent"]:
            logger.info("Using knowledge agent for grounding")
            return self.knowledge_agent
        else:
            logger.info("Using search index for grounding")
            return self.search_grounding

    async def prepare_llm_messages(
        self,
        grounding_results: GroundingResults,
        chat_thread: List[Message],
        search_text: str,
        # image_data: str = None,
    ):
        logger.info("Preparing LLM messages")
        try:
            # Create user content with text and image if available
            user_content = [{"text": search_text, "type": "text"}]

            # # Add uploaded image to the user's message if available
            # if image_data and image_data.startswith("data:image"):
            #     logger.info("Adding user uploaded image to the user query")
            #     user_content.append(
            #         {"type": "image_url", "image_url": {"url": image_data}}
            #     )

            # After adding the image to user_content
            # logger.info(f"Image data starts with: {image_data[:30]}...")
            logger.info(f"User content with image: {user_content}")

            # Prepare documents from grounding retrieval separately
            collected_documents = []

            # Add documents from grounding retrieval
            for doc in grounding_results["references"]:
                if doc["content_type"] == "text":
                    collected_documents.append(
                        {
                            "type": "text",
                            "text": str(doc["content"]),
                        }
                    )
                elif doc["content_type"] == "image":
                    collected_documents.append(
                        {
                            "type": "text",
                            "text": f"The image below has the ID: [{doc["ref_id"]}]",
                        }
                    )
                    # blob path differs if index was created through self script in repo or from the portal mulitmodal RAG wizard
                    blob_client = self.container_client.get_blob_client(doc["content"])
                    image_base64 = await get_blob_as_base64(blob_client)
                    if image_base64 is None:
                        content_path = doc["content"]
                        path_split = content_path.split("/")
                        content_container = path_split[0]
                        content_blob = "/".join(path_split[1:])
                        ks_container_client = (
                            self.blob_service_client.get_container_client(
                                content_container
                            )
                        )
                        blob_client = ks_container_client.get_blob_client(content_blob)
                        image_base64 = await get_blob_as_base64(blob_client)

                    collected_documents.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            },
                        }
                    )

            # Construct messages array with proper separation of user query and grounding documents
            messages = [
                {
                    "role": "system",
                    "content": [{"text": SYSTEM_PROMPT_NO_META_DATA, "type": "text"}],
                },
                *chat_thread,
                {
                    "role": "user",
                    "content": user_content,
                },
            ]

            # Only add the documents message if there are retrieved documents
            if collected_documents:
                messages.append(
                    {
                        "role": "user",
                        "content": collected_documents,
                    }
                )

            return messages
        except Exception as e:
            logger.error(f"Error preparing LLM messages: {e}")
            raise e

    async def extract_citations(
        self,
        grounding_retriever: GroundingRetriever,
        grounding_results: List[GroundingResult],
        text_citation_ids: list,
        image_citation_ids: list,
    ) -> dict:
        """Extracts both text and image citations from search results."""
        return {
            "text_citations": await grounding_retriever._get_text_citations(
                text_citation_ids, grounding_results
            ),
            "image_citations": await grounding_retriever._get_image_citations(
                image_citation_ids, grounding_results
            ),
        }
