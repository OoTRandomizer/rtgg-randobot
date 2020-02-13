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

    def get_handler_class(self):
        return RandoHandler

    def get_handler_kwargs(self, *args, **kwargs):
        return {
            **super().get_handler_kwargs(*args, **kwargs),
            'zsr': self.zsr,
        }
