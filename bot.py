import asyncio
import asyncpg
import hikari
import typing
from hikari import presences
import classyjson as cj

import datetime

_BotT = typing.TypeVar("_BotT", bound="AmorWatcher")
START_STOP_CHANNEL_ID = 866699773700341760


def get_config():
    with open("config.json", "r") as config_file:
        return cj.load(config_file)


async def setup_database_pool():
    CONFIG = get_config()
    return await asyncpg.create_pool(
        host=CONFIG.database.host,  # where db is hosted
        database=CONFIG.database.name,  # name of database
        user=CONFIG.database.user,  # database username
        password=CONFIG.database.passw,  # password which goes with user_id
    )


class AmorWatcher(hikari.GatewayBot):
    def __init__(self):
        self.db = asyncio.get_event_loop().run_until_complete(setup_database_pool())
        super().__init__(
            token=get_config().token,
            intents=hikari.Intents(256),
            banner=None,
            logs=None
        )

    def run(self, *args, **kwargs):
        self.event_manager.subscribe(hikari.PresenceUpdateEvent, self.update)
        self.event_manager.subscribe(hikari.StartedEvent, self.on_started)

        super().run(
            activity=presences.Activity(name=f"𝓐𝓶𝓸𝓻", type=presences.ActivityType.WATCHING),
            status=presences.Status.IDLE,
            idle_since=datetime.datetime.utcnow()
        )

    async def on_started(self, event):
        print("Bot Started!")

    async def update(self, event):
        old_presence = event.old_presence
        presence = event.presence
        user = await event.fetch_user()
        if user.id == 861974078431821885:
            self.stdout_channel = await self.rest.fetch_channel(START_STOP_CHANNEL_ID)
            if old_presence is None:
                if presence.visible_status in [
                    hikari.presences.Status.ONLINE,
                    hikari.presences.Status.IDLE,
                    hikari.presences.Status.DO_NOT_DISTURB
                ]:
                    await self.started()
                    await self.stdout_channel.send("🟢  Amor is now running")
                elif presence.visible_status == hikari.presences.Status.OFFLINE:
                    await self.stopped()
                    await self.stdout_channel.send("🔴  Amor stopped")
                return
            if old_presence.visible_status == hikari.presences.Status.OFFLINE and presence.visible_status in [
                hikari.presences.Status.ONLINE,
                hikari.presences.Status.IDLE,
                hikari.presences.Status.DO_NOT_DISTURB
            ]:
                await self.started()
                await self.stdout_channel.send("🟢  Amor is now running")
            elif old_presence.visible_status in [
                hikari.presences.Status.ONLINE,
                hikari.presences.Status.IDLE,
                hikari.presences.Status.DO_NOT_DISTURB
            ] and presence.visible_status == hikari.presences.Status.OFFLINE:
                await self.stopped()
                await self.stdout_channel.send("🔴  Amor stopped")

    async def started(self):
        last = await self.db.fetchrow(f"SELECT * FROM bot_times WHERE starts = (SELECT MAX (starts) FROM bot_times);")
        if last:
            off: datetime = last["leave"]
            offline: datetime.timedelta = last["offline_time"]
            if off:
                # off = datetime.datetime(off.year, off.month, off.day, off.hour + 2, off.minute, off.second, off.microsecond)
                delta = (datetime.datetime.utcnow() - off) + offline
            else:
                if offline:
                    delta = datetime.datetime.utcnow() + offline
                else:
                    delta = datetime.datetime.utcnow()
        else:
            delta = datetime.timedelta(days=0, seconds=0, microseconds=0, milliseconds=0, minutes=0, hours=0, weeks=0)
        await self.db.execute("INSERT INTO bot_times (joined, offline_time) VALUES ($1, $2)",
                              datetime.datetime.utcnow(),
                              delta)

    async def stopped(self):
        last = await self.db.fetchrow(f"SELECT * FROM bot_times WHERE starts = (SELECT MAX (starts) FROM bot_times);")
        if last:
            on: datetime = last["joined"]
            online: datetime.timedelta = last["online_time"]
            # on = datetime.datetime(on.year, on.month, on.day, on.hour+2, on.minute, on.second, on.microsecond)
            if online:
                delta = (datetime.datetime.utcnow() - on) + online
            else:
                delta = datetime.datetime.utcnow() - on
        else:
            delta = datetime.timedelta(days=0, seconds=0, microseconds=0, milliseconds=0, minutes=0, hours=0, weeks=0)
        await self.db.execute("UPDATE bot_times SET leave=$1, online_time=$2 WHERE starts = (SELECT MAX (starts) FROM bot_times);",
                              datetime.datetime.utcnow(),
                              delta,
                              )
