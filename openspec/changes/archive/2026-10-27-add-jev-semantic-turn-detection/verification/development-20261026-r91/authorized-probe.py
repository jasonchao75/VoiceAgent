"""Execute only the pinned D-081 case through the existing bounded probe."""
import json
import sys
from pathlib import Path
root=Path('/Volumes/work/OpenCode/VoiceAgent')
sys.path.insert(0,str(root))
from scripts.evaluation import probe_td_compatibility as probe
plan_path=probe.CHANGE/'verification/deepgram-negation-continuation-r91-plan.json'
plan=json.loads(plan_path.read_text())
probe.build_plan=lambda **kwargs: plan
original=probe.verify_authorization
def claim(plan,decision):
    original(plan,decision)
    path=probe.CHANGE/'verification/delivery-status.json'
    data=json.loads(path.read_text())
    grant=next(x for x in data['external_calls'] if x['batch_id']==plan['batch_id'])
    grant['execution_status']='started_no_replay'
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
probe.verify_authorization=claim
raise SystemExit(probe.main(['--execute','--authorization-decision','D-081']))
