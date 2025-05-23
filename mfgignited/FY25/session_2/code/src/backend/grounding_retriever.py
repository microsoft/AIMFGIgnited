from abc import ABC, abstractmethod
from typing import List
from models import Message, GroundingResults


class GroundingRetriever(ABC):
    """Abstract base class for answer grounding functionality.

    This class defines the contract for classes that implement answer grounding,
    which involves retrieving relevant documents based on user messages and chat history.
    """

    @abstractmethod
    async def retrieve(
        self,
        user_message: str,
        chat_thread: List[Message],
        options: dict,
        image_data: str = None,
    ) -> GroundingResults:
        """Retrieve relevant documents based on the user message and chat history.

        Args:
            user_message: The current user message to process
            chat_thread: The history of messages in the current chat
            options: Configuration options for the retriever
            image_data: Base64-encoded image data if an image was uploaded with the message

        Returns:
            GroundingResults containing the retrieved references and search queries

        Raises:
            Exception: If the search request fails or document processing fails
        """
        pass

    @abstractmethod
    async def _get_text_citations(
        self, ref_ids: List[str], grounding_results: GroundingResults
    ) -> List[dict]:
        pass

    @abstractmethod
    async def _get_image_citations(
        self, ref_ids: List[str], grounding_results: GroundingResults
    ) -> List[dict]:
        pass
