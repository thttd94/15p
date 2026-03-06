VERSION="Proxy Excel Engine v3 ULTRA"

import xlwings as xw
import asyncio
import socks

CHECK_HOST="1.1.1.1"
CHECK_PORT=80

TIMEOUT=1

MAX_ROWS=500
MAX_COL=120

LOOP_DELAY=1

proxy_cache={}


def get_target_sheets(wb):

    sheets=[]

    for s in wb.sheets:

        if s.name.upper().startswith("TIKTOK"):

            sheets.append(s)

    return sheets



def scan_sheet(sheet):

    proxies=[]
    cells=[]

    for col in range(1,MAX_COL,3):

        proxy_col=col+1
        status_col=col+2

        values=sheet.range((2,proxy_col),(MAX_ROWS,proxy_col)).value

        if not isinstance(values,list):
            values=[values]

        for i,v in enumerate(values):

            row=i+2
            cell=sheet.range((row,status_col))

            if not v:

                cell.value=""
                cell.color=None
                continue

            proxies.append(v)
            cells.append((sheet,row,status_col,v))

    return proxies,cells



async def check_proxy(proxy):

    try:

        ip,port,user,password=proxy.split(":")

        s=socks.socksocket()

        s.set_proxy(
            socks.SOCKS5,
            ip,
            int(port),
            True,
            user,
            password
        )

        s.settimeout(TIMEOUT)

        s.connect((CHECK_HOST,CHECK_PORT))
        s.close()

        return "LIVE"

    except:

        return "DIE"



async def engine():

    print(VERSION)

    wb=xw.books.active

    while True:

        all_proxies=[]
        all_cells=[]

        for sheet in get_target_sheets(wb):

            proxies,cells=scan_sheet(sheet)

            all_proxies+=proxies
            all_cells+=cells


        unique=list(set(all_proxies))

        tasks=[check_proxy(p) for p in unique]

        results=await asyncio.gather(*tasks)


        for i,p in enumerate(unique):

            proxy_cache[p]=results[i]


        app=xw.apps.active
        app.screen_updating=False


        for sheet,row,col,p in all_cells:

            result=proxy_cache.get(p,"DIE")

            cell=sheet.range((row,col))

            cell.value=result

            if result=="LIVE":

                cell.color=(0,200,0)

            else:

                cell.color=(255,120,120)


        app.screen_updating=True


        print("checked",len(unique),"unique proxies")

        await asyncio.sleep(LOOP_DELAY)



asyncio.run(engine())
