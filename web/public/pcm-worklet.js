class AingelPCM extends AudioWorkletProcessor {
  constructor() {
    super();
    this.pending = [];
    this.stopped = false;
    this.port.onmessage = (e) => {
      if (e.data === "flush") {
        this.flush();
        this.stopped = true;
        this.port.postMessage("flushed");
      }
    };
  }
  flush() {
    if (!this.pending.length) return;
    const pcm = new Int16Array(this.pending.length);
    for (let i = 0; i < pcm.length; i++) {
      const sample = Math.max(-1, Math.min(1, this.pending[i]));
      pcm[i] = sample < 0 ? sample * 32768 : sample * 32767;
    }
    this.pending = [];
    this.port.postMessage(pcm.buffer, [pcm.buffer]);
  }
  process(inputs) {
    if (this.stopped) return false;
    const samples = inputs[0]?.[0];
    if (samples) {
      for (const sample of samples) this.pending.push(sample);
      if (this.pending.length >= 1920) this.flush();
    }
    return true;
  }
}
registerProcessor("aingel-pcm", AingelPCM);
