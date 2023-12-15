from flask import Flask, request, jsonify
from model import TextClassificationModel, preprocess_text, predict
import torch

app = Flask(__name__)

# Load the trained model
model_path = "./trained_model.pth"
vocab_size = 10000  # Update with the correct value
embed_dim = 100  # Update with the correct value
num_class = 2  # Update with the correct value

loaded_model = TextClassificationModel(vocab_size, embed_dim, num_class)
loaded_model.load_state_dict(torch.load(model_path))
loaded_model.eval()

# Define an endpoint for prediction
@app.route('/predict', methods=['POST'])
def predict_endpoint():
    data = request.get_json(force=True)
    text = data['text']

    # Perform preprocessing if needed
    preprocessed_text = preprocess_text(text)

    # Make a prediction using the loaded model
    prediction = predict(preprocessed_text)

    # Return the prediction as JSON
    return jsonify({'prediction': int(prediction)})

if __name__ == '__main__':
    app.run(port=3290)
