import paho.mqtt.client as mqtt
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import load_model
import numpy as np
from flask import Flask, request, render_template, jsonify, current_app
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt
from tensorflow import keras
import numpy as np
from keras.models import load_model
from joblib import load
import logging
import threading

# MQTT Settings
app = Flask(__name__)
socketio = SocketIO(app)

broker_address = "broker.mqtt-dashboard.com"
topic = "Max30100"
data = []
data30 = []

loaded_model_gru = load_model('trained_gru_model.h5')  # Replace with your model file name
loaded_model_tree = load('tree.joblib')

def Prediksi(data):
    # Load the saved model

    # Load the data
    # data = pd.read_csv('dd.csv')

    # Normalize the data
    scaler = MinMaxScaler()
    scaled_data = scaler.fit_transform(data)

    # Reshape the data to match the model input shape
    input_data = scaled_data.reshape((1, scaled_data.shape[0], scaled_data.shape[1]))

    # Predict the next 30 seconds' BPM and SpO2
    predicted_values = loaded_model_gru.predict(input_data)

    # Inverse transform the predicted values to get the original scale
    predicted_values = scaler.inverse_transform(predicted_values)

    bpm = predicted_values[0, 0]
    spo2 = predicted_values[0, 1]


    return bpm, spo2

def klasifikasi(heart_rate, spo2):
    # Create a NumPy array with the input values
    input_data = np.array([[heart_rate, spo2]])

    # Predict using the loaded model
    prediction = loaded_model_tree.predict(input_data)

    # Return the prediction
    return prediction[0]


def on_message(client, userdata, msg):
    try:
        global data30
        global data
        global hasilKlasifikasi
        message = msg.payload.decode()

        # Extracting heart rate and SpO2 from the message
        extracted_data = message.split("/")
        heart_rate = int(extracted_data[0].split(": ")[1].split(" bpm")[0])
        spo2 = int(extracted_data[1].split(": ")[1].split("%")[0])

        # Append heart_rate and spo2 to the data list
        if heart_rate != 0 and spo2 != 0:
            data.append([heart_rate, spo2])

        if len(data) > 29:
            data30 = data.copy()
            data.clear()
            bpm,spo2 = Prediksi(data30)
            spo2 = int(spo2)
            hasilKlasifikasi = klasifikasi(bpm,spo2) 
            if hasilKlasifikasi == 1:
                hipoksia = "positif"
            else:
                hipoksia = "negatif"
            display_numbers(heart_rate, spo2, hipoksia)
        else:
            display_bpm_spo2(heart_rate, spo2)

    except ValueError as ve:
        logging.error(f"Value error! (not float): {ve}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

def display_bpm_spo2(heartrate, spO2):
    print(f"Received heartrate data from MQTT: {heartrate} \nand spO2 data from MQTT: {spO2}")
    socketio.emit('status_update', {'heartrate': heartrate, 'spO2': spO2})

def display_numbers(heartrate, spO2, result):
    print(f"Received heartrate data from MQTT: {heartrate} \nand spO2 data from MQTT: {spO2} \nand result: {result}")
    socketio.emit('status_hipoksia_update', {'heartrate': heartrate, 'spO2': spO2, 'classification' : result})
    
# MQTT client setup
client = mqtt.Client()
client.on_message = on_message
client.connect(broker_address, 1883, 60)
client.subscribe(topic)
client.loop_start()

# ==========================================   Frontend settings   ================================================ #

@app.route('/predict_hipoksia', methods=['POST'])
def predict_hipoksia():
    global data30
    global data
    global hasilKlasifikasi
    try:
        data = request.json
        heart_rate = float(data.get('heartrate'))
        spo2 = float(data.get('spO2'))

        # Append heart_rate and spo2 to the data list
        if heart_rate != 0 and spo2 != 0:
            data.append([heart_rate, spo2])

        if len(data) > 29:
            data30 = data.copy()
            data.clear()
            bpm,spo2 = Prediksi(data30)
            spo2 = int(spo2)
            hasilKlasifikasi = klasifikasi(bpm,spo2) 
            if hasilKlasifikasi == 1:
                hipoksia = "positif"
            else:
                hipoksia = "negatif"
                
            display_numbers(heart_rate, spo2, hipoksia)
            return jsonify({'heartrate': heart_rate, 'spO2': spo2, 'classification' : hipoksia})

        else:
            display_bpm_spo2(heart_rate, spo2)
            return jsonify({'heartrate': heart_rate, 'spO2': spo2, 'classification': None})

    except ValueError:
        return jsonify({'error': 'Invalid temperature data. Could not convert to float.'}), 400
    except Exception as e:
        return jsonify({'error': f'An error occurred: {e}'}), 500
    

@app.route('/')
def index():
    return render_template('predict_hipoksia.html')

# ==========================================      Run the web      ================================================ #
if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)

socketio.run(app)
