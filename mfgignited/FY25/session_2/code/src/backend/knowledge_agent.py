import asyncio
import json
import logging
import aiohttp
from typing import List
from data_model import DataModel
from models import Message, GroundingResults, GroundingResult
from azure.search.documents.agent.aio import KnowledgeAgentRetrievalClient
from azure.search.documents.agent.models import KnowledgeAgentRetrievalResponse
from azure.search.documents.indexes.models import (
    KnowledgeAgent as AzureSearchKnowledgeAgent,
    KnowledgeAgentTargetIndex,
    KnowledgeAgentAzureOpenAIModel,
    AzureOpenAIVectorizerParameters,
)
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.aio import SearchIndexClient
from grounding_retriever import GroundingRetriever

logger = logging.getLogger("grounding")


class KnowledgeAgentGrounding(GroundingRetriever):
    def __init__(
        self,
        retrieval_agent_client: KnowledgeAgentRetrievalClient,
        search_client: SearchClient,
        index_client: SearchIndexClient,
        data_model: DataModel,
        index_name: str,
        agent_name: str,
        azure_openai_endpoint: str,
        azure_openai_searchagent_deployment: str,
        azure_openai_searchagent_model: str,
    ):
        self.retrieval_agent_client = retrieval_agent_client
        self.search_client = search_client
        self.index_client = index_client
        self.data_model = data_model
        self.index_name = index_name

        self._create_retrieval_agent(
            agent_name,
            azure_openai_endpoint,
            azure_openai_searchagent_deployment,
            azure_openai_searchagent_model,
        )

    def _create_retrieval_agent(
        self,
        agent_name,
        azure_openai_endpoint,
        azure_openai_searchagent_deployment,
        azure_openai_searchagent_model,
    ):
        logger.info(f"Creating retrieval agent for {agent_name}")
        try:
            asyncio.create_task(
                self.index_client.create_or_update_agent(
                    agent=AzureSearchKnowledgeAgent(
                        name=agent_name,
                        target_indexes=[
                            KnowledgeAgentTargetIndex(
                                index_name=self.index_name,
                                default_include_reference_source_data=True,
                            )
                        ],
                        models=[
                            KnowledgeAgentAzureOpenAIModel(
                                azure_open_ai_parameters=AzureOpenAIVectorizerParameters(
                                    resource_url=azure_openai_endpoint,
                                    deployment_name=azure_openai_searchagent_deployment,
                                    model_name=azure_openai_searchagent_model,
                                )
                            )
                        ],
                    )
                )
            )
        except Exception as e:
            logger.error(f"Failed to create/update agent {agent_name}: {str(e)}")
            raise

    async def retrieve(
        self,
        user_message: str,
        chat_thread: List[Message],
        options: dict,
        image_data: str = None,
    ) -> GroundingResults:

        try:
            # Create user content with text and potentially image
            user_content = [{"text": user_message, "type": "text"}]
            
            # If we have an image, we should include it in the user message
            # to let the knowledge agent utilize the visual information
            if image_data and image_data.startswith("data:image"):
                user_content.append({
                    "type": "image_url", 
                    "image_url": {"url": image_data}
                })
            
            messages = [
                *chat_thread,
                {"role": "user", "content": user_content},
            ]

            result = await self.retrieval_agent_client.retrieve(
                retrieval_request={
                    "messages": messages,
                    "target_index_params": [
                        {
                            "indexName": self.index_name,
                            "includeReferenceSourceData": False,
                        }
                    ],
                },
            )

            result_dict = result.as_dict()
            references: List[GroundingResult] = []
            for ref in result_dict["response"]:
                for content in ref.get("content", []):
                    content_text = json.loads(content.get("text", "{}"))
                    for reference in content_text:
                        reference["ref_id"] = self._get_document_id(
                            reference["ref_id"], result
                        )
                        references.append(
                            {
                                "ref_id": reference["ref_id"],
                                "content": reference,
                                "content_type": "text",  # Knowledge agent currently only returns text content
                            }
                        )
            return {
                "references": references,
                "search_queries": self._get_search_queries(result),
            }
        except aiohttp.ClientError as e:
            logger.error(f"Error calling Azure AI Search Retrieval Agent: {str(e)}")
            raise

    async def _get_text_citations(
        self, ref_ids: List[str], grounding_results: GroundingResults
    ) -> List[dict]:
        try:
            citations = []
            for ref_id in ref_ids:
                document = await self.search_client.get_document(ref_id)
                citations.append(self.data_model.extract_citation(document))
            return citations
        except Exception as e:
            logger.error(f"Error creating text citations: {str(e)}")
            raise

    async def _get_image_citations(
        self, ref_ids: List[str], grounding_results: GroundingResults
    ) -> List[dict]:
        return []

    """Need to use document id as the reference id so I can lookkup the document properties for citations"""

    def _get_search_queries(self, response: KnowledgeAgentRetrievalResponse):
        return [
            activity.as_dict()["query"]
            for activity in response.activity
            if activity.type == "AzureSearchQuery"
        ]

    def _get_document_id(
        self, ref_id: str, response: KnowledgeAgentRetrievalResponse
    ) -> str:
        for ref in response.references:
            ref_dict = ref.as_dict()
            if str(ref_dict["id"]) == str(ref_id):
                return ref_dict["doc_key"]
        raise ValueError(f"Reference ID {ref_id} not found in response")
