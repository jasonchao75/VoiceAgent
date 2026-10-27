import {test, expect} from '@playwright/test';
import {mkdirSync,writeFileSync} from 'node:fs';
const evidence = process.env.VOICE_AGENT_TD_RTC_PROBE_EVIDENCE || process.env.VOICE_AGENT_TD_UI_EVIDENCE || '../test-results/td-rtc-probe-evidence';
mkdirSync(evidence,{recursive:true});

test.use({permissions:['microphone'], launchOptions:{args:['--autoplay-policy=no-user-gesture-required', '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream']}});

test('inspect RTP and decoded-audio API boundaries without providers or a call', async ({page}, info) => {
  // A loopback secure origin is fulfilled entirely in-process; no application or vendor is called.
  await page.route('**/*', route => route.fulfill({contentType:'text/html', body:'<!doctype html><title>API probe</title>'}));
  await page.goto('http://127.0.0.1:8765/rtc-api-probe');
  const result = await page.evaluate(async () => {
    const result = {
      secureContext:isSecureContext,
      userAgent:navigator.userAgent,
      encodedTransform:typeof RTCRtpScriptTransform,
      receiverTransform:'transform' in RTCRtpReceiver.prototype,
      decodedAudioProcessor:typeof MediaStreamTrackProcessor,
      audioDataProperties:typeof AudioData === 'undefined' ? [] : Object.getOwnPropertyNames(AudioData.prototype),
    };
    if (typeof MediaStreamTrackProcessor === 'undefined') return result;
    const context = new AudioContext();
    const source = context.createOscillator();
    const destination = context.createMediaStreamDestination();
    source.connect(destination);
    // Keep the Web Audio graph pulling even if the track consumer is unsupported.
    const silentPull = context.createGain();
    silentPull.gain.value = 0;
    source.connect(silentPull); silentPull.connect(context.destination);
    source.start();
    const track = destination.stream.getAudioTracks()[0];
    let reader, timeout;
    try {
      const processor = new MediaStreamTrackProcessor({track});
      reader = processor.readable.getReader();
      await context.resume();
      result.contextState = context.state;
      result.track = {kind:track.kind, readyState:track.readyState, enabled:track.enabled};
      const item = await Promise.race([
        reader.read(),
        new Promise((_, reject) => {timeout = setTimeout(() => reject(new Error('Audio read timeout')), 1500);}),
      ]);
      const frame = item.value;
      result.audioRead = {done:item.done, type:frame?.constructor.name,
        timestamp:frame?.timestamp, frames:frame?.numberOfFrames, sampleRate:frame?.sampleRate,
        rtpTimestamp:frame?.rtpTimestamp ?? null};
      frame?.close();
    } catch (error) {
      result.audioReadError = {name:error.name, message:error.message, audioClockSeconds:context.currentTime};
    } finally {
      clearTimeout(timeout);
      await reader?.cancel().catch(()=>{});
      reader?.releaseLock();
      track.stop(); source.stop(); await context.close();
    }
    return result;
  });
  expect(result.secureContext).toBe(true);
  expect(result.audioRead || result.audioReadError || result.decodedAudioProcessor === 'undefined').toBeTruthy();
  writeFileSync(`${evidence}/capabilities.${info.project.name}.json`, JSON.stringify(result, null, 2));
});

