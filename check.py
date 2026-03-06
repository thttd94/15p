import xlwings as xw
import asyncio
import socks
import time

VERSION = "Proxy Excel Engine v4 STABLE"

WORKBOOK_NAME = "TIKTOK Japan.xlsx"

CHECK_HOST = "1.1.1.1"
CHECK_PORT = 80

TIMEOUT = 1

MAX_ROWS = 500
BLOCK_STEP = 3

proxy_cache = {}


def get_workbook():
    try:
        return xw.books[WORKBOOK_NAME]
    except:
        return None


def get_target_sheets(wb):

    targets = []

    for s in wb.sheets:
        if s.name.upper().startswith("TIKTOK"):
            targets.append(s)

    return targets


def scan_proxies(wb):

    proxies = {}

    for sheet in get_target_sheets(wb):

        for col in range(1, 120, BLOCK_STEP):

            proxy_col = col + 1
            status_col = col + 2

            values = sheet.range((2, proxy_col), (MAX_ROWS, proxy_col)).value

            if not isinstance(values, list):
                values = [values]

            for i, proxy in enumerate(values):

                row = i + 2

                key = f"{sheet.name}:{row}:{proxy_col}"

                if not proxy:

                    try:
                        sheet.range((row, status_col)).value = ""
                        sheet.range((row, status_col)).color = None
                    except:
                        pass

                    continue

                proxies[key] = (proxy, sheet, row, status_col)

    return proxies


async def check_proxy(proxy):

    try:

        ip, port, user, password = proxy.split(":")

        s = socks.socksocket()

        s.set_proxy(
            socks.SOCKS5,
            ip,
            int(port),
            True,
            user,
            password
        )

        s.settimeout(TIMEOUT)

        s.connect((CHECK_HOST, CHECK_PORT))
        s.close()

        return "LIVE"

    except:

        return "DIE"


async def engine():

    print(VERSION)

    while True:

        try:

            wb = get_workbook()

            if not wb:
                await asyncio.sleep(2)
                continue

            proxies = scan_proxies(wb)

            tasks = []
            task_keys = []

            for key, (proxy, sheet, row, col) in proxies.items():

                if proxy_cache.get(key) == proxy:
                    continue

                proxy_cache[key] = proxy

                tasks.append(check_proxy(proxy))
                task_keys.append(key)

            if tasks:

                results = await asyncio.gather(*tasks)

                for i, result in enumerate(results):

                    key = task_keys[i]

                    proxy, sheet, row, col = proxies[key]

                    try:

                        cell = sheet.range((row, col))

                        cell.value = result

                        if result == "LIVE":
                            cell.color = (0, 200, 0)
                        else:
                            cell.color = (255, 120, 120)

                    except:
                        pass

        except Exception as e:
            print("engine error:", e)

        await asyncio.sleep(1)


asyncio.run(engine())
