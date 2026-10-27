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
            for index, (start, end, text) in enumerate([(1,1.95,'我的号码是123'),(3,3.95,'4'),(5,5.95,'不是123，是124'),(8,8.95,'89')]):
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
        return VADState.SPEAKING if 1<=seconds<=2 or 3<=seconds<=4 or 5<=seconds<=6 or 8<=seconds<=9 else VADState.QUIET

class ReviewLLM(base.LocalLLM):
    """Inject fixed tool choices, retaining actual SDK dispatch and state validation."""
    async def _process_context(self,context):
        version=self.response_scope.provenance(context)
        if version is None:
            raise RuntimeError('Missing response provenance')
        import json
        correction='不是' in version.text
        name='clear_identifier' if correction else 'submit_identifier'
        arguments={} if correction else {'identifier':'123'}
        invoked=getattr(self,'review_invoked',set())
        self.review_invoked=invoked
        if version.response_id not in invoked:
            invoked.add(version.response_id)
            await self.run_function_calls([base.FunctionCallFromLLM(function_name=name,tool_call_id=version.response_id,arguments=arguments,context=context)])
            return
        results=[m for m in context.get_messages() if m.get('role')=='tool']
        actual=json.loads(results[-1]['content'])
        if correction:
            assert actual['status']=='cleared' and actual['value']==''
            reply='编号已清空，请完整重念。'
        else:
            assert actual['status']=='submitted' and actual['value']=='123'
            reply='已记录编号123，请继续。'
        await self.push_frame(LLMTextFrame(reply))

base.IdentifierASR=ReviewASR
base.LocalVAD=ReviewVAD
base.LocalLLM=ReviewLLM
app=base.create_local_app(Path('/tmp/voiceagent-gate2-mixed-20261026'),'http://127.0.0.1:18998','identifier')
async def synthesize(unit,config,rate,*,timeout,api_key):
    """Hold the pure segment in playback until the correction arrives."""
    return b'\x00\x08' * (rate * 10)
app.state.echo_synthesize=synthesize
uvicorn.run(app,host='127.0.0.1',port=18998)
