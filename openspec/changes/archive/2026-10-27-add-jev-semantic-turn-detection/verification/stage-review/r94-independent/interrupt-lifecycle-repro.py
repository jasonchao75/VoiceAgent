import asyncio
from tests.test_flux_interrupt_boundary import setup_service
async def main():
 service, _, old, _ = setup_service()
 gates=[asyncio.Event(),asyncio.Event()];starts=[asyncio.Event(),asyncio.Event()];count=0
 async def send(message):
  nonlocal count
  i=count;count+=1;starts[i].set();await gates[i].wait()
 service._transport_send_json=send
 await service.on_audio_context_interrupted(old);first=service._interrupt_sender
 await starts[0].wait()
 await service._handle_message({'type':'SpeechInterrupted'})
 await service.on_audio_context_interrupted('second-abandoned-context');second=service._interrupt_sender
 await starts[1].wait()
 await service._cancel_interrupt_sender()
 print({'distinct_sender_tasks':first is not second,'first_survived_join':not first.done(),'second_done':second.done()})
 first.cancel();await asyncio.gather(first,return_exceptions=True)
asyncio.run(main())
