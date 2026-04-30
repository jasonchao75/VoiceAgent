import sys
import soundfile as sf
from scipy.signal import resample
import numpy as np

def upsample_wav(in_file, out_file):
    data, samplerate = sf.read(in_file)
    target_sr = 16000
    
    if samplerate == target_sr:
        sf.write(out_file, data, target_sr)
        return
        
    duration = len(data) / samplerate
    target_samples = int(duration * target_sr)
    
    resampled_data = resample(data, target_samples)
    
    # Write as 16-bit PCM
    sf.write(out_file, resampled_data, target_sr, subtype='PCM_16')
    print(f"Successfully resampled {in_file} from {samplerate}Hz to {target_sr}Hz -> {out_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python upsample.py <input.wav> <output.wav>")
        sys.exit(1)
    upsample_wav(sys.argv[1], sys.argv[2])