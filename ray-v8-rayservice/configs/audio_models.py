# --------------------------------------------------------
# Installation requirement:
#   pip install git+https://github.com/huggingface/transformers
# If you cannot import `Falcon3AudioForConditionalGeneration` from `transformers`, use the definition from the section `Falcon3-Audio Model Definition`
# --------------------------------------------------------

import requests
import librosa
import numpy as np
from io import BytesIO
from pydub import AudioSegment
from transformers import AutoProcessor, Falcon3AudioForConditionalGeneration
from pydantic import BaseModel
from typing import Optional, List

def load_audio(audio_path, sampling_rate=16000):
    """
    Loads audio from various sources (local files or HTTPS URLs).
    Returns audio as a NumPy array.
    """
    if audio_path.startswith("https://"):
        response = requests.get(audio_path, stream=True)
        response.raise_for_status()
        open_function = lambda path, mode: BytesIO(response.content)
    else:
        open_function = open

    with open_function(audio_path, 'rb') as f:
        file_ext = audio_path.split('.')[-1].lower()
        if file_ext in ['flac', 'wav']:
            audio_array = librosa.load(f, sr=sampling_rate)[0]
        elif file_ext in ['mp3', 'mp4']:
            audio_segment = AudioSegment.from_file(BytesIO(f.read()), format=file_ext)
            audio_array = np.array(audio_segment.get_array_of_samples()) / (2**15)
            if audio_segment.channels == 2:
                audio_array = audio_array.reshape((-1, 2)).mean(axis=1)
            audio_array = librosa.resample(
                audio_array, 
                orig_sr=audio_segment.frame_rate,
                target_sr=sampling_rate
            )
        else:
            raise ValueError(f"Unsupported audio format: {file_ext}")

    return audio_array

def complete_chat(model, processor, audio_path, prompt):

    conversation = [
    {"role": "user", "content": [
        {"type": "audio", "audio_url": audio_path},
    ]},
    {"role": "user", "content": prompt},
    ]
    
    text = processor.apply_chat_template(conversation, add_generation_prompt=True, tokenize=False)
    audio = load_audio(audio_path)

    inputs = processor(text=text, audios=audio, return_tensors="pt", 
                       padding=False, sampling_rate=16000)
    if "token_type_ids" in inputs:
        del inputs["token_type_ids"]

    for k, v in inputs.items():
        inputs[k] = v.to(next(model.parameters()).device)

    generate_ids = model.generate(**inputs)
    generate_ids = generate_ids[:, inputs.input_ids.size(1):]

    return generate_ids

class AudioInput(BaseModel):
    audio_url: str  # URL or path to the audio file
    sampling_rate: Optional[int] = 16000  # Sampling rate for processing

class ChatMessage(BaseModel):
    role: str  # e.g., "user", "assistant"
    content: str  # Text content of the message

class AudioChatRequest(BaseModel):
    audio: AudioInput  # Audio input details
    prompt: str  # Text prompt for the chat

class AudioChatResponse(BaseModel):
    generated_text: str  # Generated text response
    confidence: Optional[float] = None  # Confidence score (if applicable)

class ErrorResponse(BaseModel):
    error: str  # Error message
    code: Optional[int] = None  # Optional error code
