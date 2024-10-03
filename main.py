import asyncio

from aiocdp import setup_default_factories

from aiocdp_utils.shared import ioc


async def main(
        keyword: str,

):
    setup_default_factories()

    chrome = ioc.get_chrome()
    targets = []

    for target in chrome.iterate_targets():
        if target.get_info().get_type() == 'page':
            targets.append(target)

    if not targets:
        chrome.start()

    linkedin_targets = []

    for target in targets:
        url = target.get_info().get_url()

        for prefix in [
            'https://linkedin.com',
            'https://www.linkedin.com'
        ]:
            if url.startswith(prefix):
                linkedin_targets.append(target)

    # if not linkedin_targets:
    chrome.new_tab('https://linkedin.com/jobs/search/?keywords=' + keyword)


if __name__ == "__main__":
    asyncio.run(main('python software engineer'))