test('RTP reception precedes decoder and active playback progress', async ({page}, info) => {
  test.skip(process.env.VOICE_AGENT_TD_RTC_PAIR_PROBE !== '1', 'Optional local RTC decoder/player diagnostic; enable its bounded fake-device test explicitly.');
  await page.route('**/*', route => route.fulfill({contentType:'text/html', body:'<!doctype html><title>RTP probe</title>'}));
  await page.goto('http://127.0.0.1:8765/rtc-api-probe');
  const result = await page.evaluate(async () => {
    const fakeCapture = await navigator.mediaDevices.getUserMedia({audio:true});
    const sending = new RTCPeerConnection({iceServers:[]});
    const receiving = new RTCPeerConnection({iceServers:[]});
    const context = new AudioContext();
    const source = context.createOscillator(), stream = context.createMediaStreamDestination();
    const silent = context.createGain(); silent.gain.value = 0;
    source.connect(stream); source.connect(silent); silent.connect(context.destination);
    source.start(); await context.resume();
    const track = stream.stream.getAudioTracks()[0];
    sending.addTrack(track, stream.stream);
    let receiver, reader, consuming, decodedFrames = 0, player;
    const decodedTiming = [];
    receiving.ontrack = event => {
      receiver = event.receiver;
      // Consume decoded frames without routing them to an element, context or speaker.
      reader = new MediaStreamTrackProcessor({track:event.track}).readable.getReader();
      consuming = (async () => {
        while (true) {
          const frame = await reader.read();
          if (frame.done) break;
          decodedFrames++;
          decodedTiming.push({timestamp:frame.value.timestamp, frames:frame.value.numberOfFrames,
            sampleRate:frame.value.sampleRate, observedAt:performance.now()});
          if (decodedTiming.length > 12) decodedTiming.shift();
          frame.value.close();
        }
      })();
    };
    async function gathered(pc) {
      if (pc.iceGatheringState === 'complete') return;
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('Local ICE timeout')), 4000);
        pc.onicegatheringstatechange = () => {
          if (pc.iceGatheringState === 'complete') {clearTimeout(timer); resolve();}
        };
      });
    }
    try {
      await sending.setLocalDescription(await sending.createOffer());
      await gathered(sending);
      await receiving.setRemoteDescription(sending.localDescription);
      await receiving.setLocalDescription(await receiving.createAnswer());
      await gathered(receiving);
      await sending.setRemoteDescription(receiving.localDescription);
      const observations = [];
      const deadline = performance.now() + 5000;
      while (performance.now() < deadline) {
        for (const source of receiver?.getSynchronizationSources() || []) {
          if (observations.at(-1)?.rtpTimestamp !== source.rtpTimestamp) {
            observations.push({timestamp:source.timestamp, rtpTimestamp:source.rtpTimestamp});
          }
        }
        if (observations.length >= 5) break;
        await new Promise(resolve => setTimeout(resolve, 20));
      }
      const stats = [...(await receiving.getStats()).values()].filter(s => s.type === 'inbound-rtp' && s.kind === 'audio');
      const beforePlayback = {decodedFrames, synchronizationObservations:observations.length,
        inbound:stats.map(s=>({packetsReceived:s.packetsReceived, jitterBufferEmittedCount:s.jitterBufferEmittedCount}))};
      player = document.createElement('audio'); player.muted = true;
      player.srcObject = new MediaStream([receiver.track]); document.body.append(player);
      await player.play();
      const playbackDeadline = performance.now() + 3000;
      while (performance.now() < playbackDeadline && observations.length < 5) {
        for (const source of receiver.getSynchronizationSources()) {
          if (observations.at(-1)?.rtpTimestamp !== source.rtpTimestamp) {
            observations.push({timestamp:source.timestamp, rtpTimestamp:source.rtpTimestamp});
          }
        }
        await new Promise(resolve=>setTimeout(resolve,20));
      }
      return {connection:sending.connectionState, ice:sending.iceConnectionState, decodedFrames,
        decodedTiming, browserTimeOrigin:performance.timeOrigin,
        beforePlayback, player:{paused:player.paused, muted:player.muted},
        mdnsCandidates:sending.localDescription.sdp.includes('.local'),
        candidateCounts:{sender:(sending.localDescription.sdp.match(/a=candidate:/g)||[]).length,
          receiver:(receiving.localDescription.sdp.match(/a=candidate:/g)||[]).length},
        receiverIce:receiving.iceConnectionState, dtls:receiver?.transport?.state, observations,
        remoteSinkCreated:true, htmlAudioElements:document.querySelectorAll('audio').length,
        remoteTrackState:receiver?.track.readyState};
    } finally {
      if (player) {player.pause(); player.srcObject = null; player.remove();}
      await reader?.cancel().catch(()=>{});
      await consuming?.catch(()=>{}); reader?.releaseLock();
      sending.close(); receiving.close(); track.stop(); source.stop();
      fakeCapture.getTracks().forEach(track => track.stop());
      await context.close();
    }
  });
  writeFileSync(`${evidence}/no-sink-rtp.${info.project.name}.json`,JSON.stringify(result,null,2));
  expect(result.observations.length).toBeGreaterThanOrEqual(2);
  expect(result.beforePlayback.inbound[0].packetsReceived).toBeGreaterThan(0);
  expect(result.htmlAudioElements).toBe(1);
  expect(result.player.paused).toBe(false);
});
