import os
import discord
import requests
import json
import aiohttp
import asyncio
import matplotlib
import io
matplotlib.use("Agg") 
import matplotlib.pyplot as plt
from matplotlib import font_manager
from discord.ext import commands
from requests import Response
token="YOUR TOKEN HERE"
intents= discord.Intents.default()
intents.message_content=True
bot=commands.Bot(command_prefix="!",intents=intents)
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"]
plt.rcParams["axes.unicode_minus"] = False
API = "https://api.earthmc.net/v4"
#Kuze_Hibiki 版权所有 盗窃死妈
#函数部分
_cache = {}
def make_autopct(values):
    def my_autopct(pct):
        total = sum(values)
        val = pct * total / 100
        return f"{pct:.1f}%\n{val:,.0f}G"
    return my_autopct
@bot.command()
async def api_post(session, path, payload):
    async with session.post(f"{API}/{path}", json=payload) as r:
        r.raise_for_status()
        return await r.json()
async def get_nation(session, name):
    data = await api_post(session, "nations", {"query": name})
    return data[0] if data else None
async def get_town(session, query):
    data = await api_post(session, "towns", {"query": query})
    return data[0] if data else None
#饼图
async def get_players(session, uuids):
    if not uuids:
        return []
    data = await api_post(session, "players", {"query": uuids})
    return data
async def get_player(session, uuid):
    data = await api_post(session, "players", {"query": uuid})
    return data[0] if data else None
def pie_chart(labels, values, title):
    fig, ax = plt.subplots(figsize=(8, 8))
    pairs = sorted(zip(labels, values), key=lambda x: -x[1])
    total = sum(values) or 1
    main, other = [], 0
    for name, v in pairs:
        if v / total < 0.02:       
            other += v
        else:
            main.append((name, v))
    if other:
        main.append(("其他", other))

    lbl = [n for n, _ in main]
    val = [v for _, v in main]

    ax.pie(val, labels=lbl,  autopct=make_autopct(val), startangle=90,
           counterclock=False)
    ax.set_title(title)
    ax.axis("equal")

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=110)
    plt.close(fig)
    buf.seek(0)
    return buf
#饼图输出
@bot.hybrid_command(name="nationwealth", description="统计国家各城镇与居民财产占比")
async def nation_wealth(ctx, nation_name: str):
    await ctx.defer() 

    async with aiohttp.ClientSession() as session:
        nation = await get_nation(session, nation_name)
        if not nation:
            await ctx.send("找不到该国家")
            return
        raw_towns = nation.get("towns") or []
        town_uuids = [
            t if isinstance(t, str) else t.get("uuid")
            for t in raw_towns
        ]
        town_uuids = [u for u in town_uuids if u]
        town_residents = {}       
        all_resident_uuids = set()

        # 城镇
        towns_data = await api_post(session, "towns", {"query": town_uuids}) \
            if town_uuids else []

        for t in towns_data:
            tname = t.get("name") or t.get("uuid")
            residents = t.get("residents") or []
            ruuids = [
                r if isinstance(r, str) else r.get("uuid")
                for r in residents
            ]
            ruuids = [u for u in ruuids if u]
            town_residents[tname] = ruuids
            all_resident_uuids.update(ruuids)

        if not all_resident_uuids:
            await ctx.send("该国没有居民")
            return

        #玩家余额
        all_resident_uuids = list(all_resident_uuids)
        players = await get_players(session, all_resident_uuids)
    p_info = {}
    for p in players:
        uuid = p.get("uuid")
        name = p.get("name") or uuid
        stats = p.get("stats") or {}
        bal = stats.get("balance", 0) or 0
        p_info[uuid] = (name, bal)
    town_wealth = {}  
    resident_wealth = {}        

    for tname, ruuids in town_residents.items():
        s = 0
        for u in ruuids:
            if u in p_info:
                nm, bal = p_info[u]
                s += bal
                resident_wealth[nm] = bal
        town_wealth[tname] = s
    loop = asyncio.get_event_loop()
    print("town_wealth:", town_wealth)
    print("resident_wealth sample:", list(resident_wealth.items())[:5])
    town_wealth = {k: v for k, v in town_wealth.items() if v > 0}
    resident_wealth = {k: v for k, v in resident_wealth.items() if v > 0}

    if not town_wealth and not resident_wealth:
        await ctx.send("没有可统计的财产数据")
        return
    buf1 = await loop.run_in_executor(
        None, pie_chart,
        list(town_wealth.keys()), list(town_wealth.values()),
        f"{nation_name} 各城镇财产占比"
    )
    top = sorted(resident_wealth.items(), key=lambda x: -x[1])[:15]
    buf2 = await loop.run_in_executor(
        None, pie_chart,
        [n for n, _ in top], [v for _, v in top],
        f"{nation_name} 财产最多的居民占比 (Top15)"
    )

    files = [
        discord.File(buf1, filename="towns.png"),
        discord.File(buf2, filename="residents.png"),
    ]
    await ctx.send(files=files)
#同步指令
@bot.command()
async def synccommands(ctx):
    await bot.tree.sync()
    await ctx.send("已同步")
#功能部分
@bot.hybrid_command()
async def town(ctx,a:str):
    resp = requests.post('https://api.earthmc.net/v4/towns', json={"query": a})
    data = resp.json()
    if not data:
        await ctx.send("找不到该城镇")
        return
    town_data = data[0]       
    nation=town_data.get("nation")
    nation_name = nation.get("name") if nation else "无"
    mayor=town_data.get("mayor")
    mayor_name=mayor.get("name")
    if mayor_name=="ClayCoffee":
        await ctx.send(f"匪窝:{town_data['name']} 所属国家:{nation_name} 罪大恶极的战争罪犯:{mayor_name}")
    else:
        await ctx.send(f"城镇名: {town_data['name']} 所属国家: {nation_name} 城主{mayor_name}")
@bot.hybrid_command()
async def nation(ctx,a:str):
    resp = requests.post('https://api.earthmc.net/v4/nations', json={"query": a})
    data = resp.json()
    if not data:
        await ctx.send("找不到该国家")
        return
    nation_data = data[0]
    capital=nation_data.get("capital")
    capital_name=capital.get("name")
    king=nation_data.get("king")
    king_name=king.get("name")           
    await ctx.send(f"国家: {nation_data['name']} 首都: {capital_name} 领导人{king_name}")
@bot.hybrid_command()
async def vp(ctx):
    resp=requests.get('https://api.earthmc.net/v4/')
    data=resp.json()
    vp=data.get("voteParty")
    vp_num=vp.get("numRemaining")
    await ctx.send(f"距离vp还有{vp_num}票")
@bot.hybrid_command()
async def version(ctx):
    await ctx.send("版本v0.0.2a 民国115年9月19日")
bot.run(token)