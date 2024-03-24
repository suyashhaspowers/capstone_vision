import requests
from openai import OpenAI
import cv2
import time
import os
import base64
import errno
import ast
import csv
import json
from asyncio import Queue


port = '/dev/tty.usbserial-14440'
baud_rate = 57600

product_names = ['Dill Pickles', 'Banana Peppers', 'Black Olives', 'Green Olives']

product_mapping = {
    'Sliced Black Olives': product_names[2],
    'Sliced Green Olives': product_names[3],
    'Sliced Dill Pickles': product_names[0],
    'Hot Sliced Banana Peppers': product_names[1]
}

weight_values = Queue()

image_directory = "images"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer "
}

def make_post_request(url, headers, payload, retries=3):
    for _ in range(retries):
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response
        except ConnectionError as e:
            print(f"Error: {e}")
            continue
    raise ConnectionError("Failed to establish connection after multiple retries.")

def capture_photo():
    # Initialize the webcam
    cap = cv2.VideoCapture(0)

    # Set desired resolution (adjust as needed)
    desired_width = 1920
    desired_height = 1080
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, desired_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, desired_height)

    # Check if the webcam is opened correctly
    if not cap.isOpened():
        raise IOError("Cannot open webcam")

    # Wait for the camera to initialize and adjust light levels
    time.sleep(2)

    # while True:
    ret, frame = cap.read()
    if ret:
        # Save the frame as a lossless PNG image
        print("📸 Taking photo of inventory shelf.")
        path = f"{image_directory}/shelf.png"
        cv2.imwrite(path, frame, [cv2.IMWRITE_PNG_COMPRESSION, 0])
    else:
        print("Failed to capture image")

    # Wait for 2 seconds
    time.sleep(2)

    # Release the camera and close all windows
    cap.release()
    cv2.destroyAllWindows()
    
    image_files = [f for f in os.listdir(image_directory) if os.path.isfile(os.path.join(image_directory, f))]

    image_paths = []

    # Iterate over the list of image files and encode each one
    for image_file in image_files:
        if ('.png' or '.jpg' or '.jpeg') in image_file:
            image_path = os.path.join(image_directory, image_file)
            image_paths.append(image_path)

    encoded_image = encode_image(image_paths[0])

    return encoded_image


def encode_image(image_path):
    while True:
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except IOError as e:
            if e.errno != errno.EACCES:
                # Not a "file in use" error, re-raise
                raise
            # File is being written to, wait a bit and retry
            time.sleep(0.1)

def analyze(encoded_image, gpt_content):
    payload = {
        "model": "gpt-4-vision-preview",
        "messages": [
            {
                "role": "system",
                "content": gpt_content
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is on the shelf?"},
                    {
                        "type": "image_url",
                        "image_url": f"data:image/jpeg;base64,{encoded_image}",
                    }
                ]
            }
        ],
        "max_tokens": 2000,
    }

    try:
        response = make_post_request('https://api.openai.com/v1/chat/completions', headers, payload)
        print(response.json()['choices'][0]['message']['content'])
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

    return ast.literal_eval(response.json()['choices'][0]['message']['content'])

def make_post_request_to_subwai(weight_data, product_data):
    payload = {
        "products": []
    }

    used_inventory = []

    for index, value in enumerate(product_data):
        if value != None:
            product = {
                'product': product_mapping[value],
                'quantity': (weight_data[index] - 400) * 10
            }
            used_inventory.append(product_mapping[value])
            payload["products"].append(product)

    result = [item for item in product_names if item not in used_inventory]

    for product in result:
        product = {
                'product': product,
                'quantity': 0
            }
        payload["products"].append(product)

    url = 'https://subwai-deployment.vercel.app/api/addInventory'

    print(payload)
    payload = json.dumps(payload)

    try:
        response = requests.post(url, data=payload, headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        return response
    except ConnectionError as e:
        print(f"Error: {e}")
    raise ConnectionError("Failed to establish connection after multiple retries.")


def read_weight_data():
    try:
        with open('data.csv', 'r') as file:
            reader = csv.reader(file)
            for row in reader:
                values = []
                for x in range(3):
                    values.append(float(row[x]))
                return values[::-1]
    except FileNotFoundError:
        print("CSV file not found.")


def analyze_readings(weight_readings):
    content = """
                You will be given an image of an wooden shelf. This shelf is supposed to represent an inventory shelf.
                Boxes will be placed on this shelf. There can be a total of 3 boxes on the shelf. Sometimes there may be 2.
                Sometimes there be 1. Sometimes there may be none.
                Your task will be to classify the contents of the boxes of the shelf. Some Boxes are white and some are brown.
                You will do this by reading the labels on the boxes and placing them in an array to indicate its position.
                Think of the shelf as a grid system with 1 rows and 3 columns.
                Boxes on the left side of a row are in the first column.
                Boxes in the middle of the row are in the second column.
                Boxes on the right side of a row are in the third column.
                Sometimes columns can be empty.
                The following box labels exist on the boxes:
                1. Sliced Black Olives
                2. Sliced Green Olives
                3. Sliced Dill Pickles
                4. Hot Sliced Banana Peppers
                # An example output of your response would be:
                # ['Sliced Black Olives', None, 'Sliced Dill Pickles']
                # You only need to return the array.
                This means that Sliced Black Olives exists in the first column, the second column is empty, and  Sliced Green Olives exist in the third column.
                Another example output of your response would be:
                # [None, 'Hot Sliced Banana Peppers', None]
                For the image you are about to see:
                """
    
    truth_of_plates = []
    for index, value in enumerate(weight_readings):
        if value >= 100 or value <= -100:
            truth_of_plates.append(True)
            content = content + f" >There is a box in column #{index+1}"
        else:
            truth_of_plates.append(False)
            content = content + f" >There is no box in column #{index+1}"

    return content
    
    

def run():
    while True:
        print('Please enter your command: ')
        user_input = input()
        if user_input.lower() in ['exit', 'quit']:
            print("Exiting program.")
            break
        else:
            time.sleep(5)
            weight_readings = read_weight_data()
            gpt_content = analyze_readings(weight_readings)

            print(gpt_content)
            
            encoded_image = capture_photo()
            product_data = analyze(encoded_image, gpt_content)
            print(weight_readings)

            make_post_request_to_subwai(weight_readings, product_data)

run()