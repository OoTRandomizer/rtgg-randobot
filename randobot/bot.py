from racetime_bot import Bot

from .handler import RandoHandler
from .midos_house import MidosHouse
from .zsr import ZSR


class RandoBot(Bot):
    """
    RandoBot base class.
    """
    def __init__(self, ootr_api_key, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.zsr = ZSR(ootr_api_key)
        self.midos_house = MidosHouse()

    def get_handler_class(self):
        return RandoHandler

    def get_handler_kwargs(self, *args, **kwargs):
        return {
            **super().get_handler_kwargs(*args, **kwargs),
            'zsr': self.zsr,
            'midos_house': self.midos_house,
        }
