from flask import Flask, request, jsonify
import torch
from torchtext.vocab import Vocab
from text_classification import TextClassificationModel
from torchtext.data.utils import get_tokenizer
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Load Vocabulary
vocabulary = torch.load("vocabulary.pth")
vocabulary.set_default_index(vocabulary["<unk>"])

# Load Model
num_class = 2
model = TextClassificationModel(len(vocabulary), 100, num_class)
model.load_state_dict(torch.load("trained_model.pth", map_location=torch.device('cpu')))
model.eval()

# Tokenizer
tokenizer = get_tokenizer("basic_english")

def predict(text):
    with torch.no_grad():
        encoded = torch.tensor(vocabulary(tokenizer(text)))
        output = model(encoded, torch.tensor([0]))
    return output.argmax(1).item()

@app.route('/predict', methods=['POST'])
def predict_endpoint():
    data = request.json
    text = data['text']
    prediction = predict(text)
    return jsonify({"prediction": prediction})
    
if __name__ == "__main__":
    app.run(debug=True)
    # from waitress import serve
    # serve(app, host="0.0.0.0", port=3299)
