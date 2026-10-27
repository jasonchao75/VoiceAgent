/* Playback evidence is emitted by the render thread, never by receipt of a server message. */
class TaskStreamProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = [];
    this.tasks = new Map();
    this.pendingStops = [];
    this.pendingEnds = new Set();
    this.pendingInterrupt = null;
    this.clockSamples = [];
    this.lastRendered = null;
    this.queuedSamples = 0;
    this.limit = (typeof sampleRate === "number" ? sampleRate : 24000) * 30;
    this.port.onmessage = ({data}) => this.message(data);
  }

  task(id) {
    if (typeof id !== "string" || !id || id.length > 128) return null;
    if (!this.tasks.has(id)) this.tasks.set(id, {id, rendered:0, queued:0, started:false, ended:false, closed:false, lastFrame:null});
    return this.tasks.get(id);
  }

  timing(frame = typeof currentFrame === "number" ? currentFrame : null) {
    if (!Number.isSafeInteger(frame) || typeof sampleRate !== "number") return {};
    return {render_frame:frame, render_sample_rate:sampleRate};
  }

  stop(task) {
    this.queue = this.queue.filter(chunk=>chunk.task !== task);
    this.queuedSamples -= task.queued;
    task.queued = 0;
    task.closed = true;
    this.pendingEnds.delete(task);
  }

  message(data) {
    if (!data || typeof data !== "object") return;
    if (data.event === "clock_sample") {
      if(typeof data.sample_id==='string' && /^[a-f0-9]{32}$/.test(data.sample_id)
        && this.clockSamples.length<8) this.clockSamples.push(data.sample_id);
    } else if (data.event === "write") {
      const task = this.task(data.trackId || "default");
      if (!task || task.closed || !(data.buffer instanceof Int16Array) || !data.buffer.length) return;
      if (this.queuedSamples + data.buffer.length > this.limit) {
        this.stop(task);
        this.port.postMessage({event:"task_failed",playback_id:task.id,reason:"render_queue_limit",rendered_samples:task.rendered});
        return;
      }
      task.queued += data.buffer.length;
      this.queuedSamples += data.buffer.length;
      this.queue.push({task, buffer:data.buffer, offset:0});
    } else if (data.event === "task_end") {
      const task = this.task(data.playback_id);
      if (task && !task.closed) { task.ended = true; this.pendingEnds.add(task); }
    } else if (data.event === "stop_task") {
      const task = this.task(data.playback_id);
      if (!task) return;
      this.stop(task);
      this.pendingStops.push({task,requestId:data.requestId});
    } else if (data.event === "interrupt") {
      for (const task of this.tasks.values()) if (!task.closed) {
        this.stop(task);
        this.pendingStops.push({task,requestId:data.requestId});
      }
      this.pendingInterrupt = data.requestId;
    } else if (data.event === "offset") {
      const task = this.tasks.get(this.lastRendered);
      this.port.postMessage({event:"offset",requestId:data.requestId,trackId:task?.id || null,offset:task?.rendered || 0});
    }
  }

  process(inputs, outputs) {
    const output = outputs[0]?.[0];
    if (!output) return true;
    for(const sample_id of this.clockSamples.splice(0)) {
      this.port.postMessage({event:'clock_sample',sample_id,...this.timing()});
    }
    output.fill(0);
    let cursor = 0;
    while (cursor < output.length && this.queue.length) {
      const chunk = this.queue[0], task = chunk.task;
      if (task.closed) { this.queue.shift(); continue; }
      const size = Math.min(output.length-cursor,chunk.buffer.length-chunk.offset);
      for (let i=0;i<size;i++) output[cursor+i] = chunk.buffer[chunk.offset+i] / 32768;
      chunk.offset += size; cursor += size;
      task.rendered += size; task.queued -= size; this.queuedSamples -= size;
      this.lastRendered = task.id;
      task.lastFrame = typeof currentFrame === "number" ? currentFrame + cursor : null;
      if (!task.started && size) {
        task.started = true;
        this.port.postMessage({event:"task_started",playback_id:task.id,rendered_samples:task.rendered,...this.timing(task.lastFrame === null ? null : task.lastFrame-size)});
      }
      if (chunk.offset === chunk.buffer.length) this.queue.shift();
    }
    for (const task of this.pendingEnds) {
      if (task.ended && !task.closed && task.queued === 0) {
        task.closed = true;
        this.pendingEnds.delete(task);
        this.port.postMessage({event:"task_finished",playback_id:task.id,rendered_samples:task.rendered,started:task.started,...this.timing(task.lastFrame ?? undefined)});
      }
    }
    for (const {task,requestId} of this.pendingStops) {
      this.port.postMessage({event:"task_stopped",playback_id:task.id,request_id:requestId,rendered_samples:task.rendered,started:task.started,...this.timing()});
    }
    this.pendingStops = [];
    if (this.pendingInterrupt !== null) {
      const task = this.tasks.get(this.lastRendered);
      this.port.postMessage({event:"offset",requestId:this.pendingInterrupt,trackId:task?.id || null,offset:task?.rendered || 0});
      this.port.postMessage({event:"stop"});
      return false;
    }
    return true;
  }
}
registerProcessor("stream_processor",TaskStreamProcessor);
