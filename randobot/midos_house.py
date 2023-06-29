import time

import gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportError


class MidosHouse:
    def __init__(self):
        self.client = gql.Client(transport=AIOHTTPTransport(url='https://midos.house/api/v1/graphql'))
        self.cache = None
        self.cache_expires_at = time.monotonic()

    async def handles_custom_goal(self, goal_name):
        if time.monotonic() > self.cache_expires_at:
            try:
                query = gql.gql("""
                    query {
                        goalNames
                    }
                """)
                response = await self.client.execute_async(query)
                self.cache_expires_at = time.monotonic() + 60 * 60 * 24
                self.cache = response['goalNames']
            except TransportError: # if anything goes wrong, assume Mido's House is down and we should handle the room
                self.cache_expires_at = time.monotonic() + 60
                self.cache = None
        if self.cache is None:
            return False
        return goal_name in self.cache
