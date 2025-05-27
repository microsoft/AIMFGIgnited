import logging
import time
from typing import List, Dict, TypedDict
from openai import AsyncAzureOpenAI
from data_model import DataModel
from prompts import SEARCH_QUERY_SYSTEM_PROMPT
from models import Message, SearchConfig, GroundingResults
from azure.search.documents.aio import SearchClient
from grounding_retriever import GroundingRetriever

logger = logging.getLogger("groundingapi")


class SearchGroundingRetriever(GroundingRetriever):

    def __init__(
        self,
        search_client: SearchClient,
        openai_client: AsyncAzureOpenAI,
        data_model: DataModel,
        chatcompletions_model_name: str,
    ):
        self.search_client = search_client
        self.openai_client = openai_client
        self.data_model = data_model
        self.chatcompletions_model_name = chatcompletions_model_name

    async def retrieve(
        self,
        user_message: str,
        chat_thread: List[Message],
        options: SearchConfig,
        image_data: str = None,
    ) -> GroundingResults:
        # Generate a search query using both the user message and image analysis if available
        # This enhanced query will contain keywords derived from visual content
        query = await self._generate_search_query(user_message, chat_thread, image_data)

        logger.info(f"Generated search query with image augmentation: {query}")

        try:
            # Create search payload with the image-enriched query
            payload = self.data_model.create_search_payload(query, options)

            search_results = await self.search_client.search(
                search_text=payload["search"],
                top=payload["top"],
                vector_queries=payload["vector_queries"],
                query_type=payload.get("query_type", "simple"),
                select=payload["select"],
            )
        except Exception as e:
            raise Exception(f"Azure AI Search request failed: {str(e)}")

        results_list = []
        async for result in search_results:
            results_list.append(result)

        references = await self.data_model.collect_grounding_results(results_list)

        return {
            "references": references,
            "search_queries": [query],
        }

    async def _generate_search_query(
        self, user_message: str, chat_thread: List[Message], image_data: str = None
    ) -> str:
        try:
            # Build user content that includes image if provided
            user_content = [{"type": "text", "text": user_message}]

            # Add the image to user_content if available, making this a true multimodal request
            if image_data and image_data.startswith("data:image"):
                logger.info("Using image data for search query generation")
                user_content.append(
                    {"type": "image_url", "image_url": {"url": image_data}}
                )

            # System prompt that instructs GPT to analyze both text and image
            system_prompt = SEARCH_QUERY_SYSTEM_PROMPT
            if image_data and image_data.startswith("data:image"):
                system_prompt += (
                    "\n\nThe user has uploaded an image with their query. "
                    + "Carefully analyze the image and extract relevant details including: "
                    + "equipment type, model numbers, brand names, visible parts, damages, "
                    + "error conditions, and any text visible in the image. "
                    + "Combine these visual details with the user's text query to generate "
                    + "comprehensive search terms that will help retrieve relevant technical documentation."
                )

            # Create a multimodal message structure
            messages = [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": system_prompt}],
                },
                *chat_thread,
                {"role": "user", "content": user_content},
            ]

            response = await self.openai_client.chat.completions.create(
                model=self.chatcompletions_model_name,
                messages=messages,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating search query with image: {e}")
            raise Exception(
                f"Error while calling Azure OpenAI to generate a search query: {str(e)}"
            )

    async def _get_image_citations(
        self, ref_ids: List[str], grounding_results: GroundingResults
    ) -> List[dict]:
        return self._extract_citations(ref_ids, grounding_results)

    async def _get_text_citations(
        self, ref_ids: List[str], grounding_results: GroundingResults
    ) -> List[dict]:
        return self._extract_citations(ref_ids, grounding_results)

    def _extract_citations(
        self, ref_ids: List[str], grounding_results: GroundingResults
    ) -> List[dict]:
        if not ref_ids:
            return []

        references = {
            grounding_result["ref_id"]: grounding_result
            for grounding_result in grounding_results
        }
        extracted_citations = []
        for ref_id in ref_ids:
            if ref_id in references:
                ref = references[ref_id]
                extracted_citations.append(self.data_model.extract_citation(ref))
        return extracted_citations
