import gql
import gql.transport.aiohttp
from racetime_bot import Bot

from .handler import RandoHandler
from .zsr import ZSR


class RandoBot(Bot):
    """
    RandoBot base class.
    """
    def __init__(self, ootr_api_key, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.zsr = ZSR(ootr_api_key)
        self.midos_house = gql.Client(transport=gql.transport.aiohttp.AIOHTTPTransport(url='https://midos.house/api/v1/graphql'))

    def get_handler_class(self):
        return RandoHandler

    def get_handler_kwargs(self, *args, **kwargs):
        return {
            **super().get_handler_kwargs(*args, **kwargs),
            'zsr': self.zsr,
            'midos_house': self.midos_house,
        }
