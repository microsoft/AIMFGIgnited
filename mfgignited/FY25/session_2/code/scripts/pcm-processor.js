// pcm-processor.js
// AudioWorkletProcessor: Converts Float32 audio to Int16 PCM, computes RMS, and posts data to main thread.
class PCMProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this._buffer = [];
        this._bufferSize = 1024; // Match Python chunk size
    }

    process(inputs, outputs, parameters) {
        const input = inputs[0];
        if (input && input[0]) {
            const channelData = input[0];
            // Buffer audio until we have enough samples
            for (let i = 0; i < channelData.length; i++) {
                this._buffer.push(channelData[i]);
                if (this._buffer.length === this._bufferSize) {
                    // Convert Float32 [-1, 1] to Int16 PCM and compute RMS
                    const pcm16 = new Int16Array(this._bufferSize);
                    let sumSquares = 0;
                    for (let j = 0; j < this._bufferSize; j++) {
                        let s = Math.max(-1, Math.min(1, this._buffer[j]));
                        pcm16[j] = s < 0 ? s * 32768 : s * 32767;
                        sumSquares += s * s;
                    }
                    const rms = Math.sqrt(sumSquares / this._bufferSize);
                    // Post both the PCM data and RMS value
                    this.port.postMessage({ pcm16, rms });
                    this._buffer = [];
                }
            }
        }
        return true;
    }
}

registerProcessor('pcm-processor', PCMProcessor);
