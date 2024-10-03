import asyncio
import json
import time
from dataclasses import dataclass

from aiocdp import Session as BaseSession

from aiocdp_utils.shared.commons import chunk
from aiocdp_utils.shared import ioc

QUERY_ALL_BY_XPATH_FUNCTION = '''
function queryAllByXPath(xpath, contextNode = document) {
    const xPathResult = document.evaluate(
        xpath,
        contextNode,
        null,
        XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
        null
    )

    const nodes = []

    for (let i = 0; i < xPathResult.snapshotLength; i++) {
        nodes.push(xPathResult.snapshotItem(i))
    }

    return nodes
}
'''

QUERY_BY_XPATH_FUNCTION = '''
function queryByXPath(xpath, contextNode = document) {
    return document.evaluate(
        xpath,
        contextNode,
        null,
        XPathResult.FIRST_ORDERED_NODE_TYPE,
        null
    ).singleNodeValue
}
'''


def get_center_of_box_model(box_model: dict):
    box = []

    for x, y in chunk(
        box_model['model']['content'],
        2
    ):
        box.append((x, y))

    p1 = box[0]
    p2 = box[2]

    return (
        (p1[0] + p2[0]) / 2,
        (p1[1] + p2[1]) / 2
    )


@dataclass
class Session(BaseSession):
    async def click_node_id(self, node_id: int):
        box_model = await self.send_and_await_response(
            'DOM.getBoxModel',
            {
                'nodeId': node_id
            }
        )

        # noinspection PyTypeChecker
        x, y = get_center_of_box_model(box_model)

        await self.click_xy(x, y)

    async def click_object_id(self, object_id: str):
        node_id = await self.send_and_await_response(
            'DOM.requestNode',
            {
                'objectId': object_id
            }
        )

        # noinspection PyUnresolvedReferences
        await self.click_node_id(
            node_id['nodeId']
        )

    async def click_xpath(self, xpath: str):
        await self.wait_until_xpath_loaded(xpath)

        result = await self.query_by_xpath(xpath)

        await self.click_object_id(
            result['result']['objectId']
        )

    async def click_xy(self, x: int, y: int):
        await self.mouse_press_xy(x, y)
        await self.mouse_release_xy(x, y)

    async def evaluate(self, expression: str) -> dict:
        # noinspection PyTypeChecker
        return await self.send_and_await_response(
            'Runtime.evaluate',
            {
                'expression': expression
            }
        )

    async def evaluate_and_get_json_result(self, expression: str):
        result = await self.evaluate_and_get_value(expression)
        return json.loads(result)

    async def evaluate_and_get_result(self, expression: str):
        result = await self.evaluate(expression)

        if 'exceptionDetails' in result:
            raise Exception(result['exceptionDetails']['exception']['description'])

        return result['result']

    async def evaluate_and_get_value(self, expression: str):
        result = await self.evaluate_and_get_result(expression)
        return result['value']

    async def get_document(self):
        return await self.send_and_await_response(
            'DOM.getDocument',
            {
                'depth': 0
            }
        )

    async def get_current_url(self):
        url = await self.evaluate('window.location.href')
        url = url.get('result').get('value')

        return url

    async def load_query_by_xpath_function(self):
        return await self.evaluate(QUERY_BY_XPATH_FUNCTION)

    async def mouse_press_xy(self, x: int, y: int):
        await self.send_and_await_response(
            'Input.dispatchMouseEvent',
            {
                'type': 'mousePressed',
                'x': x,
                'y': y,
                'button': 'left',
                'clickCount': 1
            }
        )

    async def mouse_release_xy(self, x: int, y: int):
        await self.send_and_await_response(
            'Input.dispatchMouseEvent',
            {
                'type': 'mouseReleased',
                'x': x,
                'y': y,
                'button': 'left',
                'clickCount': 1
            }
        )

    async def navigate(self, url: str):
        return await self.send_and_await_response(
            'Page.navigate',
            {
                'url': url
            }
        )

    async def query_by_xpath(self, xpath: str):
        return await self.evaluate(
            QUERY_BY_XPATH_FUNCTION + f'queryByXPath(`{xpath}`)'
        )

    async def wait_for_js_condition(
            self,
            condition: str,
            retries: int = 3,
            retry_interval: int = 500
    ):
        logger = ioc.get_logger()

        for i in range(retries):
            result = await self.evaluate_and_get_value(condition)

            if result:
                logger.debug('JS condition met')
                return

            logger.debug('JS condition not met')
            await asyncio.sleep(retry_interval / 1000)

        raise Exception(f'Failed to meet condition: {condition}')

    async def wait_until_xpath_loaded(
            self,
            xpath: str,
            timeout: float = 3,
            interval: float = .5
    ):
        await self.load_query_by_xpath_function()

        start_time = time.time()

        while True:
            print('waiting for xpath')
            result = await self.evaluate(f'queryByXPath(`{xpath}`)')

            if result['result'] is not None and result['result']['subtype'] != 'null':
                break

            if time.time() - start_time > timeout:
                raise Exception(f'Timeout waiting for xpath: {xpath}')

            await asyncio.sleep(interval)

    async def write_text(self, text: str, interval: float = .1):
        for char in text:
            await self.send_and_await_response(
                'Input.dispatchKeyEvent',
                {
                    'type': 'char',
                    'text': char
                }
            )
            await asyncio.sleep(interval)