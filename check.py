VERSION = "Proxy Excel Engine v4 FARM"

import xlwings as xw
import asyncio
import socks
import time

CHECK_HOST = "1.1.1.1"
CHECK_PORT = 80

TIMEOUT = 1

MAX_ROWS = 500
MAX_COL = 120

SCAN_DELAY = 1

proxy_cache = {}
proxy_cells = {}


def get_target_sheets(wb):

    sheets = []

    for s in wb.sheets:

        if s.name.upper().startswith("TIKTOK"):

            sheets.append(s)

    return sheets


def scan_excel(wb):

    proxies = {}

    for sheet in get_target_sheets(wb):

        for col in range(1, MAX_COL, 3):

            proxy_col = col + 1
            status_col = col + 2

            values = sheet.range((2, proxy_col), (MAX_ROWS, proxy_col)).value

            if not isinstance(values, list):
                values = [values]

            for i, v in enumerate(values):

                row = i + 2

                key = f"{sheet.name}:{row}:{proxy_col}"

                if not v:

                    sheet.range((row, status_col)).value = ""
                    sheet.range((row, status_col)).color = None

                    continue

                proxies[key] = (v, sheet, row, status_col)

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

    wb = xw.books.active

    while True:

        current = scan_excel(wb)

        tasks = []
        task_keys = []

        for key, (proxy, sheet, row, col) in current.items():

            if proxy_cache.get(key) == proxy:

                continue

            proxy_cache[key] = proxy

            tasks.append(check_proxy(proxy))
            task_keys.append(key)

        if tasks:

            results = await asyncio.gather(*tasks)

            for i, result in enumerate(results):

                key = task_keys[i]

                proxy, sheet, row, col = current[key]

                cell = sheet.range((row, col))

                cell.value = result

                if result == "LIVE":

                    cell.color = (0, 200, 0)

                else:

                    cell.color = (255, 120, 120)

        await asyncio.sleep(SCAN_DELAY)


asyncio.run(engine())
