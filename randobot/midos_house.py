import time

import gql
import gql.transport.aiohttp

class MidosHouse:
    def __init__(self):
        self.client = gql.Client(transport=gql.transport.aiohttp.AIOHTTPTransport(url='https://midos.house/api/v1/graphql'))
        self.cache = None
        self.cache_last_updated = None

    async def handles_custom_goal(self, goal_name):
        if self.cache is None or time.monotonic() > self.cache_last_updated + 60 * 60 * 24:
            try:
                query = gql.gql("""
                    query {
                        goalNames
                    }
                """)
                self.cache_last_updated = time.monotonic()
                self.cache = self.client.execute(query)['goalNames']
            except gql.transport.exceptions.TransportError: # if anything goes wrong, assume Mido's House is down and we should handle the room
                self.cache = None
                return False
        return goal_name in self.cache
