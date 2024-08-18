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
from RealtimeSTT import AudioToTextRecorder

"""
Discord API variables
Permissions: Send Messages, Connect
permissions_integer=1050624
"""
client = discord.Client(intents=intents, activity=discord.CustomActivity(name=time.strftime("Started %d %b %y %H%M %z")))

"""
# configure this to be fed audio data from discord.py.  I'm handing voice data to RSTT for transcription, it's not recording sound from my mic on its own.
recorder_config = {
        'spinner': False,
        'model': 'large-v2',
        'silero_sensitivity': 0.4,
        'webrtc_sensitivity': 2,
        'post_speech_silence_duration': 0.4,            # probably not needed
        'min_length_of_recording': 0,                   # probably not needed? maybe?
        'min_gap_between_recordings': 0,
        'enable_realtime_transcription': True,          # probably not needed? Start simple with just non-realtime transcription
        'realtime_processing_pause': 0.2,                   # probably not needed
        'realtime_model_type': 'tiny',                      # probably not needed
        'on_realtime_transcription_update': text_detected,  # probably not needed
        'silero_deactivity_detection': True,                # probably not needed
}
recorder = AudioToTextRecorder(**recorder_config)
"""

@client.event
async def on_ready():
    pass

with open('blipblap', 'r') as file:
    data = file.read()
    client.run(data)