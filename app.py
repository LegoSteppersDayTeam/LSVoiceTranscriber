# I dedicate this code to the public domain.
# dependent packages: discord.py, RealtimeSTT
"""
This bot is meant to provide live voice transcription on request by specific
people on the Lego Steppers discord.

Usage:
    1. Join a voice channel
    2. switch to a channel in which you want your words to be transcribed, i.e.
    #test-voice-to-text-output 3. from that channel, run the "/transcribe" slash
    command

For the duration of your connection to that voice channel, spoken words will be
transcribed from Nacl's computer into the chosen chat channel.  Transcription
will end when the requester disconnects from the specified voice chat channel.

If the user of the /transcribe command is not in a voice channel, an appropriate
error should be shown If the user of the /transcribe command is not authorized
to use the command, an appropriate error should be shown (shouldn't even show up
as a command?)
"""

import asyncio
import discord
from discord import app_commands
from discord.ext import commands, voice_recv
import time
import websockets

"""
Discord API variables
Permissions: Send Messages, Connect
permissions_integer=1050624  # probably not needed
"""

MY_GUILD = discord.Object(id=818478021563908116)
MY_USER_ID = 151847709286989824
transcription_ok_roles = {
    'housekeeping': 818490394123698177,
    'housekeeping_emeritus': 1062177151371198504,
    'host': 819233684136788009,
    'transcription_approved': 1274617618296340521
}

#transcription_tasks = {}
#active_voiceclient = None
transcription_channel = None
transcription_user = None
STT_websocket_listen_address = "::1" #ipv6 localhost
STT_websocket_listen_port = 48156

class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents, activity: discord.CustomActivity):
        super().__init__(intents=intents, activity=activity)
        self.tree = app_commands.CommandTree(self)
        
    async def setup_hook(self):
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)

intents = discord.Intents.default()
intents.voice_states = True
client = MyClient(intents=intents, activity=discord.CustomActivity(name="Voice Transcriber Experiment Bot"))

def text_detected(text):
    #do something with text
    pass

@client.event
async def on_ready():
    print(f'Logged in as {client.user} (ID: {client.user.id})')
    print('------')

#Define a slash command
"""
@client.tree.command()
async def testge(interaction: discord.Interaction):
    await interaction.response.send_message(f'hi, {interaction.user.mention}')
"""

@client.tree.command()
async def dumpstate(interaction: discord.Interaction):
    global transcription_tasks
    print(f'Dumping transcription_tasks: {transcription_tasks}')
    await interaction.response.send_message('ok. check log', ephemeral=True)

async def JoinVoiceChannel(channel):
    print(f'Joining voice channel: {channel}')
    pass
    
async def DisconnectVoiceChannel(channel):
    print(f'Disconnecting from channel: {channel}')
    pass

"""
/transcribehere
"""
@client.tree.command()
async def transcribehere(interaction: discord.Interaction):
    """
    Does the following:
        1. picks the designated channel for text output
        2. starts the websocket server for local messaging from the
        transcription process
    """
    global transcription_channel
    if interaction.user.id != MY_USER_ID:
        print(f'someone tried to invoke transcribehere who is not JayDeezus (id: {interaction.user.id})')
        return
    
    
    
    if transcription_channel:
        transcription_channel = None
        await interaction.response.send_message('No longer transcribing here.')
    else:
        transcription_channel = interaction.channel
        await interaction.response.send_message('Transcribing here.')

