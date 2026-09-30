import torch
from flask import Flask, request, render_template
from flask_cors import CORS
from transformers import AutoTokenizer, AutoModelForCausalLM

app = Flask(__name__)
CORS(app)

# 1. Detección automática de hardware (GPU / MPS / CPU)
device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
print(f"Cargando modelo SmolLM2 en dispositivo: {device}...")

model_name = "HuggingFaceTB/SmolLM2-360M-Instruct"

tokenizer = AutoTokenizer.from_pretrained(model_name)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16 if device != "cpu" else torch.float32,
    device_map=device
)

system_prompt = {
    "role": "system",
    "content": "Eres un asistente de IA útil, servicial y amigable. Responde siempre en español proporcionando explicaciones claras, estructuradas y completas."
}

# Historial estructurado para la API de Chat
conversation_history = []

@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/chatbot', methods=['POST'])
def handle_prompt():
    data = request.get_json()
    if not data or "prompt" not in data:
        return "Falta el parámetro 'prompt'", 400

    input_text = data["prompt"]

    # Agregar el mensaje del usuario al historial de la sesión
    conversation_history.append({"role": "user", "content": input_text})

    # Mantener los últimos 8 mensajes (4 turnos) + el System Prompt único
    recent_history = conversation_history[-8:]
    full_messages = [system_prompt] + recent_history

    # Formatear el input con el template oficial del modelo
    tokenized = tokenizer.apply_chat_template(
        full_messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True,
        truncation=True,
        max_length=512
    ).to(device)

    # Inferencia
    with torch.inference_mode():
        outputs = model.generate(
            input_ids=tokenized["input_ids"],
            attention_mask=tokenized["attention_mask"],
            max_new_tokens=300,  # Aumentado de 100 a 250 (aprox. 180-200 palabras)
            temperature=0.6,
            top_p=0.85,
            do_sample=True,
            repetition_penalty=1.1,
            pad_token_id=tokenizer.pad_token_id
        )

    # Extraer la respuesta (descartando los tokens del prompt original)
    input_length = tokenized["input_ids"].shape[-1]
    response = tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True).strip()

    # Guardar la respuesta generada en el historial
    conversation_history.append({"role": "assistant", "content": response})

    return response

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)