from abc import ABC, abstractmethod
import asyncio

from data_injestion.models import ProcessRequest


class Strategy(ABC):
    """
    Base class for all strategies. Subclasses must implement the run method.
    """

    @abstractmethod
    async def run(self, request: ProcessRequest, **kwargs):
        """
        Abstract method to be implemented by subclasses.
        This method should define the strategy's execution logic.
        """
        await asyncio.sleep(0)
        pass
