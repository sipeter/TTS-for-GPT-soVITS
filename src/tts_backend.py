import soundfile as sf
from flask import Flask, request, Response, jsonify, stream_with_context,send_file
import io, os
import urllib.parse,sys
import tempfile
import hashlib

# 将当前文件所在的目录添加到 sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from load_infer_info import load_character, character_name, get_wav_from_text_api, models_path, update_character_info

app = Flask(__name__)

# 存储临时文件的字典
temp_files = {}

# 用于防止重复请求
def generate_file_hash(*args):
    """生成基于输入参数的哈希值，用于唯一标识一个请求"""
    hash_object = hashlib.md5()
    for arg in args:
        hash_object.update(str(arg).encode())
    return hash_object.hexdigest()

@app.route('/character_list', methods=['GET'])
def character_list():
    return jsonify(update_character_info()['characters_and_emotions'])


@app.route('/tts', methods=['GET', 'POST'])
def tts():
    global character_name
    global models_path

    # 尝试从JSON中获取数据，如果不是JSON，则从查询参数中获取
    if request.is_json:
        data = request.json
    else:
        data = request.args

    text = urllib.parse.unquote(data.get('text', ''))
    cha_name = data.get('cha_name', None)
    expected_path = os.path.join(models_path, cha_name) if cha_name else None

    # 检查cha_name和路径
    if cha_name and cha_name != character_name and expected_path and os.path.exists(expected_path):
        character_name = cha_name
        print(f"Loading character {character_name}")
        load_character(character_name)  
    elif expected_path and not os.path.exists(expected_path):
        return jsonify({"error": f"Directory {expected_path} does not exist. Using the current character."}), 400

    text_language = data.get('text_language', '多语种混合')
    try:
        top_k = int(data.get('top_k', 6))
        top_p = float(data.get('top_p', 0.8))
        temperature = float(data.get('temperature', 0.8))
        stream = data.get('stream', 'False').lower() == 'true'
        save_temp = data.get('save_temp', 'False').lower() == 'true'
    except ValueError:
        return jsonify({"error": "Invalid parameters. They must be numbers."}), 400
    character_emotion = data.get('character_emotion', 'default')

    request_hash = generate_file_hash(text, text_language, top_k, top_p, temperature, character_emotion, character_name)
    if stream == False:
        if save_temp:
            if request_hash in temp_files:
                return send_file(temp_files[request_hash], mimetype='audio/wav')
            else:
                gen = get_wav_from_text_api(text, text_language, top_k=top_k, top_p=top_p, temperature=temperature, character_emotion=character_emotion, stream=stream)
                sampling_rate, audio_data = next(gen)
                temp_file_path = tempfile.mktemp(suffix='.wav')
                with open(temp_file_path, 'wb') as temp_file:
                    sf.write(temp_file, audio_data, sampling_rate, format='wav')
                temp_files[request_hash] = temp_file_path
                return send_file(temp_file_path, mimetype='audio/wav')
        else:
            gen = get_wav_from_text_api(text, text_language, top_k=top_k, top_p=top_p, temperature=temperature, character_emotion=character_emotion, stream=stream)
            sampling_rate, audio_data = next(gen)
            wav = io.BytesIO()
            sf.write(wav, audio_data, sampling_rate, format="wav")
            wav.seek(0)
            return Response(wav, mimetype='audio/wav')
    else:
        gen = get_wav_from_text_api(text, text_language, top_k=top_k, top_p=top_p, temperature=temperature, character_emotion=character_emotion, stream=stream)
        return Response(stream_with_context(gen),  mimetype='audio/wav')


import json
tts_port = 5000

# 取得模型文件夹路径
config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

if os.path.exists(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        _config = json.load(f)
        tts_port = _config.get("tts_port", 5000)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=tts_port)