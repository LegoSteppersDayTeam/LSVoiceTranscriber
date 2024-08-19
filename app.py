# I dedicate this code to the public domain.
# dependent packages: discord.py, RealtimeSTT

"""
This bot is meant to provide live voice transcription on request by specific people on the Lego Steppers discord.

Usage:
    1. Join a voice channel
    2. switch to a channel in which you want your words to be transcribed, i.e. #test-voice-to-text-output
    3. from that channel, run the "/transcribe" slash command

For the duration of your connection to that voice channel, spoken words will be transcribed from Nacl's computer into the chosen chat channel.  Transcription will end when the requester disconnects from the specified voice chat channel.

If the user of the /transcribe command is not in a voice channel, an appropriate error should be shown
If the user of the /transcribe command is not authorized to use the command, an appropriate error should be shown (shouldn't even show up as a command?)


"""

import asyncio
import discord
from discord import app_commands
from discord.ext import commands, voice_recv
import time
from RealtimeSTT import AudioToTextRecorder

"""
Discord API variables
Permissions: Send Messages, Connect
permissions_integer=1050624  # probably not needed
"""

MY_GUILD = discord.Object(id=818478021563908116)
transcription_ok_roles = {
    'housekeeping': 818490394123698177,
    'housekeeping_emeritus': 1062177151371198504,
    'host': 819233684136788009,
    'transcription_approved': 1274617618296340521
}

transcription_tasks = {}
active_voiceclient = None

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

# configure this to be fed audio data from discord.py.  I'm handing voice data to RSTT for transcription, it's not recording sound from my mic on its own.
recorder_config = {
        'spinner': False,
        'model': 'large-v2',
        'silero_sensitivity': 0.4,
        'webrtc_sensitivity': 2,
        'post_speech_silence_duration': 0.4,
        'min_length_of_recording': 0,
        'min_gap_between_recordings': 0,
        'enable_realtime_transcription': True,
        'realtime_processing_pause': 0.2,
        'realtime_model_type': 'tiny',
        'on_realtime_transcription_update': text_detected,
        'silero_deactivity_detection': True,
        'use_microphone': False,
}
recorder = AudioToTextRecorder(**recorder_config)

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
Define `/transcribeme` command
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



with open('blipblap', 'r') as file:
    data = file.read()
    client.run(data) #blocks
    
#cleanup
#recorder.stop()
