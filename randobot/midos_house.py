import time

import gql
import gql.transport.aiohttp

class MidosHouse:
    def __init__(self):
        self.client = gql.Client(transport=gql.transport.aiohttp.AIOHTTPTransport(url='https://midos.house/api/v1/graphql'))
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
                self.cache_expires_at = time.monotonic() + 60 * 60 * 24
                self.cache = self.client.execute(query)['goalNames']
            except gql.transport.exceptions.TransportError: # if anything goes wrong, assume Mido's House is down and we should handle the room
                self.cache_expires_at = time.monotonic() + 60
                self.cache = None
        if self.cache is None:
            return False
        return goal_name in self.cache
