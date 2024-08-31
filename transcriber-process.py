# I dedicate this code to the public domain.
# dependent packages: discord.py, RealtimeSTT

"""
temporary dev stuff
"""
# import importlib.util
# import sys
# spec = importlib.util.spec_from_file_location("RealtimeSTT",
# "D:\\projects\\RealtimeSTTWithAsync\\RealtimeSTT\\__init__.py") RealtimeSTT =
# importlib.util.module_from_spec(spec) sys.modules["RealtimeSTT"] = RealtimeSTT
# spec.loader.exec_module(RealtimeSTT)
# print(f'using RealtimeSTT from {RealtimeSTT.__file__}')
from RealtimeSTT import AudioToTextRecorder

"""
Transcriber process for my bot, meant to take voice input from my mic and send
the transcribed text via websocket to the discord bot which will relay the text
to a targetted discord channel.
"""
import logging
import websockets

import asyncio

# stuff for modified _recording_worker method
import queue #for queue.Empty error
import time

#logging.basicConfig(level=logging.DEBUG)

"""
class wrapper to overload _recording_worker

- _recording_worker - updated to prevent blocking during shutdown on Windows
machines

"""
class MyATTR(AudioToTextRecorder):
    def _recording_worker(self):
        """
        The main worker method which constantly monitors the audio
        input for voice activity and accordingly starts/stops the recording.
        
        NOTE: This method blocks
        """

        logging.debug('Starting recording worker')

        try:
            was_recording = False
            delay_was_passed = False

            # Continuously monitor audio for voice activity
            while self.is_running:
                try:
                    """
                    added arguments (True, 1) to self.audio_queue.get() calls to
                    allow periodically continuing the loop even when no data is
                    in the queue so self.is_running can be checked on systems
                    where .get() is a uninterruptible blocking call (Windows).
                    -JayDeezus
                    """
                    data = self.audio_queue.get(True, 1)

                    if self.on_recorded_chunk:
                        self.on_recorded_chunk(data)

                    if self.handle_buffer_overflow:
                        # Handle queue overflow
                        if (self.audio_queue.qsize() >
                                self.allowed_latency_limit):
                            logging.warning("Audio queue size exceeds "
                                            "latency limit. Current size: "
                                            f"{self.audio_queue.qsize()}. "
                                            "Discarding old audio chunks."
                                            )

                        while (self.audio_queue.qsize() >
                                self.allowed_latency_limit):

                            data = self.audio_queue.get(True, 1)

                except queue.Empty:
                    """
                    added to handle exception raised when self.audio_queue.get
                    blocks for 1 second without getting any data so that loop
                    can restart and check self.is_running during shutdown on
                    Windows. -JayDeezus
                    """
                    continue

                except BrokenPipeError:
                    print("BrokenPipeError _recording_worker")
                    self.is_running = False
                    break

                if not self.is_recording:
                    # Handle not recording state
                    time_since_listen_start = (time.time() - self.listen_start
                                               if self.listen_start else 0)

                    wake_word_activation_delay_passed = (
                        time_since_listen_start >
                        self.wake_word_activation_delay
                    )

                    # Handle wake-word timeout callback
                    if wake_word_activation_delay_passed \
                            and not delay_was_passed:

                        if self.use_wake_words and self.wake_word_activation_delay:
                            if self.on_wakeword_timeout:
                                self.on_wakeword_timeout()
                    delay_was_passed = wake_word_activation_delay_passed

                    # Set state and spinner text
                    if not self.recording_stop_time:
                        if self.use_wake_words \
                                and wake_word_activation_delay_passed \
                                and not self.wakeword_detected:
                            self._set_state("wakeword")
                        else:
                            if self.listen_start:
                                self._set_state("listening")
                            else:
                                self._set_state("inactive")

                    #self.wake_word_detect_time = time.time()
                    if self.use_wake_words and wake_word_activation_delay_passed:
                        try:
                            wakeword_index = self._process_wakeword(data)

                        except struct.error:
                            logging.error("Error unpacking audio data "
                                          "for wake word processing.")
                            continue

                        except Exception as e:
                            logging.error(f"Wake word processing error: {e}")
                            continue

                        # If a wake word is detected                        
                        if wakeword_index >= 0:

                            # Removing the wake word from the recording
                            samples_time = int(self.sample_rate * self.wake_word_buffer_duration)
                            start_index = max(
                                0,
                                len(self.audio_buffer) - samples_time
                                )
                            temp_samples = collections.deque(
                                itertools.islice(
                                    self.audio_buffer,
                                    start_index,
                                    None)
                                )
                            self.audio_buffer.clear()
                            self.audio_buffer.extend(temp_samples)

                            self.wake_word_detect_time = time.time()
                            self.wakeword_detected = True
                            #self.wake_word_cooldown_time = time.time()
                            if self.on_wakeword_detected:
                                self.on_wakeword_detected()

                    # Check for voice activity to
                    # trigger the start of recording
                    if ((not self.use_wake_words
                         or not wake_word_activation_delay_passed)
                            and self.start_recording_on_voice_activity) \
                            or self.wakeword_detected:

                        if self._is_voice_active():
                            logging.info("voice activity detected")

                            self.start()

                            if self.is_recording:
                                self.start_recording_on_voice_activity = False

                                # Add the buffered audio
                                # to the recording frames
                                self.frames.extend(list(self.audio_buffer))
                                self.audio_buffer.clear()

                            self.silero_vad_model.reset_states()
                        else:
                            data_copy = data[:]
                            self._check_voice_activity(data_copy)

                    self.speech_end_silence_start = 0

                else:
                    # If we are currently recording

                    # Stop the recording if silence is detected after speech
                    if self.stop_recording_on_voice_deactivity:
                        is_speech = (
                            self._is_silero_speech(data) if self.silero_deactivity_detection
                            else self._is_webrtc_speech(data, True)
                        )

                        if not is_speech:
                            # Voice deactivity was detected, so we start
                            # measuring silence time before stopping recording
                            if self.speech_end_silence_start == 0:
                                self.speech_end_silence_start = time.time()
                        else:
                            self.speech_end_silence_start = 0

                        # Wait for silence to stop recording after speech
                        if self.speech_end_silence_start and time.time() - \
                                self.speech_end_silence_start > \
                                self.post_speech_silence_duration:
                            logging.info("voice deactivity detected")
                            self.stop()

                if not self.is_recording and was_recording:
                    # Reset after stopping recording to ensure clean state
                    self.stop_recording_on_voice_deactivity = False

                if time.time() - self.silero_check_time > 0.1:
                    self.silero_check_time = 0

                # Handle wake word timeout (waited to long initiating
                # speech after wake word detection)
                if self.wake_word_detect_time and time.time() - \
                        self.wake_word_detect_time > self.wake_word_timeout:

                    self.wake_word_detect_time = 0
                    if self.wakeword_detected and self.on_wakeword_timeout:
                        self.on_wakeword_timeout()
                    self.wakeword_detected = False

                was_recording = self.is_recording

                if self.is_recording:
                    self.frames.append(data)

                if not self.is_recording or self.speech_end_silence_start:
                    self.audio_buffer.append(data)


        except Exception as e:
            if not self.interrupt_stop_event.is_set():
                logging.error(f"Unhandled exeption in _recording_worker: {e}")
                raise

async def RunWSClient(message_queue):
    # connect to ::1:48156
    async with websockets.connect("ws://[::1]:48156", ping_interval=None) as websocket:
    
        async def SendMessage(message):
            print(f'Sending message...')
            """
            TODO replace with code to actually send the message via connected
            websocket
            """
            await websocket.send(message)
            print(f'message sent: {message}')

        while True:
            try:
                message = await message_queue.get()
                await SendMessage(message)
                message_queue.task_done()
            except asyncio.CancelledError:
                print("task cancelled, shutting down websocket client")
                break

async def RunSTT(message_queue):
    with MyATTR(spinner=False, model="tiny.en", language="en") as recorder:
        print("Say something...")
        transcribed_text = None

        def handler(text):
            transcribed_text = text

        while True:
            #recorder.text(handler) # BLOCKS
            transcribed_text = recorder.text()
            if transcribed_text == "":
                continue
            print(f'sending: {transcribed_text}')
            await message_queue.put(transcribed_text)
            transcribed_text=""
            await message_queue.join()
            
async def amain():
    message_queue = asyncio.Queue()
    await asyncio.gather(RunWSClient(message_queue), RunSTT(message_queue))

if __name__ == '__main__':
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        print("KeyboardInterrupt detected, shutting down.")
    