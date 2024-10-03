import base64
import json
from dataclasses import dataclass, field

from aiocdp import IEventStreamReader, ISession


@dataclass
class HTTPStreamEvent:
    """
    Represents a single http request and response.
    """

    """
    The raw event.
    """
    raw: dict

    """
    The base64 decoded result from calling Fetch.getResponseBody.
    """
    response_body: dict

    """
    Whether or not the response body is json.
    """
    response_body_is_json: bool

    @property
    def request_post_data(self) -> dict | None:
        """
        The request post data.
        """
        try:
            return json.loads(self.raw['params']['request']['postData'])

        except (json.JSONDecodeError, KeyError):
            return None

    @property
    def url(self) -> str:
        """
        The url of the request.
        """
        return self.raw['params']['request']['url']


@dataclass
class HTTPStream:
    """
    Represents a stream of http requests and responses.
    """

    """
    The session that this stream is associated with.
    """
    session: ISession

    """
    The url patterns that this stream is listening for.
    """
    url_patterns: list[str]

    """
    The stream that is listening for events.
    """
    stream: IEventStreamReader = field(
        init=False,
        default=None
    )

    def is_open(self):
        """
        Public readonly access to the stream status.
        """
        if not self.stream:
            return False

        return not self.stream.is_closed()

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False

    async def open(self):
        self.stream = self.session.open_stream([
            'Fetch.requestPaused'
        ])

        await self.session.send_and_await_response(
            'Fetch.enable',
            {
                'patterns': [
                    {
                        'urlPattern': url_pattern,
                        'requestStage': 'Response'
                    }
                    for url_pattern
                    in self.url_patterns
                ]
            }
        )

    async def close(self):
        await self.session.send_and_await_response('Fetch.disable')
        self.stream.close()

    async def iterate(self):
        async for event in self.stream.iterate():
            data = await self.session.send_and_await_response(
                'Fetch.getResponseBody',
                {
                    'requestId': event['params']['requestId']
                }
            )

            await self.session.send(
                'Fetch.continueRequest',
                {
                    'requestId': event['params']['requestId']
                }
            )

            body = data['body']

            if data['base64Encoded']:
                body = base64.b64decode(body)
                body = body.decode('utf-8')

            try:
                body = json.loads(body)
                is_json = True

            except json.JSONDecodeError:
                is_json = False

            yield HTTPStreamEvent(
                raw=event,
                response_body=body,
                response_body_is_json=is_json
            )