"""
Define `/transcribeme` command
"""
"""
@client.tree.command()
async def transcribeme(interaction: discord.Interaction):
    #check if interaction.user is a host, housekeeping, or someone marked with the "transcription allowed" role
    if len(set([role.id for role in interaction.user.roles]) & set(transcription_ok_roles.values())) == 0:
        await interaction.response.send_message(f'You are not authorized to use this command.', ephemeral=True)
        return
    
    #check if interaction.user is in a voice channel
    if interaction.user.voice == None:
        await interaction.response.send_message(f'You are not in a voice chat channel.  Connect to a voice chat channel and try this command again.', ephemeral=True)
        return

    global transcription_tasks
    global active_voiceclient
    
    if interaction.user in transcription_tasks:
        #stop listening to user
        await active_voiceclient.disconnect()
        active_voiceclient = None
        del transcription_tasks[interaction.user]
        await interaction.response.send_message(f'No longer transcribing for {interaction.user.mention}.')
    else:
        #limit to 1 user at a time
        if len(transcription_tasks) > 0:
            current_transcription_user = list(transcription_tasks.keys())[0]
            await interaction.response.send_message(f'[WIP] Unable to start transcription service.  Transcription in use by {current_transcription_user.mention}')
        else:
            print(f'starting transcription, user dump: {interaction.user}')
            print(f'VoiceState for user: {interaction.user.voice}')
            transcription_tasks[interaction.user] = interaction.channel_id
            active_voiceclient = await interaction.user.voice.channel.connect(
                cls=voice_recv.VoiceRecvClient, # hook discord-ext-voice-recv here
                self_mute=True
            )
            #discord-ext-voice-recv -specific stuff
            def callback(user, data: voice_recv.VoiceData):
                print(
                    f'I heard something from {user}.\n'
                    f'\tPacket: {data.packet}.\n'
                    f'\tpcm length: {len(data.pcm)}.\n'
                    f'\tsource: {data.source}.\n'
                )
                # do something with data, i.e. hand it off to RealtimeSTT somehow

            active_voiceclient.listen(voice_recv.BasicSink(callback))

            await interaction.response.send_message(f'[WIP] {interaction.user.mention} is now transcribing voice chat to this channel.')
"""

"""
define something that happens when the person who started /transcribeme disconnects from voice chat
"""
@client.event
async def on_voice_state_update(member, before, after):
    if len(transcription_tasks) == 0:
        #print(f'Not transcribing, doing nothing.')
        return

    #print(f'on_voice_state_update called with args:')
    #print(f'Member: {member} ID: {member.id}')
    #print(f'{before}')
    #print(f'{after}')
    global active_voiceclient
    if member in transcription_tasks and before.channel is not None and after.channel is None:
        await active_voiceclient.disconnect()
        transcription_channel = client.get_channel(transcription_tasks[member])
        del transcription_tasks[member]
        await transcription_channel.send(f'No longer transcribing for {member.mention} (Disconnected from voice channel)')
        
"""
define event handler for when voice chat
NOTE: discord.py does not seem to provide actually receiving voice data
"""

"""
signature of client.run:
    
    def run(
        self,
        token: str,
        *,
        reconnect: bool = True,
        log_handler: Optional[logging.Handler] = MISSING,
        log_formatter: logging.Formatter = MISSING,
        log_level: int = MISSING,
        root_logger: bool = False,
    ) -> None:
"""

async def transcription_message_handler(websocket):
    print(f'local connection to transcriber open')
    async for message in websocket:
        print(f'\"{message}\" >> {transcription_channel or 'NO CHANNEL'}')
        if transcription_channel:
            await transcription_channel.send(message)
    print(f'local connection to transcriber closed')
    await transcription_channel.send("No longer transcribing here.")

async def transcription_message_websocket():
    """
    loop to receive data from the websocket server doing the listening from my
    mic.
    
    Or wherever.
    """
    #initialize websocket listener
    async with websockets.serve(
        transcription_message_handler, 
        STT_websocket_listen_address,
        STT_websocket_listen_port,
        ping_interval=None
    ):
        await asyncio.get_running_loop().create_future() #run forever

async def main(token, client):
    async with client:
        """
        This just starts and blocks.  I need to figure out how to run an event
        loop that weaves in both the discord.py stuff and the second websocket
        that is listening for text from a local process.
        """
        await asyncio.gather(client.start(token), transcription_message_websocket())

with open('blipblap', 'r') as file:
    token = file.read()
    """
    TODO need to turn client.run(data) and break it out so I can insert an async
    task that will check RealtimeSTT for input
    - replace client.run with whatever it invokes up until asyncio.run is
        encountered
    """
    #client.run(data) #blocks
    try:
        asyncio.run(main(token, client))
    except KeyboardInterrupt:
        pass
    
    
#cleanup
#recorder.stop()
