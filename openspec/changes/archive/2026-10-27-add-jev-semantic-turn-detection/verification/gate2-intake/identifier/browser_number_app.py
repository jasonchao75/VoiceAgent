"""Offline browser review fixture using production routes and playback."""
from pathlib import Path
import uvicorn
from tests.ui import td_local_app as base
from pipecat.frames.frames import InputAudioRawFrame, InterimTranscriptionFrame, LLMTextFrame
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.audio.vad.vad_analyzer import VADState

class ReviewASR(base.IdentifierASR):
    """Emit two proven segments; leave sustained silence for reminder dedup."""
    async def process_frame(self, frame, direction):
        await FrameProcessor.process_frame(self, frame, direction)
        if isinstance(frame, InputAudioRawFrame):
            self.audio_ms += len(frame.audio) / (frame.sample_rate * 2) * 1000
            for index, (start, end, text) in enumerate([(1,1.95,'one'),(3,3.95,'two three')]):
                if self.audio_ms < end * 1000 or index in self.sent:
                    continue
                self.sent.add(index)
                source = InterimTranscriptionFrame(text,'','',result={'event':'EndOfTurn','turn_index':index,'transcript':text,'audio_window_start':start,'audio_window_end':end,'words':[{'word':text,'start':start,'end':end}]})
                source.metadata['td_source_only'] = True
                await self.push_frame(source,direction)
        await self.push_frame(frame,direction)

class ReviewVAD(base.LocalVAD):
    """Produce deterministic source-aligned speaking windows."""
    async def analyze_audio(self,audio):
        self.samples += len(audio)//2
        seconds=self.samples/16000
        return VADState.SPEAKING if 1<=seconds<=2 or 3<=seconds<=4 else VADState.QUIET

class ReviewLLM(base.LocalLLM):
    """Return a fixed normal answer without an external inference call."""
    async def _process_context(self,context):
        if self.response_scope.provenance(context) is None:
            raise RuntimeError('Missing production response provenance')
        await self.push_frame(LLMTextFrame('The identifier has been received.'))

base.IdentifierASR=ReviewASR
base.LocalVAD=ReviewVAD
base.LocalLLM=ReviewLLM
app=base.create_local_app(Path('/tmp/voiceagent-gate2-number-playback-20261026'),'http://127.0.0.1:18998','identifier')
uvicorn.run(app,host='127.0.0.1',port=18998)
