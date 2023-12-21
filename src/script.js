let positiveCount = 0;
let negativeCount = 0;

document.getElementById('analyzeButton').addEventListener('click', function() {
    let fileInput = document.getElementById('csvFileInput');
    let file = fileInput.files[0];
    positiveCount = 0;
    negativeCount = 0;
    clearTable();
    parseCSV(file);
});

function parseCSV(file) {
    let reader = new FileReader();
    reader.onload = function(event) {
        let lines = event.target.result.split('\n');
        lines.forEach((line, index) => {
            if (line.trim() !== '' && index > 0) { // Bỏ qua hàng đầu tiên nếu đó là tiêu đề
                callAPI(line.trim());
            }
        });
    };
    reader.readAsText(file);
}

async function callAPI(comment) {
    try {
        let response = await fetch('http://127.0.0.1:5000/predict', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ "text": comment })
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        let data = await response.json();
        updateTable(comment, data.prediction);
    } catch (error) {
        console.error('Error calling the API:', error);
    }
}

function updateTable(comment, prediction) {
    let resultsTable = document.getElementById('resultsTable').getElementsByTagName('tbody')[0];
    let newRow = resultsTable.insertRow();
    let commentCell = newRow.insertCell(0);
    let predictionCell = newRow.insertCell(1);

    commentCell.textContent = comment;
    predictionCell.textContent = prediction === 1 ? 'Tích cực' : 'Tiêu cực';

    if (prediction === 1) {
        positiveCount++;
    } else {
        negativeCount++;
    }

    updateCounts();
}

function updateCounts() {
    document.getElementById('positiveCount').textContent = positiveCount;
    document.getElementById('negativeCount').textContent = negativeCount;
}

function clearTable() {
    document.getElementById('resultsTable').getElementsByTagName('tbody')[0].innerHTML = '';
}
