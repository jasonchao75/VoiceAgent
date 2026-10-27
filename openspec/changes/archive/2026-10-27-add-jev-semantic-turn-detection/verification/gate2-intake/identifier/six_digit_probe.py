"""Independent six-digit acceptance probe; production coordinator, no network."""
import asyncio
import json
from pathlib import Path
from pipecat.frames.frames import TranscriptionFrame, TTSSpeakFrame
from src.asr.td_config import IdentifierRuleSettings
from src.pipeline.identifier import IdentifierCollection, IdentifierVocabulary
from src.pipeline.identifier_rules import IdentifierRules
from tests.test_td_runtime import coordinator, interim
from tests.test_td_rule_settings import priority_settings

async def main():
    report = {}
    def make():
        config = priority_settings()
        config['collection']['target_length'] = 6
        config['vocabulary'] = [{'value': str(i), 'aliases': [str(i)]} for i in range(10)]
        state = IdentifierCollection(IdentifierVocabulary({str(i): [str(i)] for i in range(10)}), target_length=6)
        frames, events = [], []
        td = coordinator(identifier_rules=IdentifierRules(IdentifierRuleSettings.model_validate(config), state), evidence_sink=events.append)
        async def push(frame, *args, **kwargs):
            frames.append(frame)
        td.push_frame = push
        td.assistant_context('请提供编号')
        return td, state, frames, events
    async def say(td, text, index, start, end):
        await td.speech_started()
        frame = interim(text)
        frame.result.update(event='EndOfTurn', turn_index=index, audio_window_start=start/1000, audio_window_end=end/1000, words=[{'word':text,'start':start/1000,'end':end/1000}])
        await td.receive_transcript(frame)
        await td.speech_stopped(end)
    td, state, frames, events = make()
    await say(td, '123', 0, 0, 3000)
    await td.advance(3350)
    assert state.value == '123'
    await say(td, '45', 1, 4000, 6000)
    await td.advance(6350)
    assert state.value == '12345'
    await td.advance(13999)
    assert not any(isinstance(f, TTSSpeakFrame) for f in frames)
    await td.advance(14000)
    assert len([f for f in frames if isinstance(f, TTSSpeakFrame)]) == 1
    await td.advance(22000)
    assert len([f for f in frames if isinstance(f, TTSSpeakFrame)]) == 1
    assert state.value == '12345'
    report['accumulation_and_incomplete'] = {'values':['123','12345'],'before_8000ms':0,'at_8000ms':1,'continued_silence_total':1}
    td.assistant_context('请继续念完整编号')
    await say(td, '6', 2, 23000, 24000)
    await td.advance(26500)
    commits = [f for f in frames if isinstance(f, TranscriptionFrame)]
    assert state.value == '123456' and len(commits) == 1
    await td.advance(40000)
    assert len([f for f in frames if isinstance(f, TTSSpeakFrame)]) == 1
    report['complete'] = {'value':state.value,'submissions':len(commits),'new_incomplete_reminders':0,'events':events}
    td, state, frames, events = make()
    await say(td, '1234567', 0, 0, 7000)
    await td.advance(7349)
    assert not any(isinstance(f, TTSSpeakFrame) for f in frames)
    await td.advance(7350)
    reminders = [f for f in frames if isinstance(f, TTSSpeakFrame)]
    assert len(reminders) == 1 and reminders[0].metadata['td_output_kind'] == 'overflow'
    await td.advance(20000)
    assert state.value == '1234567'
    assert len([f for f in frames if isinstance(f, TTSSpeakFrame)]) == 1
    assert not any(isinstance(f, TranscriptionFrame) for f in frames)
    report['overflow'] = {'value':state.value,'before_350ms':0,'at_350ms':1,'submissions':0,'events':events}
    source = state.bind_source(0, 'clear-request', 1, '清空编号')
    result = state.clear_tool(source)
    assert result['status'] == 'cleared' and state.value == ''
    td.assistant_context('请重新提供编号')
    await say(td, '89', 1, 21000, 23000)
    await td.advance(23350)
    assert state.value == '89'
    report['clear_and_resume'] = {'clear_status':result['status'],'new_value':state.value,'generation':state.generation}
    path = Path('openspec/changes/add-jev-semantic-turn-detection/verification/gate2-intake/identifier/six-digit-results.json')
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    import logging
    logging.warning('PASS: six-digit accumulation, timeout boundary/dedup, full, overflow, clear/resume')

asyncio.run(main())
