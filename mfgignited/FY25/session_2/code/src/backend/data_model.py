from abc import ABC, abstractmethod
from typing import List
from models import (
    SearchRequestParameters,
    SearchConfig,
    GroundingResult,
    GroundingResults,
)


class DataModel(ABC):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @abstractmethod
    def create_search_payload(
        self, query: str, search_config: SearchConfig
    ) -> SearchRequestParameters:
        """Creates the search request payload."""
        pass

    @abstractmethod
    def extract_citation(
        self,
        document: dict,
    ) -> dict:
        """Extracts citations from search results."""
        pass

    @abstractmethod
    async def collect_grounding_results(self, search_results: List[dict]) -> list:
        """Collects and formats documents from search results."""
        pass


class DocumentPerChunkDataModel(DataModel):
    def create_search_payload(
        self, query: str, search_config: SearchConfig
    ) -> SearchRequestParameters:
        """Creates the search request payload with vector/semantic/hybrid configurations using a configured vectorizer."""

        payload = {
            "search": query,
            "top": search_config["chunk_count"],
            "vector_queries": [
                {
                    "text": query,
                    "fields": "content_embedding",
                    "kind": "text",
                    "k": search_config["chunk_count"],
                }
            ],
            "select": "content_id, content_text, document_title, text_document_id, image_document_id, locationMetadata, content_path",
        }

        # Use semantic search if configured
        if search_config["use_semantic_ranker"]:
            payload["query_type"] = "semantic"

        # Note: In the future, we could add image vector search here if the search index supports it
        # by creating embeddings from the image and using them for similarity search

        return payload

    def extract_citation(self, document):
        return {
            "locationMetadata": document["locationMetadata"],
            "text": document["content_text"],
            "title": document["document_title"],
            "content_id": document["content_id"],
            "docId": (
                document["text_document_id"]
                if document["text_document_id"] is not None
                else document["image_document_id"]
            ),
        }

    async def collect_grounding_results(
        self, search_results: List[dict]
    ) -> List[GroundingResult]:
        collected_documents = []
        for result in search_results:
            is_image = result.get("image_document_id") is not None
            is_text = result.get("text_document_id") is not None

            if is_text and result["content_text"] is not None:
                collected_documents.append(
                    {
                        "ref_id": result["content_id"],
                        "content": {
                            "ref_id": result["content_id"],
                            "text": result["content_text"],
                        },
                        "content_type": "text",
                        **result,
                    }
                )
            elif is_image and result["content_path"] is not None:
                collected_documents.append(
                    {
                        "ref_id": result["content_id"],
                        "content": result["content_path"],
                        "content_type": "image",
                        **result,
                    }
                )
            else:
                raise ValueError(
                    f"Values for both image_chunk_document_id and text_chunk_document_id are missing for result: {result}"
                )
        return collected_documents
